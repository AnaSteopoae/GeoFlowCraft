#!/bin/bash

set -e

echo "🛰️  Starting Copernicus Data Service..."
echo ""

cd service.copernicus

# Verifică dacă virtual environment există
if [ ! -d "copernicus_env" ]; then
    echo "⚠️  Virtual environment not found. Creating it..."
    python3 -m venv copernicus_env
    
    echo "📦 Installing dependencies..."
    source copernicus_env/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
fi

# Activează virtual environment
source copernicus_env/bin/activate

# Verifică dacă .env există și are DOWNLOAD_DIR
if ! grep -q "DOWNLOAD_DIR" .env 2>/dev/null; then
    echo "📝 Adding DOWNLOAD_DIR to .env..."
    echo "" >> .env
    echo "# Download directory (shared with AI service)" >> .env
    echo "DOWNLOAD_DIR=/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data" >> .env
fi

# Verifică dacă shared-data există
SHARED_DATA="/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data"
if [ ! -d "$SHARED_DATA" ]; then
    echo "📁 Creating shared-data directory..."
    mkdir -p "$SHARED_DATA"
fi

echo "✅ Configuration OK"
echo ""
echo "🚀 Starting Copernicus service on port 8000..."
echo ""
echo "📝 Service endpoints:"
echo "   - Base URL: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Search: POST http://localhost:8000/search/sentinel2"
echo "   - Download: POST http://localhost:8000/download"
echo ""
echo "📁 Download directory: $SHARED_DATA"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Pornește serviciul
uvicorn main:app --reload --host 0.0.0.0 --port 8000
