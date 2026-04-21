"""
change_detection.py — Detecția schimbărilor pe imagini super-rezolvate
======================================================================

Implementare Change Vector Analysis (CVA) pe output-uri SR.

Concepte cheie:
    CVA tratează fiecare pixel ca un vector în spațiul spectral (B, G, R, NIR).
    Între două momente T1 și T2, vectorul de schimbare este:
        ΔX = X(T2) - X(T1)
    
    Magnitudinea: ||ΔX|| = √(ΔB² + ΔG² + ΔR² + ΔNIR²)
        → Cât de mult s-a schimbat pixelul (indiferent de direcție)
    
    ΔNDVI: NDVI(T2) - NDVI(T1)
        → Schimbare specifică vegetație
        → Negativ = pierdere vegetație, Pozitiv = creștere vegetație

    Binary Mask: magnitudine > threshold
        → Pixeli care s-au schimbat semnificativ

Referință: Malila, W.A. (1980). "Change Vector Analysis: An Approach for 
           Detecting Forest Changes with Landsat."

Integrare: apelat din endpoint-ul /change-detection din serviciul Copernicus
"""

import logging
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

logger = logging.getLogger("copernicus-service")


def compute_ndvi(data: np.ndarray) -> np.ndarray:
    """
    Calculează NDVI (Normalized Difference Vegetation Index).

    Formula: NDVI = (NIR - Red) / (NIR + Red)

    NDVI variază între -1 și +1:
        -1 → 0:   apă, sol gol, zăpadă, nori
        0 → 0.3:  sol gol, vegetație rară
        0.3 → 0.6: vegetație moderată (agricultură)
        0.6 → 1:  vegetație densă (pădure)

    Args:
        data: array (4, H, W) cu benzile B02, B03, B04, B08

    Returns:
        array (H, W) cu valori NDVI în [-1, 1]
    """
    red = data[2].astype(np.float64)   # B04 = Red
    nir = data[3].astype(np.float64)   # B08 = NIR

    # Evită împărțirea la zero
    denominator = nir + red
    ndvi = np.where(denominator > 0, (nir - red) / denominator, 0.0)

    return ndvi.astype(np.float32)


def compute_cva(sr_t1: np.ndarray, sr_t2: np.ndarray) -> dict:
    """
    Change Vector Analysis — calculează magnitudinea și direcția schimbării.

    Fiecare pixel e un punct în spațiul spectral 4D (B, G, R, NIR).
    Vectorul de schimbare: ΔX = X(T2) - X(T1)
    Magnitudinea: ||ΔX|| = √(ΔB² + ΔG² + ΔR² + ΔNIR²)

    Magnitudinea mare → pixel s-a schimbat mult (defrișare, construcție, inundație)
    Magnitudinea mică → pixel stabil (pădure, lac, clădire)

    Args:
        sr_t1: array (4, H, W) — imaginea SR la momentul T1
        sr_t2: array (4, H, W) — imaginea SR la momentul T2

    Returns:
        dict cu:
            magnitude: (H, W) — magnitudinea schimbării
            delta_bands: (4, H, W) — diferența per bandă
            ndvi_t1: (H, W) — NDVI la T1
            ndvi_t2: (H, W) — NDVI la T2
            delta_ndvi: (H, W) — NDVI(T2) - NDVI(T1)
    """
    # Diferența per bandă
    delta = sr_t2.astype(np.float64) - sr_t1.astype(np.float64)

    # Magnitudine CVA: norma euclidiană pe axa spectrală
    magnitude = np.sqrt(np.sum(delta ** 2, axis=0)).astype(np.float32)

    # NDVI diferențial
    ndvi_t1 = compute_ndvi(sr_t1)
    ndvi_t2 = compute_ndvi(sr_t2)
    delta_ndvi = ndvi_t2 - ndvi_t1

    return {
        "magnitude": magnitude,
        "delta_bands": delta.astype(np.float32),
        "ndvi_t1": ndvi_t1,
        "ndvi_t2": ndvi_t2,
        "delta_ndvi": delta_ndvi,
    }


def compute_change_mask(magnitude: np.ndarray, method: str = "otsu") -> np.ndarray:
    """
    Generează masca binară de schimbare dintr-o hartă de magnitudine.

    Două metode de thresholding:
        - "otsu": threshold automat bazat pe distribuția valorilor
          (separă automat în două clase: schimbat/neschimbat)
        - "percentile": top N% cei mai schimbați pixeli (default: top 5%)

    De ce threshold și nu magnitudine brută?
        Magnitudinea absolută depinde de calibrarea radiometrică, sezon, 
        unghiul solar. Thresholding-ul relativ (Otsu/percentile) e mai robust.

    Args:
        magnitude: array (H, W) — magnitudinea CVA
        method: "otsu" sau "percentile"

    Returns:
        array (H, W) binary — True = schimbare detectată
    """
    # Ignoră pixeli fără date (magnitudine = 0)
    valid = magnitude[magnitude > 0]

    if len(valid) == 0:
        return np.zeros_like(magnitude, dtype=bool)

    if method == "otsu":
        # Otsu's method: găsește threshold-ul care minimizează variația intra-clasă
        # Implementare simplificată fără sklearn/cv2
        hist, bin_edges = np.histogram(valid, bins=256)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        total = hist.sum()
        if total == 0:
            return np.zeros_like(magnitude, dtype=bool)

        best_threshold = 0
        best_variance = 0

        cum_sum = 0
        cum_weight = 0

        for i in range(len(hist)):
            cum_weight += hist[i]
            if cum_weight == 0:
                continue

            bg_weight = total - cum_weight
            if bg_weight == 0:
                break

            cum_sum += hist[i] * bin_centers[i]
            bg_mean = (valid.sum() - cum_sum) / bg_weight
            fg_mean = cum_sum / cum_weight

            variance = cum_weight * bg_weight * (fg_mean - bg_mean) ** 2

            if variance > best_variance:
                best_variance = variance
                best_threshold = bin_centers[i]

        threshold = best_threshold

    elif method == "percentile":
        # Top 5% cei mai schimbați pixeli
        threshold = np.percentile(valid, 95)

    else:
        raise ValueError(f"Metodă necunoscută: {method}. Folosește 'otsu' sau 'percentile'.")

    logger.info(f"Threshold ({method}): {threshold:.2f}")
    mask = magnitude > threshold

    return mask


def compute_statistics(
    magnitude: np.ndarray,
    change_mask: np.ndarray,
    delta_ndvi: np.ndarray,
    pixel_size_m: float = 2.5,
) -> dict:
    """
    Calculează statistici ale schimbărilor detectate.

    Args:
        magnitude: (H, W) — magnitudinea CVA
        change_mask: (H, W) — masca binară
        delta_ndvi: (H, W) — diferența NDVI
        pixel_size_m: dimensiunea pixelului în metri (2.5m pentru SR)

    Returns:
        dict cu statistici
    """
    total_pixels = magnitude.size
    valid_pixels = np.sum(magnitude > 0)
    changed_pixels = np.sum(change_mask)

    # Suprafața per pixel în hectare
    pixel_area_ha = (pixel_size_m * pixel_size_m) / 10000.0

    # Pixeli cu pierdere de vegetație (ΔNDVI < -0.1)
    veg_loss_mask = (delta_ndvi < -0.1) & change_mask
    veg_loss_pixels = np.sum(veg_loss_mask)

    # Pixeli cu creștere de vegetație (ΔNDVI > 0.1)
    veg_gain_mask = (delta_ndvi > 0.1) & change_mask
    veg_gain_pixels = np.sum(veg_gain_mask)

    stats = {
        "total_pixels": int(total_pixels),
        "valid_pixels": int(valid_pixels),
        "changed_pixels": int(changed_pixels),
        "change_percentage": round(float(changed_pixels / valid_pixels * 100), 2) if valid_pixels > 0 else 0,
        "total_area_ha": round(float(valid_pixels * pixel_area_ha), 2),
        "changed_area_ha": round(float(changed_pixels * pixel_area_ha), 2),
        "vegetation_loss_ha": round(float(veg_loss_pixels * pixel_area_ha), 2),
        "vegetation_gain_ha": round(float(veg_gain_pixels * pixel_area_ha), 2),
        "mean_magnitude": round(float(np.mean(magnitude[magnitude > 0])), 2) if valid_pixels > 0 else 0,
        "max_magnitude": round(float(np.max(magnitude)), 2),
        "mean_delta_ndvi": round(float(np.mean(delta_ndvi[change_mask])), 4) if changed_pixels > 0 else 0,
    }

    return stats


def run_change_detection(
    sr_t1_path: str,
    sr_t2_path: str,
    output_dir: str,
    threshold_method: str = "otsu",
    pixel_size_m: float = 2.5,
) -> dict:
    """
    Pipeline complet de change detection pe două imagini SR.

    Pași:
    1. Citește cele două imagini SR (GeoTIFF, 4 benzi fiecare)
    2. Verifică alinierea spațială (CRS, dimensiuni)
    3. Calculează CVA (magnitudine + diferențe spectrale)
    4. Calculează ΔNDVI
    5. Generează masca binară de schimbare
    6. Calculează statistici
    7. Salvează rezultatele ca GeoTIFF-uri

    Args:
        sr_t1_path: calea GeoTIFF SR pentru momentul T1 (mai vechi)
        sr_t2_path: calea GeoTIFF SR pentru momentul T2 (mai recent)
        output_dir: directorul unde se salvează rezultatele
        threshold_method: "otsu" sau "percentile"
        pixel_size_m: dimensiunea pixelului (default 2.5m pentru SR)

    Returns:
        dict cu: căile fișierelor output + statistici
    """
    logger.info(f"Change Detection: {sr_t1_path} vs {sr_t2_path}")

    # ── 1. Citește imaginile ──
    with rasterio.open(sr_t1_path) as src1:
        sr_t1 = src1.read().astype(np.float32)  # (4, H, W)
        profile = src1.profile.copy()
        t1_crs = src1.crs
        t1_transform = src1.transform
        t1_shape = (src1.height, src1.width)

    with rasterio.open(sr_t2_path) as src2:
        sr_t2 = src2.read().astype(np.float32)  # (4, H, W)
        t2_shape = (src2.height, src2.width)
        t2_crs = src2.crs

    # ── 2. Verifică alinierea ──
    if t1_shape != t2_shape:
        logger.warning(
            f"Dimensiuni diferite: T1={t1_shape}, T2={t2_shape}. "
            f"Reproiectez T2 pe grila T1..."
        )
        # Reproiectează T2 pe grila T1
        sr_t2_aligned = np.zeros_like(sr_t1)
        with rasterio.open(sr_t2_path) as src2:
            for band in range(4):
                reproject(
                    source=rasterio.band(src2, band + 1),
                    destination=sr_t2_aligned[band],
                    src_transform=src2.transform,
                    src_crs=src2.crs,
                    dst_transform=t1_transform,
                    dst_crs=t1_crs,
                    resampling=Resampling.bilinear,
                )
        sr_t2 = sr_t2_aligned

    logger.info(f"Dimensiuni: {sr_t1.shape[1]}×{sr_t1.shape[2]}, 4 benzi")

    # ── 3. CVA ──
    logger.info("Calculare CVA...")
    cva_result = compute_cva(sr_t1, sr_t2)

    # ── 4. Mască binară ──
    logger.info(f"Generare mască de schimbare (metoda: {threshold_method})...")
    change_mask = compute_change_mask(cva_result["magnitude"], method=threshold_method)

    # ── 5. Statistici ──
    stats = compute_statistics(
        cva_result["magnitude"],
        change_mask,
        cva_result["delta_ndvi"],
        pixel_size_m=pixel_size_m,
    )
    logger.info(f"Statistici: {stats['changed_area_ha']} ha schimbate ({stats['change_percentage']}%)")

    # ── 6. Salvează rezultatele ──
    os.makedirs(output_dir, exist_ok=True)

    # Profil comun pentru output-uri (1 bandă, float32)
    out_profile = profile.copy()
    out_profile.update(count=1, dtype="float32", compress="lzw")

    # 6a. Magnitudine CVA
    magnitude_path = os.path.join(output_dir, "cva_magnitude.tif")
    with rasterio.open(magnitude_path, "w", **out_profile) as dst:
        dst.write(cva_result["magnitude"], 1)
        dst.update_tags(1, name="CVA_Magnitude")

    # 6b. ΔNDVI
    delta_ndvi_path = os.path.join(output_dir, "delta_ndvi.tif")
    with rasterio.open(delta_ndvi_path, "w", **out_profile) as dst:
        dst.write(cva_result["delta_ndvi"], 1)
        dst.update_tags(1, name="Delta_NDVI")

    # 6c. Mască binară de schimbare
    mask_profile = out_profile.copy()
    mask_profile.update(dtype="uint8")
    mask_path = os.path.join(output_dir, "change_mask.tif")
    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(change_mask.astype(np.uint8), 1)
        dst.update_tags(1, name="Change_Mask")

    # 6d. NDVI T1 și T2 (pentru vizualizare)
    ndvi_t1_path = os.path.join(output_dir, "ndvi_t1.tif")
    with rasterio.open(ndvi_t1_path, "w", **out_profile) as dst:
        dst.write(cva_result["ndvi_t1"], 1)

    ndvi_t2_path = os.path.join(output_dir, "ndvi_t2.tif")
    with rasterio.open(ndvi_t2_path, "w", **out_profile) as dst:
        dst.write(cva_result["ndvi_t2"], 1)

    logger.info(f"Rezultate salvate în: {output_dir}")

    return {
        "magnitude_path": magnitude_path,
        "delta_ndvi_path": delta_ndvi_path,
        "change_mask_path": mask_path,
        "ndvi_t1_path": ndvi_t1_path,
        "ndvi_t2_path": ndvi_t2_path,
        "statistics": stats,
    }


# ══════════════════════════════════════════════════════════════
# ΔCHM — Change Detection pentru defrișări
# ══════════════════════════════════════════════════════════════

def run_chm_change_detection(
    chm_t1_path: str,
    chm_t2_path: str,
    output_dir: str,
    height_threshold: float = 5.0,
    pixel_size_m: float = 10.0,
) -> dict:
    """
    Detecție defrișări prin diferența de înălțime a canopiei (ΔCHM).

    De ce ΔCHM în loc de ΔNDVI pentru defrișări?
    ─────────────────────────────────────────────
    NDVI e un index spectral care variază cu:
    - Sezonul (frunze cad toamna → NDVI scade → detectat ca "defrișare")
    - Umiditate (secetă → NDVI scade temporar)
    - Unghiul solar (iarnă → reflexie diferită)
    
    CHM (Canopy Height Model) măsoară înălțimea fizică a copacilor:
    - Un copac de 20m rămâne 20m iarna, vara, în secetă
    - Dacă ΔCHM = -15m, copacul a fost tăiat — certitudine mare
    - Nu e afectat de sezonalitate
    
    Limitare CHM: rezoluție 10m (nu beneficiază de SR).
    Dar pentru defrișare contează mai mult robustețea decât rezoluția.

    Pași:
    1. Citește CHM T1 și CHM T2 (1 bandă, înălțime în metri)
    2. Calculează ΔCHM = CHM(T2) - CHM(T1)
       - Negativ = pierdere canopy (defrișare)
       - Pozitiv = creștere canopy (regenerare)
    3. Aplică threshold: |ΔCHM| > height_threshold
    4. Separare: defrișare (ΔCHM < -threshold) vs regenerare (ΔCHM > +threshold)
    5. Calculează statistici (hectare defrișate, pierdere maximă)

    Args:
        chm_t1_path: GeoTIFF CHM la momentul T1 (1 bandă, metri)
        chm_t2_path: GeoTIFF CHM la momentul T2 (1 bandă, metri)
        output_dir: directorul output
        height_threshold: pragul minim de schimbare în metri (default 5m)
                          Sub 5m poate fi variabilitate naturală sau eroare model
        pixel_size_m: dimensiunea pixelului (default 10m pentru CHM)

    Returns:
        dict cu căi output + statistici defrișare
    """
    logger.info(f"CHM Change Detection: {chm_t1_path} vs {chm_t2_path}")
    logger.info(f"  Threshold: {height_threshold}m")

    # ── 1. Citește CHM-urile ──
    with rasterio.open(chm_t1_path) as src1:
        chm_t1 = src1.read(1).astype(np.float32)  # (H, W)
        profile = src1.profile.copy()
        t1_transform = src1.transform
        t1_crs = src1.crs

    with rasterio.open(chm_t2_path) as src2:
        chm_t2 = src2.read(1).astype(np.float32)

    # ── 2. Aliniere (dacă dimensiuni diferite) ──
    if chm_t1.shape != chm_t2.shape:
        logger.warning(f"Dimensiuni diferite: T1={chm_t1.shape}, T2={chm_t2.shape}. Reproiectez...")
        chm_t2_aligned = np.zeros_like(chm_t1)
        with rasterio.open(chm_t2_path) as src2:
            reproject(
                source=rasterio.band(src2, 1),
                destination=chm_t2_aligned,
                src_transform=src2.transform,
                src_crs=src2.crs,
                dst_transform=t1_transform,
                dst_crs=t1_crs,
                resampling=Resampling.bilinear,
            )
        chm_t2 = chm_t2_aligned

    # ── 3. ΔCHM ──
    # Negativ = pierdere înălțime (defrișare)
    # Pozitiv = creștere înălțime (regenerare)
    delta_chm = chm_t2 - chm_t1

    # Mască pixeli valizi (ambele CHM-uri au date, înălțime > 0 la T1)
    valid_mask = (chm_t1 > 0) | (chm_t2 > 0)

    # ── 4. Clasificare schimbări ──
    # Defrișare: pierdere semnificativă de înălțime
    deforestation_mask = (delta_chm < -height_threshold) & valid_mask
    
    # Regenerare: creștere semnificativă
    regrowth_mask = (delta_chm > height_threshold) & valid_mask
    
    # Orice schimbare semnificativă
    change_mask = deforestation_mask | regrowth_mask

    # ── 5. Statistici ──
    pixel_area_ha = (pixel_size_m * pixel_size_m) / 10000.0
    
    valid_pixels = int(np.sum(valid_mask))
    deforestation_pixels = int(np.sum(deforestation_mask))
    regrowth_pixels = int(np.sum(regrowth_mask))

    # Pierdere maximă și medie (doar pe pixeli defrișați)
    deforested_values = delta_chm[deforestation_mask]
    max_height_loss = float(np.min(deforested_values)) if len(deforested_values) > 0 else 0
    mean_height_loss = float(np.mean(deforested_values)) if len(deforested_values) > 0 else 0

    stats = {
        "method": "delta_chm",
        "height_threshold_m": height_threshold,
        "pixel_size_m": pixel_size_m,
        "valid_pixels": valid_pixels,
        "total_forest_area_ha": round(float(np.sum(chm_t1 > 2) * pixel_area_ha), 2),
        "deforestation_pixels": deforestation_pixels,
        "deforestation_area_ha": round(float(deforestation_pixels * pixel_area_ha), 2),
        "regrowth_pixels": regrowth_pixels,
        "regrowth_area_ha": round(float(regrowth_pixels * pixel_area_ha), 2),
        "net_change_ha": round(float((regrowth_pixels - deforestation_pixels) * pixel_area_ha), 2),
        "max_height_loss_m": round(abs(max_height_loss), 1),
        "mean_height_loss_m": round(abs(mean_height_loss), 1),
        "chm_t1_mean_height": round(float(np.mean(chm_t1[chm_t1 > 2])), 1) if np.sum(chm_t1 > 2) > 0 else 0,
        "chm_t2_mean_height": round(float(np.mean(chm_t2[chm_t2 > 2])), 1) if np.sum(chm_t2 > 2) > 0 else 0,
    }

    logger.info(
        f"ΔCHM: defrișare={stats['deforestation_area_ha']} ha, "
        f"regenerare={stats['regrowth_area_ha']} ha, "
        f"pierdere max={stats['max_height_loss_m']}m"
    )

    # ── 6. Salvează rezultatele ──
    os.makedirs(output_dir, exist_ok=True)

    out_profile = profile.copy()
    out_profile.update(count=1, dtype="float32", compress="lzw")

    # ΔCHM continuu
    delta_chm_path = os.path.join(output_dir, "delta_chm.tif")
    with rasterio.open(delta_chm_path, "w", **out_profile) as dst:
        dst.write(delta_chm, 1)
        dst.update_tags(1, name="Delta_CHM_meters")

    # Mască defrișare (binară)
    mask_profile = out_profile.copy()
    mask_profile.update(dtype="uint8")
    
    deforestation_path = os.path.join(output_dir, "deforestation_mask.tif")
    with rasterio.open(deforestation_path, "w", **mask_profile) as dst:
        dst.write(deforestation_mask.astype(np.uint8), 1)
        dst.update_tags(1, name="Deforestation_Mask")

    # Mască regenerare
    regrowth_path = os.path.join(output_dir, "regrowth_mask.tif")
    with rasterio.open(regrowth_path, "w", **mask_profile) as dst:
        dst.write(regrowth_mask.astype(np.uint8), 1)
        dst.update_tags(1, name="Regrowth_Mask")

    # Clasificare: -1=defrișare, 0=stabil, +1=regenerare
    classification = np.zeros_like(delta_chm, dtype=np.int8)
    classification[deforestation_mask] = -1
    classification[regrowth_mask] = 1
    
    class_profile = out_profile.copy()
    class_profile.update(dtype="int8")
    classification_path = os.path.join(output_dir, "change_classification.tif")
    with rasterio.open(classification_path, "w", **class_profile) as dst:
        dst.write(classification, 1)
        dst.update_tags(1, name="Classification_-1deforest_0stable_1regrowth")

    logger.info(f"Rezultate ΔCHM salvate în: {output_dir}")

    return {
        "delta_chm_path": delta_chm_path,
        "deforestation_mask_path": deforestation_path,
        "regrowth_mask_path": regrowth_path,
        "classification_path": classification_path,
        "statistics": stats,
    }