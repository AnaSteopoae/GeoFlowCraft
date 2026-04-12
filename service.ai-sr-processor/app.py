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
from functools import lru_cache
from collections import OrderedDict

import numpy as np
import rasterio
from rasterio.transform import Affine
import torch
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.responses import StreamingResponse

from model_arch import DualBranchSARNet
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
# Când muți pe HPC cu GPU, această linie detectează automat CUDA:
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
# Parametrii arhitecturii — trebuie să corespundă cu ce ai antrenat pe HPC
MODEL_CONFIG = {
    "num_features": 64,       # nr. filtre per layer
    "num_rcab_branch": 4,     # RCAB per ramură (S2 și S1 separat)
    "num_rcab_shared": 8,     # RCAB în corpul comun după fuziune
    "reduction": 16,          # ratio atenție canal
    "scale": 4,               # upsampling ×4 (10m → 2.5m)
}

# Checkpoint-uri — relative la directorul containerului
DB_V1_PATH = "model/db_v1_best.pth"
GAN_V3_PATH = "model/gan_v3_last.pth"

# Presetări expuse utilizatorilor
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
# Stocăm state_dict-urile (parametrii) celor două modele,
# plus un cache pentru alpha-uri deja calculate.
db_state_dict = None       # parametrii DB v1
gan_state_dict = None      # parametrii GAN v3
model = None               # instanța activă DualBranchSRNet
alpha_cache = OrderedDict() # cache: alpha -> state_dict interpolat
MAX_CACHE_SIZE = 5          # nr. maxim de alpha-uri cached


def load_models():
    """
    Încarcă checkpoint-urile de pe disc în memorie.

    De ce stocăm state_dict-uri separate?
    - Network interpolation funcționează la nivel de parametri:
      w_interp = (1 - α) * w_db + α * w_gan
    - Avem nevoie de ambele seturi de greutăți mereu în memorie
    - Modelul activ (instanța) primește greutățile interpolate
    """
    global db_state_dict, gan_state_dict, model

    logger.info("Încărcare checkpoint DB v1...")
    db_checkpoint = torch.load(DB_V1_PATH, map_location=device, weights_only=False)
    # Checkpoint-ul poate conține doar state_dict sau un dict cu cheia 'model_state_dict'
    db_state_dict = db_checkpoint.get("model_state_dict", db_checkpoint)

    logger.info("Încărcare checkpoint GAN v3...")
    gan_checkpoint = torch.load(GAN_V3_PATH, map_location=device, weights_only=False)
    # gan_state_dict = gan_checkpoint.get("model_state_dict", gan_checkpoint)
    gan_state_dict = gan_checkpoint.get("generator_state_dict", 
                 gan_checkpoint.get("model_state_dict", gan_checkpoint))

    # Creează o instanță a rețelei (inițializată random, o suprascriem imediat)
    model = DualBranchSARNet(**MODEL_CONFIG).to(device)
    model.eval()  # mod evaluare — dezactivează dropout, BatchNorm în mod inferență

    # Încarcă implicit DB v1 (fidelitate) ca default
    model.load_state_dict(db_state_dict)
    logger.info("Modele încărcate cu succes.")


def get_interpolated_state_dict(alpha: float) -> dict:
    """
    Network Interpolation: amestecă parametrii DB și GAN.

    Formula: w = (1 - α) * w_db + α * w_gan

    - α = 0.0 → 100% DB v1 (fidelitate pură)
    - α = 1.0 → 100% GAN v3 (claritate pură)
    - α = 0.9 → 90% GAN + 10% DB (balans optim)

    De ce la nivel de parametri (nu la nivel de output)?
    - Un singur forward pass (nu două)
    - Gradienții sunt mai coerenți (relevant la fine-tuning)
    - Calitate superioară vs. media pixelilor din două output-uri

    Cache-ul evită recalcularea la request-uri consecutive cu același α.
    """
    # Verifică cache
    alpha_key = round(alpha, 4)  # rotunjire pentru a evita erori float
    if alpha_key in alpha_cache:
        logger.info(f"Cache hit pentru α={alpha_key}")
        return alpha_cache[alpha_key]

    # Interpolează parametru cu parametru
    interpolated = OrderedDict()
    for key in db_state_dict:
        interpolated[key] = (1 - alpha) * db_state_dict[key] + alpha * gan_state_dict[key]

    # Adaugă în cache (cu limită de dimensiune)
    alpha_cache[alpha_key] = interpolated
    if len(alpha_cache) > MAX_CACHE_SIZE:
        alpha_cache.popitem(last=False)  # elimină cel mai vechi

    logger.info(f"Interpolat α={alpha_key} (cache size: {len(alpha_cache)})")
    return interpolated


def apply_alpha(alpha: float):
    """
    Aplică un alpha pe modelul activ.

    Cazuri speciale (α=0 și α=1) folosesc direct checkpoint-urile
    originale fără interpolare, pentru eficiență.
    """
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
    """
    Se execută o singură dată la pornirea serverului.
    Încarcă modelele în memorie înainte de a accepta request-uri.
    """
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
    """
    Pipeline-ul de inferență super-rezoluție.

    Input:  GeoTIFF 6 benzi la 10m (Sentinel-2 B/G/R/NIR + Sentinel-1 VV/VH)
    Output: GeoTIFF 4 benzi la 2.5m (B/G/R/NIR super-rezolvat)

    Pași:
    1. Citește GeoTIFF-ul din request
    2. Separă benzile S2 (4) și S1 (2)
    3. Normalizează fiecare set conform convențiilor de antrenare
    4. Rulează inferența prin DualBranchSRNet
    5. Denormalizează output-ul
    6. Actualizează metadatele geospațiale (transform, dimensiuni)
    7. Returnează GeoTIFF
    """
    start_time = time.time()

    # ── 1. Determină alpha ──
    if alpha is not None:
        # Utilizatorul a specificat un alpha custom
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
            # src.read() returnează (bands, height, width)
            data = src.read().astype(np.float32)  # shape: (6, H, W)
            profile = src.profile.copy()          # metadate geospațiale
            original_transform = src.transform    # Affine transform
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Eroare la citirea GeoTIFF: {e}")

    # Validare: așteptăm exact 6 benzi
    if data.shape[0] != 6:
        raise HTTPException(
            status_code=400,
            detail=f"Așteptam 6 benzi (4×S2 + 2×S1), am primit {data.shape[0]}"
        )

    # ── 3. Separă și normalizează ──
    s2_raw = data[:4]   # (4, H, W) — B, G, R, NIR
    s1_raw = data[4:]   # (2, H, W) — VV, VH

    s2_norm = normalize_s2(s2_raw)    # /10000, clip [0,1]
    s1_norm = normalize_s1(s1_raw)    # dB conversion, min-max norm

    # ── 4. Creează tensorii PyTorch ──
    # Adaugă dimensiunea batch: (1, C, H, W)
    s2_tensor = torch.from_numpy(s2_norm).unsqueeze(0).to(device)
    s1_tensor = torch.from_numpy(s1_norm).unsqueeze(0).to(device)

    # ── 5. Aplică alpha și rulează inferența ──
    apply_alpha(effective_alpha)

    with torch.no_grad():  # dezactivează calculul gradienților (economie memorie)
        sr_tensor = model(s2_tensor, s1_tensor)  # (1, 4, H*4, W*4)

    # ── 6. Post-procesare ──
    sr_numpy = sr_tensor.squeeze(0).cpu().numpy()   # (4, H*4, W*4)
    sr_numpy = denormalize_sr_output(sr_numpy)       # înapoi la scara reflectanță

    # ── 7. Actualizează metadatele geospațiale ──
    # La ×4, rezoluția pixelului scade de 4 ori (10m → 2.5m)
    # Affine transform: (pixel_size_x, 0, origin_x, 0, -pixel_size_y, origin_y)
    new_transform = Affine(
        original_transform.a / 4,   # pixel_size_x / 4
        original_transform.b,       # 0 (fără rotație)
        original_transform.c,       # origin_x (neschimbat)
        original_transform.d,       # 0 (fără rotație)
        original_transform.e / 4,   # pixel_size_y / 4 (negativ)
        original_transform.f,       # origin_y (neschimbat)
    )

    profile.update({
        "count": 4,                              # 4 benzi output (B,G,R,NIR)
        "height": sr_numpy.shape[1],             # H × 4
        "width": sr_numpy.shape[2],              # W × 4
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
    """
    Returnează modurile disponibile cu descrieri.
    Frontend-ul folosește acest endpoint pentru a popula selectorul de mod.
    """
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
    """
    Health check — folosit de Docker healthcheck și de load balancere.
    Verifică că modelul e încărcat și funcțional.
    """
    return {
        "status": "healthy" if model is not None else "loading",
        "device": str(device),
        "models_loaded": {
            "db_v1": db_state_dict is not None,
            "gan_v3": gan_state_dict is not None,
        },
    }