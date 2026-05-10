# ============================================================
# GeoFlowCraft SR Service — Dockerfile (CPU)
# ============================================================
# Versiune CPU: imagine mică (~1.5 GB vs ~6 GB cu CUDA)
#
# Pentru GPU, înlocuiește:
#   FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime
#   și elimină --extra-index-url din requirements.txt
# ============================================================

# ── Bază: Python slim (fără CUDA) ──
FROM python:3.11-slim

# ── Dependențe sistem pentru rasterio (citire GeoTIFF) ──
# rasterio are nevoie de librării C (GDAL) care nu vin cu python:slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*
# curl e necesar pentru healthcheck-ul Docker
# rm -rf /var/lib/apt/lists/* reduce dimensiunea imaginii

WORKDIR /app

# ── Dependențe Python (layer separat pentru cache) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Codul aplicației ──
COPY . .

# ── Documentare port ──
EXPOSE 5555

# ── Pornire server ──
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5555"]