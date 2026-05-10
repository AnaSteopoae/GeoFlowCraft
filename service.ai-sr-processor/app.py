"""
GeoFlowCraft — Super-Resolution Microservice
=============================================
Serviciu FastAPI care expune modele de super-rezoluție (DualBranchSRNet)
pentru imagini satelitare Sentinel-2 + Sentinel-1.

Modele disponibile:
  - DB v1 (α=0.0):  fidelitate spectrală maximă (PSNR ~28.57 dB)
  - GAN v3 (α=1.0): margini ascuțite, blur minim (Edge ~88.7% GT)
  - Interpolat (α configrabil): compromis continuu între cele două

Endpoint-uri:
  POST /predict/   — primește GeoTIFF (S2+S1, 6 benzi), returnează GeoTIFF SR
  GET  /modes      — listează modurile disponibile
  GET  /health     — health check
"""

import io
import logging
import time
from collections import OrderedDict

import numpy as np
import rasterio
from rasterio.transform import Affine
import torch
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.responses import StreamingResponse

from model_arch import DualBranchSARNet
from tiling import predict_with_tiling
from utils import (
    normalize_s2,
    normalize_s1,
    tensor_to_geotiff_bytes,
    denormalize_sr_output,
)

# ──────────────────────────────────────────────
# Configurare logging
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sr-service")

# ──────────────────────────────────────────────
# Configurare dispozitiv (CPU acum, GPU ulterior)
# ──────────────────────────────────────────────
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Dispozitiv folosit: {device}")

# ──────────────────────────────────────────────
# Inițializare FastAPI
# ──────────────────────────────────────────────
app = FastAPI(
    title="GeoFlowCraft SR Service",
    description="Super-Resolution for Sentinel-2 imagery enhanced with Sentinel-1 SAR",
    version="1.0.0",
)

# ──────────────────────────────────────────────
# Încărcare modele la startup
# ──────────────────────────────────────────────
MODEL_CONFIG = {
    "num_features": 64,
    "num_rcab_branch": 4,
    "num_rcab_shared": 8,
    "reduction": 16,
    "scale": 4,
}

DB_V1_PATH = "model/db_v1_best.pth"
GAN_V3_PATH = "model/gan_v3_last.pth"

PRESETS = {
    "fidelity": {
        "alpha": 0.0,
        "description": "DB v1 — maximum spectral fidelity (PSNR ~28.57 dB). "
                       "Best for NDVI, change detection, quantitative analysis."
    },
    "balanced": {
        "alpha": 0.9,
        "description": "Interpolated α=0.9 — best visual + fidelity balance "
                       "(PSNR ~28.13 dB, Edge ~82.2% GT)."
    },
    "sharp": {
        "alpha": 1.0,
        "description": "GAN v3 — sharpest edges, lowest blur "
                       "(Edge ~88.7% GT). For visual inspection and cartography."
    },
}

# ──────────────────────────────────────────────
# Variabile globale pentru modele
# ──────────────────────────────────────────────
db_state_dict = None
gan_state_dict = None
model = None
alpha_cache = OrderedDict()
MAX_CACHE_SIZE = 5


def load_models():
    global db_state_dict, gan_state_dict, model

    logger.info("Încărcare checkpoint DB v1...")
    db_checkpoint = torch.load(DB_V1_PATH, map_location=device, weights_only=False)
    db_state_dict = db_checkpoint.get("model_state_dict", db_checkpoint)

    logger.info("Încărcare checkpoint GAN v3...")
    gan_checkpoint = torch.load(GAN_V3_PATH, map_location=device, weights_only=False)
    gan_state_dict = gan_checkpoint.get("generator_state_dict",
                     gan_checkpoint.get("model_state_dict", gan_checkpoint))

    model = DualBranchSARNet(**MODEL_CONFIG).to(device)
    model.eval()
    model.load_state_dict(db_state_dict)
    logger.info("Modele încărcate cu succes.")


def get_interpolated_state_dict(alpha: float) -> dict:
    alpha_key = round(alpha, 4)
    if alpha_key in alpha_cache:
        logger.info(f"Cache hit pentru α={alpha_key}")
        return alpha_cache[alpha_key]

    interpolated = OrderedDict()
    for key in db_state_dict:
        interpolated[key] = (1 - alpha) * db_state_dict[key] + alpha * gan_state_dict[key]

    alpha_cache[alpha_key] = interpolated
    if len(alpha_cache) > MAX_CACHE_SIZE:
        alpha_cache.popitem(last=False)

    logger.info(f"Interpolat α={alpha_key} (cache size: {len(alpha_cache)})")
    return interpolated


def apply_alpha(alpha: float):
    if alpha == 0.0:
        model.load_state_dict(db_state_dict)
    elif alpha == 1.0:
        model.load_state_dict(gan_state_dict)
    else:
        interpolated = get_interpolated_state_dict(alpha)
        model.load_state_dict(interpolated)


# ──────────────────────────────────────────────
# Evenimente de startup
# ──────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    load_models()
    logger.info(f"SR Service pornit pe {device}")


# ──────────────────────────────────────────────
# Endpoint: POST /predict/
# ──────────────────────────────────────────────
@app.post("/predict/")
async def predict(
    file: UploadFile = File(..., description="GeoTIFF cu 6 benzi: 4×S2 (B,G,R,NIR) + 2×S1 (VV,VH)"),
    mode: str = Query("balanced", description="Preset: fidelity | balanced | sharp"),
    alpha: float = Query(None, ge=0.0, le=1.0, description="Custom α (suprascrie mode)")
):
    start_time = time.time()

    # ── 1. Determină alpha ──
    if alpha is not None:
        effective_alpha = alpha
    elif mode in PRESETS:
        effective_alpha = PRESETS[mode]["alpha"]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Mod necunoscut: '{mode}'. Opțiuni: {list(PRESETS.keys())}"
        )

    # ── 2. Citește GeoTIFF-ul ──
    try:
        contents = await file.read()
        with rasterio.open(io.BytesIO(contents)) as src:
            data = src.read().astype(np.float32)
            profile = src.profile.copy()
            original_transform = src.transform
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Eroare la citirea GeoTIFF: {e}")

    if data.shape[0] != 6:
        raise HTTPException(
            status_code=400,
            detail=f"Așteptam 6 benzi (4×S2 + 2×S1), am primit {data.shape[0]}"
        )

    # ── 3. Separă și normalizează ──
    s2_norm = normalize_s2(data[:4])
    s1_norm = normalize_s1(data[4:])

    # ── 4. Aplică alpha ──
    apply_alpha(effective_alpha)

    # ── 5. Inferență (cu tiling automat pentru imagini mari) ──
    sr_numpy = predict_with_tiling(model, s2_norm, s1_norm, device)

    # ── 6. Denormalizare ──
    sr_numpy = denormalize_sr_output(sr_numpy)

    # ── 7. Actualizează metadatele geospațiale ──
    new_transform = Affine(
        original_transform.a / 4,
        original_transform.b,
        original_transform.c,
        original_transform.d,
        original_transform.e / 4,
        original_transform.f,
    )

    profile.update({
        "count": 4,
        "height": sr_numpy.shape[1],
        "width": sr_numpy.shape[2],
        "transform": new_transform,
        "dtype": "float32",
    })

    # ── 8. Scrie GeoTIFF în memorie și returnează ──
    output_bytes = tensor_to_geotiff_bytes(sr_numpy, profile)

    elapsed = time.time() - start_time
    logger.info(
        f"Inferență completă: mode={mode}, α={effective_alpha:.2f}, "
        f"input={data.shape[1]}×{data.shape[2]}, "
        f"output={sr_numpy.shape[1]}×{sr_numpy.shape[2]}, "
        f"timp={elapsed:.2f}s"
    )

    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="image/tiff",
        headers={
            "Content-Disposition": "attachment; filename=sr_output.tif",
            "X-SR-Alpha": str(effective_alpha),
            "X-SR-Mode": mode,
            "X-Processing-Time": f"{elapsed:.2f}s",
        }
    )


# ──────────────────────────────────────────────
# Endpoint: GET /modes
# ──────────────────────────────────────────────
@app.get("/modes")
async def get_modes():
    return {
        "presets": PRESETS,
        "custom_alpha": {
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "description": "α=0 (fidelity) ↔ α=1 (sharp). Suprascrie preset-ul."
        },
        "device": str(device),
    }


# ──────────────────────────────────────────────
# Endpoint: GET /health
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy" if model is not None else "loading",
        "device": str(device),
        "models_loaded": {
            "db_v1": db_state_dict is not None,
            "gan_v3": gan_state_dict is not None,
        },
    }