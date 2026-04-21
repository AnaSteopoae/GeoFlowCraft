"""
tiling.py — Inferență cu tiling pentru imagini mari
====================================================

v2: overlap 48px + blending cosinus (elimină artefactele vizibile de la v1)

Două schimbări față de v1:
1. OVERLAP: 16 → 48 (la output ×4 = 192px zonă de blending)
   → receptive field-ul modelului e acoperit complet
2. Blending cosinus în loc de liniar
   → tranziție mai lină (derivata e zero la capete, nu abruptă)
"""

import logging
import numpy as np
import torch

logger = logging.getLogger("sr-service")

TILE_THRESHOLD = 512
TILE_SIZE = 256
OVERLAP = 48
SCALE = 4


def predict_with_tiling(model, s2_norm, s1_norm, device):
    """
    Inferență SR cu tiling automat.
    Sub TILE_THRESHOLD → forward pass direct.
    Peste → tiling cu overlap și blending cosinus.
    """
    _, h, w = s2_norm.shape

    if h <= TILE_THRESHOLD and w <= TILE_THRESHOLD:
        logger.info(f"Direct inference: {w}×{h}")
        s2_tensor = torch.from_numpy(s2_norm).unsqueeze(0).to(device)
        s1_tensor = torch.from_numpy(s1_norm).unsqueeze(0).to(device)
        with torch.no_grad():
            sr_tensor = model(s2_tensor, s1_tensor)
        return sr_tensor.squeeze(0).cpu().numpy()

    logger.info(f"Tiling inference: {w}×{h} → patch-uri {TILE_SIZE}×{TILE_SIZE} cu overlap {OVERLAP}")

    out_h = h * SCALE
    out_w = w * SCALE
    out_tile = TILE_SIZE * SCALE
    out_overlap = OVERLAP * SCALE

    output = np.zeros((4, out_h, out_w), dtype=np.float64)
    weights = np.zeros((out_h, out_w), dtype=np.float64)

    weight_mask = _create_cosine_weight(out_tile, out_tile, out_overlap)

    step = TILE_SIZE - OVERLAP
    y_positions = _compute_positions(h, TILE_SIZE, step)
    x_positions = _compute_positions(w, TILE_SIZE, step)

    total = len(y_positions) * len(x_positions)
    logger.info(f"Total patch-uri: {total} ({len(y_positions)} rows × {len(x_positions)} cols)")

    idx = 0
    for y in y_positions:
        for x in x_positions:
            idx += 1

            s2_patch = s2_norm[:, y:y+TILE_SIZE, x:x+TILE_SIZE].copy()
            s1_patch = s1_norm[:, y:y+TILE_SIZE, x:x+TILE_SIZE].copy()

            s2_t = torch.from_numpy(s2_patch).unsqueeze(0).to(device)
            s1_t = torch.from_numpy(s1_patch).unsqueeze(0).to(device)
            with torch.no_grad():
                sr_patch = model(s2_t, s1_t)
            sr_np = sr_patch.squeeze(0).cpu().numpy()
            del s2_t, s1_t, sr_patch

            oy = y * SCALE
            ox = x * SCALE
            ph = sr_np.shape[1]
            pw = sr_np.shape[2]

            w_mask = weight_mask[:ph, :pw]

            output[:, oy:oy+ph, ox:ox+pw] += sr_np * w_mask[np.newaxis, :, :]
            weights[oy:oy+ph, ox:ox+pw] += w_mask

            if idx % 10 == 0 or idx == total:
                logger.info(f"  Patch {idx}/{total}")

    weights = np.maximum(weights, 1e-8)
    output /= weights[np.newaxis, :, :]

    logger.info(f"Tiling complet: output {out_w}×{out_h}")
    return output.astype(np.float32)


def _compute_positions(size, tile_size, step):
    positions = []
    pos = 0
    while pos + tile_size <= size:
        positions.append(pos)
        pos += step
    if not positions or positions[-1] + tile_size < size:
        positions.append(max(0, size - tile_size))
    return positions


def _create_cosine_weight(h, w, overlap):
    """
    Weight mask cu ramp cosinus la margini.

    Cosinus: weight(x) = 0.5 * (1 - cos(π * x / overlap))
    - La x=0: weight=0 (marginea patch-ului)
    - La x=overlap: weight=1 (centrul patch-ului)
    - Derivata la capete = 0 → tranziție lină, fără discontinuitate

    2D: produsul weight_y × weight_x
    """
    wy = np.ones(h, dtype=np.float64)
    if overlap > 0 and overlap < h // 2:
        for i in range(overlap):
            val = 0.5 * (1.0 - np.cos(np.pi * i / overlap))
            wy[i] = val
            wy[h - 1 - i] = val

    wx = np.ones(w, dtype=np.float64)
    if overlap > 0 and overlap < w // 2:
        for j in range(overlap):
            val = 0.5 * (1.0 - np.cos(np.pi * j / overlap))
            wx[j] = val
            wx[w - 1 - j] = val

    return np.outer(wy, wx)