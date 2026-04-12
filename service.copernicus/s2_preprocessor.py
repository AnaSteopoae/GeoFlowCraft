"""
s2_preprocessor.py — Extragere benzi S2 din .SAFE → GeoTIFF 4 benzi
====================================================================

Sentinel-2 se descarcă ca .SAFE.zip care conține benzi separate (.jp2).
Serviciul SR are nevoie de un GeoTIFF cu 4 benzi (B02, B03, B04, B08)
la 10m rezoluție, cropat la zona de interes (bbox).

Acest modul:
1. Dezarhivează .SAFE.zip
2. Găsește benzile B02, B03, B04, B08 (10m)
3. Cropează la bbox-ul selectat de utilizator
4. Le combină într-un singur GeoTIFF 4 benzi
5. Returnează calea GeoTIFF-ului
"""

import logging
import zipfile
import os
from pathlib import Path
from glob import glob

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.transform import Affine
from rasterio.warp import transform_bounds

logger = logging.getLogger("copernicus-service")

BANDS_10M = ["B02", "B03", "B04", "B08"]


def find_band_file(safe_dir: str, band_name: str) -> str:
    """Găsește fișierul .jp2 pentru o bandă în structura SAFE (L2A sau L1C)."""
    # L2A: GRANULE/L2A_.../IMG_DATA/R10m/*_B02_10m.jp2
    pattern_l2a = os.path.join(safe_dir, "GRANULE", "*", "IMG_DATA", "R10m", f"*_{band_name}_10m.jp2")
    matches = glob(pattern_l2a)
    if matches:
        return matches[0]

    # L1C: GRANULE/L1C_.../IMG_DATA/*_B02.jp2
    pattern_l1c = os.path.join(safe_dir, "GRANULE", "*", "IMG_DATA", f"*_{band_name}.jp2")
    matches = glob(pattern_l1c)
    if matches:
        return matches[0]

    raise FileNotFoundError(f"Banda {band_name} nu a fost găsită în {safe_dir}")


def preprocess_s2_safe(safe_zip_path: str, output_path: str = None, bbox: list = None) -> str:
    """
    Transformă un .SAFE.zip Sentinel-2 într-un GeoTIFF cu 4 benzi, cropat la bbox.

    Args:
        safe_zip_path: calea către .SAFE.zip sau directorul .SAFE
        output_path: calea output GeoTIFF (opțional)
        bbox: [min_lon, min_lat, max_lon, max_lat] în WGS84 (opțional, cropează)

    Returns:
        calea către GeoTIFF-ul cu 4 benzi
    """
    safe_zip_path = str(safe_zip_path)
    logger.info(f"Preprocesare S2: {safe_zip_path}")
    if bbox:
        logger.info(f"  Crop bbox: {bbox}")

    # ── 1. Determină directorul SAFE ──
    if safe_zip_path.endswith(".zip"):
        extract_dir = os.path.dirname(safe_zip_path)
        safe_dir = None

        for item in os.listdir(extract_dir):
            if item.endswith(".SAFE") and os.path.isdir(os.path.join(extract_dir, item)):
                safe_dir = os.path.join(extract_dir, item)
                logger.info(f"SAFE deja extras: {safe_dir}")
                break

        if not safe_dir:
            logger.info(f"Dezarhivare: {safe_zip_path}")
            with zipfile.ZipFile(safe_zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            for item in os.listdir(extract_dir):
                if item.endswith(".SAFE") and os.path.isdir(os.path.join(extract_dir, item)):
                    safe_dir = os.path.join(extract_dir, item)
                    break

        if not safe_dir:
            raise FileNotFoundError(f"Nu am găsit directorul .SAFE după dezarhivare în {extract_dir}")

    elif os.path.isdir(safe_zip_path) and safe_zip_path.endswith(".SAFE"):
        safe_dir = safe_zip_path
    else:
        safe_dir = safe_zip_path
        if not os.path.exists(safe_dir):
            raise FileNotFoundError(f"Calea nu există: {safe_zip_path}")

    logger.info(f"Director SAFE: {safe_dir}")

    # ── 2. Găsește benzile ──
    band_files = {}
    for band in BANDS_10M:
        band_files[band] = find_band_file(safe_dir, band)
        logger.info(f"  {band}: {os.path.basename(band_files[band])}")

    # ── 3. Citește metadate de la prima bandă ──
    with rasterio.open(band_files[BANDS_10M[0]]) as ref:
        full_profile = ref.profile.copy()
        full_transform = ref.transform
        full_crs = ref.crs
        full_height = ref.height
        full_width = ref.width

    # ── 4. Calculează fereastra de crop (dacă bbox e dat) ──
    if bbox:
        # Transformă bbox din WGS84 în CRS-ul imaginii (ex: UTM)
        min_lon, min_lat, max_lon, max_lat = bbox
        
        if str(full_crs) != "EPSG:4326":
            # Reproiectează bbox-ul în CRS-ul S2
            crop_left, crop_bottom, crop_right, crop_top = transform_bounds(
                "EPSG:4326", full_crs, min_lon, min_lat, max_lon, max_lat
            )
        else:
            crop_left, crop_bottom, crop_right, crop_top = min_lon, min_lat, max_lon, max_lat

        # Calculează fereastra (rânduri/coloane) din transform
        window = from_bounds(
            crop_left, crop_bottom, crop_right, crop_top,
            transform=full_transform
        )
        
        # Rotunjește la pixeli întregi
        row_off = max(0, int(window.row_off))
        col_off = max(0, int(window.col_off))
        win_height = min(int(window.height) + 1, full_height - row_off)
        win_width = min(int(window.width) + 1, full_width - col_off)

        # Noul transform (originea se mută la colțul ferestrei)
        new_transform = Affine(
            full_transform.a, full_transform.b,
            full_transform.c + col_off * full_transform.a,
            full_transform.d, full_transform.e,
            full_transform.f + row_off * full_transform.e,
        )

        out_height = win_height
        out_width = win_width
        out_transform = new_transform

        logger.info(f"  Crop: {full_width}×{full_height} → {out_width}×{out_height}")
    else:
        row_off = 0
        col_off = 0
        out_height = full_height
        out_width = full_width
        out_transform = full_transform

    # ── 5. Generează calea output ──
    if not output_path:
        safe_name = os.path.basename(safe_dir).replace(".SAFE", "")
        suffix = "_cropped" if bbox else ""
        output_path = os.path.join(
            os.path.dirname(safe_dir),
            f"{safe_name}_4bands_10m{suffix}.tif"
        )

    # ── 6. Creează GeoTIFF cu 4 benzi (cropat) ──
    profile = full_profile.copy()
    profile.update({
        "driver": "GTiff",
        "count": 4,
        "height": out_height,
        "width": out_width,
        "transform": out_transform,
        "dtype": "float32",
        "compress": "lzw",
    })

    logger.info(f"Scriere GeoTIFF: {output_path} ({out_width}×{out_height}, 4 benzi)")

    with rasterio.open(output_path, "w", **profile) as dst:
        for i, band in enumerate(BANDS_10M, start=1):
            with rasterio.open(band_files[band]) as src:
                if bbox:
                    # Citește doar fereastra relevantă
                    win = rasterio.windows.Window(col_off, row_off, out_width, out_height)
                    data = src.read(1, window=win).astype(np.float32)
                else:
                    data = src.read(1).astype(np.float32)
                dst.write(data, i)
            dst.update_tags(i, name=band)

    with rasterio.open(output_path) as check:
        logger.info(
            f"S2 preprocesare completă: {check.count} benzi, "
            f"{check.width}×{check.height}, CRS={check.crs}"
        )

    return output_path