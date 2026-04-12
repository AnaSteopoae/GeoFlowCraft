"""
s1_downloader.py — Descărcare S1 procesat via Sentinel Hub Process API
======================================================================

Înlocuiește complet pipeline-ul SNAP (15-20 min) cu un request HTTP (~30s).
Sentinel Hub face intern: Apply-Orbit → ThermalNoise → Calibration → Terrain-Correction.

Output: GeoTIFF cu 2 benzi (VV, VH) în σ⁰ putere liniară, ortorectificat,
        co-registrat pe grila S2 (aceeași rezoluție, CRS, extindere).

Integrare: importat în main.py, apelat din endpoint-ul /download/s1
"""

import io
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

logger = logging.getLogger("copernicus-service")


# ──────────────────────────────────────────────
# Configurare Sentinel Hub (CDSE)
# ──────────────────────────────────────────────
# URL-urile specifice CDSE — diferite de sentinelhub.com comercial
SH_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
SH_BASE_URL = "https://sh.dataspace.copernicus.eu"
SH_PROCESS_URL = f"{SH_BASE_URL}/api/v1/process"

# Evalscript: returnează VV și VH ca FLOAT32 (putere liniară σ⁰)
# Echivalent cu output-ul SNAP după Calibration (Sigma0)
EVALSCRIPT_S1_SIGMA0 = """
//VERSION=3
function setup() {
    return {
        input: [{
            bands: ["VV", "VH"]
        }],
        output: {
            bands: 2,
            sampleType: "FLOAT32"
        }
    };
}
function evaluatePixel(sample) {
    return [sample.VV, sample.VH];
}
"""


async def get_sh_token(client_id: str, client_secret: str) -> str:
    """
    Obține token OAuth2 de la CDSE pentru Sentinel Hub API.
    
    Sentinel Hub pe CDSE folosește un endpoint OAuth separat de cel
    pentru descărcări OData (care e în auth.py).
    
    Token-ul expiră în ~10 minute — pentru producție ar trebui cache.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SH_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def download_s1_processed(
    bbox: tuple,
    target_date: datetime,
    output_path: str,
    client_id: str,
    client_secret: str,
    days_tolerance: int = 6,
    resolution: int = 10,
) -> dict:
    """
    Descarcă S1 GRD procesat (σ⁰, ortorectificat) via Sentinel Hub.

    Înlocuiește complet:
    1. Descărcare S1 GRD .zip de pe CDSE
    2. SNAP GPT (Apply-Orbit → ThermalNoise → Calibration → Terrain-Correction)

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) în WGS84
        target_date: data scenei S2 selectate de utilizator
        output_path: calea unde salvează GeoTIFF-ul S1
        client_id: OAuth client ID pentru Sentinel Hub CDSE
        client_secret: OAuth client secret
        days_tolerance: fereastră temporală ±zile (default ±6, ciclul S1)
        resolution: rezoluție în metri (default 10m, ca S2)

    Returns:
        dict cu metadate: path, shape, date_range, bbox
    """
    import httpx

    logger.info(f"Descărcare S1 procesat: bbox={bbox}, date={target_date.date()}, ±{days_tolerance} zile")

    # ── 1. Autentificare ──
    token = await get_sh_token(client_id, client_secret)

    # ── 2. Calculează dimensiunile imaginii la rezoluția dorită ──
    min_lon, min_lat, max_lon, max_lat = bbox
    # Aproximare: 1 grad lat ≈ 111 km, 1 grad lon ≈ 111 km × cos(lat)
    import math
    lat_center = (min_lat + max_lat) / 2
    width_m = (max_lon - min_lon) * 111320 * math.cos(math.radians(lat_center))
    height_m = (max_lat - min_lat) * 110540

    width_px = max(1, int(round(width_m / resolution)))
    height_px = max(1, int(round(height_m / resolution)))

    # Sentinel Hub limitează la 2500×2500 per request
    if width_px > 2500 or height_px > 2500:
        logger.warning(f"Imagine prea mare ({width_px}×{height_px}), limitez la 2500×2500")
        width_px = min(width_px, 2500)
        height_px = min(height_px, 2500)

    # ── 3. Interval temporal ──
    date_from = (target_date - timedelta(days=days_tolerance)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = (target_date + timedelta(days=days_tolerance)).strftime("%Y-%m-%dT23:59:59Z")

    # ── 4. Request body ──
    # Acesta e echivalentul a tot ce face SNAP-ul:
    # - backCoeff: SIGMA0_ELLIPSOID → calibrare σ⁰ (ca SNAP Calibration)
    # - orthorectify: true → corecție teren (ca SNAP Terrain-Correction)
    # - demInstance: COPERNICUS_30 → DEM 30m pentru ortorectificare
    request_body = {
        "input": {
            "bounds": {
                "bbox": [min_lon, min_lat, max_lon, max_lat],
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                }
            },
            "data": [{
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "timeRange": {
                        "from": date_from,
                        "to": date_to,
                    },
                    "acquisitionMode": "IW",
                    "polarization": "DV",
                    "resolution": "HIGH",
                },
                "processing": {
                    "backCoeff": "SIGMA0_ELLIPSOID",
                    "orthorectify": True,
                    "demInstance": "COPERNICUS_30",
                }
            }]
        },
        "output": {
            "width": width_px,
            "height": height_px,
            "responses": [{
                "identifier": "default",
                "format": {
                    "type": "image/tiff"
                }
            }]
        },
        "evalscript": EVALSCRIPT_S1_SIGMA0,
    }

    # ── 5. Trimite request ──
    logger.info(f"Sentinel Hub request: {width_px}×{height_px} px, {date_from[:10]}→{date_to[:10]}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            SH_PROCESS_URL,
            json=request_body,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "image/tiff",
            },
        )

        if response.status_code != 200:
            error_detail = response.text[:500]
            logger.error(f"Sentinel Hub error {response.status_code}: {error_detail}")
            raise Exception(f"Sentinel Hub API error {response.status_code}: {error_detail}")

    # ── 6. Salvează GeoTIFF ──
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Scriem răspunsul brut (deja e un GeoTIFF valid)
    output_file.write_bytes(response.content)

    # Verificare
    with rasterio.open(output_path) as src:
        logger.info(
            f"S1 descărcat: {src.count} benzi, {src.width}×{src.height}, "
            f"CRS={src.crs}, bounds={src.bounds}"
        )
        vv = src.read(1)
        vh = src.read(2)
        valid_pixels = np.sum(vv > 0)

    logger.info(
        f"Statistici S1: VV=[{vv[vv>0].min():.4f}, {vv[vv>0].max():.4f}], "
        f"VH=[{vh[vh>0].min():.4f}, {vh[vh>0].max():.4f}], "
        f"pixeli valizi: {valid_pixels:,}"
    )

    return {
        "path": str(output_file),
        "shape": (2, height_px, width_px),
        "date_range": f"{date_from[:10]} → {date_to[:10]}",
        "bbox": bbox,
        "valid_pixels": int(valid_pixels),
    }


def coregister_s1_to_s2(s1_path: str, s2_path: str, output_path: str) -> bool:
    """
    Co-registrează S1 pe grila exactă a S2.

    Reproiectează S1 la:
    - Același CRS ca S2
    - Aceeași rezoluție (transform)
    - Aceleași dimensiuni (width, height)

    Identic cu funcția coregister() din scriptul de pe HPC,
    dar adaptată pentru serviciul Copernicus.

    Args:
        s1_path: calea GeoTIFF S1 descărcat de la Sentinel Hub
        s2_path: calea GeoTIFF S2 (referință pentru grila spațială)
        output_path: calea GeoTIFF S1 co-registrat

    Returns:
        True dacă co-registration a reușit (suficienți pixeli valizi)
    """
    logger.info(f"Co-registration S1→S2: {s1_path} → {output_path}")

    with rasterio.open(s2_path) as s2:
        s2_profile = s2.profile.copy()
        s2_transform = s2.transform
        s2_width = s2.width
        s2_height = s2.height
        s2_crs = s2.crs

    # Profilul output: aceeași griă ca S2, dar 2 benzi (VV, VH) în float32
    out_profile = s2_profile.copy()
    out_profile.update(
        dtype="float32",
        count=2,
        compress="lzw",
        nodata=0,
    )

    with rasterio.open(s1_path) as s1:
        with rasterio.open(output_path, "w", **out_profile) as dst:
            for band_idx in [1, 2]:
                data_out = np.zeros((s2_height, s2_width), dtype=np.float32)
                reproject(
                    source=rasterio.band(s1, band_idx),
                    destination=data_out,
                    src_transform=s1.transform,
                    src_crs=s1.crs,
                    dst_transform=s2_transform,
                    dst_crs=s2_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=0,
                    dst_nodata=0,
                )
                dst.write(data_out, band_idx)

            dst.update_tags(1, name="Sigma0_VV")
            dst.update_tags(2, name="Sigma0_VH")

    # Verificare: suficienți pixeli valizi
    with rasterio.open(output_path) as check:
        valid = np.sum(check.read() > 0)
        logger.info(f"Co-registration: shape={check.shape}, pixeli valizi={valid:,}")
        return valid > 1000


def stack_s2_s1(s2_path: str, s1_coreg_path: str, output_path: str) -> str:
    """
    Combină S2 (4 benzi) + S1 co-registrat (2 benzi) → GeoTIFF 6 benzi.

    Ordinea benzilor (identică cu dataset-ul de antrenare):
        Band 1: B02 (Blue)
        Band 2: B03 (Green)
        Band 3: B04 (Red)
        Band 4: B08 (NIR)
        Band 5: VV  (Sigma0)
        Band 6: VH  (Sigma0)

    Acesta este input-ul direct pentru serviciul SR (/predict/).

    Args:
        s2_path: GeoTIFF S2 cu 4 benzi (B, G, R, NIR)
        s1_coreg_path: GeoTIFF S1 co-registrat cu 2 benzi (VV, VH)
        output_path: GeoTIFF output cu 6 benzi

    Returns:
        calea output-ului
    """
    logger.info(f"Stack S2+S1: {s2_path} + {s1_coreg_path} → {output_path}")

    with rasterio.open(s2_path) as s2:
        s2_data = s2.read()  # (4, H, W)
        profile = s2.profile.copy()

    with rasterio.open(s1_coreg_path) as s1:
        s1_data = s1.read()  # (2, H, W)

    # Verificare dimensiuni
    if s2_data.shape[1:] != s1_data.shape[1:]:
        raise ValueError(
            f"Dimensiuni incompatibile: S2={s2_data.shape}, S1={s1_data.shape}. "
            f"Co-registration a eșuat?"
        )

    # Stack: (4, H, W) + (2, H, W) → (6, H, W)
    stacked = np.concatenate([s2_data, s1_data], axis=0)

    profile.update(
        count=6,
        dtype="float32",
        compress="lzw",
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(stacked.astype(np.float32))
        dst.update_tags(1, name="B02_Blue")
        dst.update_tags(2, name="B03_Green")
        dst.update_tags(3, name="B04_Red")
        dst.update_tags(4, name="B08_NIR")
        dst.update_tags(5, name="Sigma0_VV")
        dst.update_tags(6, name="Sigma0_VH")

    logger.info(f"Stack complet: {stacked.shape} → {output_path}")
    return str(output_file)