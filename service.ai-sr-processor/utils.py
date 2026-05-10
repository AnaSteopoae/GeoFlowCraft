"""
GeoFlowCraft SR Service — Utilități
====================================
Funcții de normalizare și conversie pentru pipeline-ul de super-rezoluție.

IMPORTANT: Constantele de normalizare trebuie să fie IDENTICE cu cele
din dataset.py de pe HPC (/mnt/ssd/psteopoae/dataset.py).
Orice diferență produce artefacte în output.
"""

import io
import numpy as np
import rasterio

# ──────────────────────────────────────────────
# Constante de normalizare
# ──────────────────────────────────────────────
# Aceste valori TREBUIE să corespundă cu TripletDataset din dataset.py

# Sentinel-1 (SAR): conversia în dB, apoi min-max normalizare
S1_DB_MIN = -25.0   # limita inferioară dB (valori sub aceasta → 0)
S1_DB_MAX = 3.0     # limita superioară dB (valori peste aceasta → 1)

# Sentinel-2 (optic): reflectanță Level-2A, scalată ×10000
S2_SCALE_FACTOR = 10000.0


def normalize_s2(s2_raw: np.ndarray) -> np.ndarray:
    """
    Normalizează benzile Sentinel-2 (B, G, R, NIR).

    Sentinel-2 Level-2A stochează reflectanța × 10000.
    Exemplu: reflectanță 0.15 → valoare stocată 1500.

    Pași:
    1. Împarte la 10000 pentru a obține reflectanța reală [0, 1]
    2. Clip la [0, 1] — unele pixeli pot avea valori ușor negative
       (umbre, erori atmosferice) sau > 1 (nori, suprafețe foarte reflective)

    Args:
        s2_raw: array (4, H, W) cu valori brute S2

    Returns:
        array (4, H, W) normalizat în [0, 1]
    """
    s2_norm = s2_raw / S2_SCALE_FACTOR
    s2_norm = np.clip(s2_norm, 0.0, 1.0)
    return s2_norm


def normalize_s1(s1_raw: np.ndarray) -> np.ndarray:
    """
    Normalizează benzile Sentinel-1 SAR (VV, VH).

    Datele S1 GRD procesate cu SNAP sunt în putere liniară (σ⁰).
    Pipeline-ul de antrenare le convertește în dB, apoi aplică min-max.

    Pași:
    1. Clip valori ≤ 0 (imposibil fizic, dar posibil din erori de procesare)
    2. Conversie în dB: 10 × log₁₀(σ⁰)
       - Scala logaritmică comprimă rangul dinamic enorm al SAR
       - Exemplu: σ⁰ = 0.01 → -20 dB, σ⁰ = 1.0 → 0 dB
    3. Min-max normalizare cu S1_DB_MIN și S1_DB_MAX
       - Mapează [-25, 3] dB → [0, 1]
    4. Clip la [0, 1]

    Args:
        s1_raw: array (2, H, W) cu valori brute S1 (putere liniară)

    Returns:
        array (2, H, W) normalizat în [0, 1]
    """
    # Evită log(0) — înlocuiește valori ≤ 0 cu un minim mic
    s1_safe = np.clip(s1_raw, 1e-10, None)

    # Conversie putere liniară → dB
    s1_db = 10.0 * np.log10(s1_safe)

    # Min-max normalizare
    s1_norm = (s1_db - S1_DB_MIN) / (S1_DB_MAX - S1_DB_MIN)
    s1_norm = np.clip(s1_norm, 0.0, 1.0)

    return s1_norm


def denormalize_sr_output(sr_norm: np.ndarray) -> np.ndarray:
    """
    Denormalizează output-ul modelului SR înapoi la scara reflectanță.

    Modelul produce valori în [0, 1] (reflectanță normalizată).
    Le scalăm înapoi la × 10000 pentru compatibilitate cu ecosistemul
    Sentinel-2 (GeoServer, QGIS, alte tool-uri GIS).

    Args:
        sr_norm: array (4, H, W) cu valori în [0, 1]

    Returns:
        array (4, H, W) cu valori în [0, 10000]
    """
    sr_denorm = np.clip(sr_norm, 0.0, 1.0) * S2_SCALE_FACTOR
    return sr_denorm.astype(np.float32)


def tensor_to_geotiff_bytes(data: np.ndarray, profile: dict) -> bytes:
    """
    Scrie un array numpy ca GeoTIFF în memorie (fără disc).

    De ce în memorie (BytesIO) și nu pe disc?
    - Containerul e efemer — fișierele temporare se pierd la restart
    - Evităm I/O pe disc (mai rapid)
    - FastAPI poate streama direct din memorie

    Profilul conține metadatele geospațiale:
    - CRS (Coordinate Reference System, ex: EPSG:32635 pentru România)
    - Transform (Affine — leagă pixeli de coordonate)
    - Dimensiuni, tip date, compresie

    Args:
        data: array (bands, height, width)
        profile: dict rasterio cu metadate geospațiale

    Returns:
        bytes — conținut GeoTIFF complet
    """
    # Folosim compresie LZW — reduce dimensiunea ~50% fără pierdere
    profile.update({
        "driver": "GTiff",
        "compress": "lzw",
    })

    buffer = io.BytesIO()
    with rasterio.open(buffer, "w", **profile) as dst:
        dst.write(data)

    buffer.seek(0)
    return buffer.read()