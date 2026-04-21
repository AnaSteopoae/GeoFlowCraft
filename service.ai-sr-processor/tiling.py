"""
tiling.py — Inferență cu tiling pentru imagini mari
====================================================

Problema: DualBranchSARNet pe CPU consumă ~10-15× memorie față de input
la forward pass (activări intermediare din convoluții).
- 500×500 px → ~3 GB RAM → OK
- 2000×2000 px → ~50 GB RAM → OOM kill (exit code 137)

Soluția: taie imaginea în patch-uri mici, procesează fiecare separat,
apoi reasamblează. Overlap de 16px între patch-uri elimină artefactele
la margini (blending liniar în zona de suprapunere).

Funcționează transparent — endpoint-ul /predict/ apelează
`predict_with_tiling()` automat dacă imaginea depășește pragul.
"""

import logging
import numpy as np
import torch

logger = logging.getLogger("sr-service")

# Pragul peste care activăm tiling (în pixeli per dimensiune)
# Sub acest prag, forward pass direct (mai rapid, fără overhead)
TILE_THRESHOLD = 512

# Dimensiunea patch-ului (trebuie să fie multiplu de scale_factor=4)
TILE_SIZE = 256

# Overlap între patch-uri (în pixeli la rezoluția input)
# La output (×4), overlap-ul devine 64px — suficient pentru blending
OVERLAP = 16

# Scale factor (×4 upsampling)
SCALE = 4


def predict_with_tiling(model, s2_norm, s1_norm, device):
    """
    Inferență SR cu tiling automat.

    Dacă imaginea e mai mică decât TILE_THRESHOLD, rulează forward pass direct.
    Altfel, taie în patch-uri, procesează fiecare, și reasamblează.

    Args:
        model: DualBranchSARNet (eval mode, cu alpha deja aplicat)
        s2_norm: numpy array (4, H, W) — S2 normalizat [0, 1]
        s1_norm: numpy array (2, H, W) — S1 normalizat [0, 1]
        device: torch.device (cpu sau cuda)

    Returns:
        numpy array (4, H*SCALE, W*SCALE) — output SR
    """
    _, h, w = s2_norm.shape

    # Imagini mici → forward pass direct (fără overhead tiling)
    if h <= TILE_THRESHOLD and w <= TILE_THRESHOLD:
        logger.info(f"Direct inference: {w}×{h} (sub threshold {TILE_THRESHOLD})")
        s2_tensor = torch.from_numpy(s2_norm).unsqueeze(0).to(device)
        s1_tensor = torch.from_numpy(s1_norm).unsqueeze(0).to(device)

        with torch.no_grad():
            sr_tensor = model(s2_tensor, s1_tensor)

        return sr_tensor.squeeze(0).cpu().numpy()

    # ── Tiling ──
    logger.info(f"Tiling inference: {w}×{h} → patch-uri {TILE_SIZE}×{TILE_SIZE} cu overlap {OVERLAP}")

    out_h = h * SCALE
    out_w = w * SCALE
    out_overlap = OVERLAP * SCALE

    # Output acumulator + weight map (pentru blending)
    output = np.zeros((4, out_h, out_w), dtype=np.float32)
    weights = np.zeros((out_h, out_w), dtype=np.float32)

    # Calculează pozițiile patch-urilor
    step = TILE_SIZE - OVERLAP
    y_positions = list(range(0, h - TILE_SIZE + 1, step))
    x_positions = list(range(0, w - TILE_SIZE + 1, step))

    # Adaugă ultimul patch dacă nu acoperă exact
    if y_positions[-1] + TILE_SIZE < h:
        y_positions.append(h - TILE_SIZE)
    if x_positions[-1] + TILE_SIZE < w:
        x_positions.append(w - TILE_SIZE)

    total_patches = len(y_positions) * len(x_positions)
    logger.info(f"Total patch-uri: {total_patches} ({len(y_positions)} rows × {len(x_positions)} cols)")

    patch_idx = 0
    for y in y_positions:
        for x in x_positions:
            patch_idx += 1

            # Extrage patch-ul din input
            s2_patch = s2_norm[:, y:y+TILE_SIZE, x:x+TILE_SIZE].copy()
            s1_patch = s1_norm[:, y:y+TILE_SIZE, x:x+TILE_SIZE].copy()

            # Inferență pe patch
            s2_t = torch.from_numpy(s2_patch).unsqueeze(0).to(device)
            s1_t = torch.from_numpy(s1_patch).unsqueeze(0).to(device)

            with torch.no_grad():
                sr_patch = model(s2_t, s1_t)

            sr_np = sr_patch.squeeze(0).cpu().numpy()  # (4, TILE_SIZE*4, TILE_SIZE*4)

            # Eliberează memoria
            del s2_t, s1_t, sr_patch
            if device.type == 'cpu':
                pass  # gc handled automatically
            else:
                torch.cuda.empty_cache()

            # Coordonate în spațiul output (×4)
            oy = y * SCALE
            ox = x * SCALE
            oh = TILE_SIZE * SCALE
            ow = TILE_SIZE * SCALE

            # Creează weight mask — ramping la margini pentru blending
            weight = _create_weight_mask(oh, ow, out_overlap)

            # Acumulează (weighted addition)
            output[:, oy:oy+oh, ox:ox+ow] += sr_np * weight[np.newaxis, :, :]
            weights[oy:oy+oh, ox:ox+ow] += weight

            if patch_idx % 10 == 0 or patch_idx == total_patches:
                logger.info(f"  Patch {patch_idx}/{total_patches}")

    # Normalizează prin weight map (evită artefacte la overlap)
    weights = np.maximum(weights, 1e-8)  # evită împărțirea la zero
    output /= weights[np.newaxis, :, :]

    logger.info(f"Tiling complet: output {out_w}×{out_h}")
    return output


def _create_weight_mask(h, w, overlap):
    """
    Creează o mască de greutăți cu ramp-up la margini.

    Centrul patch-ului are weight=1, marginile (zona de overlap)
    au weight care crește liniar de la 0 la 1. La reasamblare,
    zona de overlap primește contribuții de la ambele patch-uri
    ponderate proporțional cu distanța de la margine.

    Rezultat: tranziție lină, fără linii vizibile.
    """
    mask = np.ones((h, w), dtype=np.float32)

    if overlap > 0:
        # Ramp pe marginea de sus
        for i in range(overlap):
            mask[i, :] *= i / overlap
        # Ramp pe marginea de jos
        for i in range(overlap):
            mask[h - 1 - i, :] *= i / overlap
        # Ramp pe marginea din stânga
        for j in range(overlap):
            mask[:, j] *= j / overlap
        # Ramp pe marginea din dreapta
        for j in range(overlap):
            mask[:, w - 1 - j] *= j / overlap

    return mask