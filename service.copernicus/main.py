from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import os
import uuid
from dotenv import load_dotenv
from auth import CopernicusAuth
from stac_search import STACSearch
from downloader import Sentinel2Downloader
from s1_downloader import download_s1_processed, coregister_s1_to_s2, stack_s2_s1
from s2_preprocessor import preprocess_s2_safe

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get download directory from environment variable, default to "downloads"
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
logger.info(f"Configured download directory: {DOWNLOAD_DIR}")

# Sentinel Hub credentials (din .env)
client_id = os.getenv("client_id", "")
client_secret = os.getenv("client_secret", "")

app = FastAPI(title="Copernicus Sentinel-2 Download API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Modele Request/Response existente
# ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    geojson: Dict[str, Any]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_cloud_cover: Optional[float] = 20.0

class SearchResponse(BaseModel):
    status: str
    total_items: int
    items: List[Dict[str, Any]]

class DownloadRequest(BaseModel):
    items: List[Dict[str, Any]]

class DownloadResponse(BaseModel):
    status: str
    message: str
    task_id: str

# ──────────────────────────────────────────────
# Modele Request/Response noi — S1 + Stack
# ──────────────────────────────────────────────

class S1DownloadRequest(BaseModel):
    """
    Request pentru descărcarea S1 procesat via Sentinel Hub.
    
    bbox: coordonatele zonei de interes [min_lon, min_lat, max_lon, max_lat]
    target_date: data scenei S2 selectate (format: "2023-07-10")
    s2_path: calea către GeoTIFF-ul S2 descărcat (pentru co-registration)
    days_tolerance: fereastră temporală ±zile pentru căutare S1 (default ±6)
    resolution: rezoluție în metri (default 10, aceeași ca S2)
    """
    bbox: List[float]
    target_date: str
    s2_path: str
    days_tolerance: Optional[int] = 6
    resolution: Optional[int] = 10

class StackRequest(BaseModel):
    """
    Request pentru combinarea S2 (4 benzi) + S1 (2 benzi) → 6 benzi.
    
    s2_path: calea GeoTIFF S2 
    s1_path: calea GeoTIFF S1 co-registrat
    output_path: calea output (opțional, se generează automat)
    """
    s2_path: str
    s1_path: str
    output_path: Optional[str] = None

# ──────────────────────────────────────────────
# Task tracking
# ──────────────────────────────────────────────

download_tasks = {}      # Task-uri S2 (existent)
s1_tasks_status = {}     # Task-uri S1 (nou)

# ──────────────────────────────────────────────
# Endpoint-uri existente (neschimbate)
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "message": "Copernicus Sentinel-2 Download API",
        "endpoints": {
            "/search": "Search for Sentinel-2 products",
            "/download": "Download Sentinel-2 products for a given area",
            "/status/{task_id}": "Check download task status",
            "/download/s1": "Download processed Sentinel-1 via Sentinel Hub",
            "/status/s1/{task_id}": "Check S1 download task status",
            "/stack/s2-s1": "Stack S2 + S1 into 6-band GeoTIFF for SR",
        }
    }

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    try:
        request.geojson = normalize_geometry(request.geojson)

        end_date = request.end_date
        start_date = request.start_date

        if not start_date or not end_date:
            logger.info(f"Missing 'start_date' or 'end_date'. Setting default date range...")
            end_date = datetime.now().isoformat()
            start_date = (datetime.now() - timedelta(days=5)).isoformat()
            logger.info(f"start_date={start_date}")
            logger.info(f"end_date={end_date}")

        auth = CopernicusAuth()
        token = auth.get_access_token()

        searcher = STACSearch(token)
        items = searcher.search_sentinel2_odata(
            geometry=request.geojson,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=request.max_cloud_cover
        )

        return SearchResponse(
            status="success",
            total_items=len(items),
            items=items
        )

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/download", response_model=DownloadResponse)
async def download_products(request: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        download_tasks[task_id] = {"status": "pending", "message": "Task queued"}

        background_tasks.add_task(
            process_download,
            task_id,
            request.items
        )

        return DownloadResponse(
            status="accepted",
            message="Download task started",
            task_id=task_id
        )

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return download_tasks[task_id]

# ──────────────────────────────────────────────
# Endpoint-uri noi — S1 Download + Stack
# ──────────────────────────────────────────────

@app.post("/download/s1")
async def download_s1(request: S1DownloadRequest, background_tasks: BackgroundTasks):
    """
    Descarcă S1 procesat (σ⁰, ortorectificat) via Sentinel Hub
    și co-registrează pe grila S2.

    Înlocuiește complet pipeline-ul SNAP (15-20 min → ~30 sec).
    Rulează ca background task — frontend pollează /status/s1/{task_id}.
    """
    # Validare credențiale
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Sentinel Hub credentials not configured. "
                   "Set client_id and client_secret in .env"
        )

    # Validare bbox
    if len(request.bbox) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox must have 4 values: [min_lon, min_lat, max_lon, max_lat]"
        )

    task_id = f"s1_{uuid.uuid4().hex[:8]}"
    s1_tasks_status[task_id] = {
        "status": "started",
        "progress": "Inițializare descărcare S1...",
        "s1_raw_path": None,
        "s1_coreg_path": None,
        "error": None,
    }

    background_tasks.add_task(
        _s1_download_task,
        task_id=task_id,
        bbox=tuple(request.bbox),
        target_date=datetime.strptime(request.target_date, "%Y-%m-%d"),
        s2_path=request.s2_path,
        days_tolerance=request.days_tolerance,
        resolution=request.resolution,
    )

    return {"task_id": task_id, "status": "started"}


@app.get("/status/s1/{task_id}")
async def get_s1_status(task_id: str):
    """Verifică statusul descărcării S1."""
    if task_id not in s1_tasks_status:
        raise HTTPException(status_code=404, detail="S1 task not found")
    return s1_tasks_status[task_id]


@app.post("/stack/s2-s1")
async def stack_s2_s1_endpoint(request: StackRequest):
    """
    Combină S2 (4 benzi) + S1 co-registrat (2 benzi) → GeoTIFF 6 benzi.

    Output-ul este input-ul direct pentru serviciul SR (/predict/).
    Ordinea benzilor: B02, B03, B04, B08, VV, VH
    """
    output_path = request.output_path
    if not output_path:
        # Generează automat calea output
        base = request.s2_path.rsplit(".", 1)[0]  # elimină extensia
        output_path = f"{base}_s2_s1_stack.tif"

    try:
        result_path = stack_s2_s1(
            s2_path=request.s2_path,
            s1_coreg_path=request.s1_path,
            output_path=output_path,
        )
        return {
            "status": "completed",
            "stacked_path": result_path,
            "bands": [
                "B02_Blue", "B03_Green", "B04_Red", "B08_NIR",
                "Sigma0_VV", "Sigma0_VH"
            ],
        }
    except Exception as e:
        logger.error(f"Stack error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class S2PreprocessRequest(BaseModel):
    """Request pentru preprocesarea S2 .SAFE → GeoTIFF 4 benzi."""
    safe_path: str                      # Calea .SAFE.zip sau directorul .SAFE
    bbox: Optional[List[float]] = None  # [min_lon, min_lat, max_lon, max_lat] — cropează


@app.post("/preprocess/s2")
async def preprocess_s2(request: S2PreprocessRequest):
    """
    Extrage benzile B02, B03, B04, B08 (10m) dintr-un produs .SAFE Sentinel-2
    și le combină într-un GeoTIFF cu 4 benzi, cropat la bbox.
    """
    try:
        output_path = preprocess_s2_safe(
            request.safe_path,
            bbox=request.bbox
        )
        return {
            "status": "completed",
            "geotiff_path": output_path,
            "bands": ["B02_Blue", "B03_Green", "B04_Red", "B08_NIR"],
        }
    except Exception as e:
        logger.error(f"S2 preprocess error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────
# Background tasks
# ──────────────────────────────────────────────

async def _s1_download_task(
    task_id: str,
    bbox: tuple,
    target_date: datetime,
    s2_path: str,
    days_tolerance: int,
    resolution: int,
):
    """
    Background task care:
    1. Descarcă S1 de la Sentinel Hub (~30s)
    2. Co-registrează S1 pe grila S2 (<1s)
    """
    try:
        # ── Pas 1: Descărcare S1 ──
        s1_tasks_status[task_id]["progress"] = "Descărcare S1 de la Sentinel Hub..."

        date_str = target_date.strftime("%Y%m%d")
        s1_raw_path = os.path.join(
            DOWNLOAD_DIR, f"s1_raw_{date_str}_{task_id}.tif"
        )

        result = await download_s1_processed(
            bbox=bbox,
            target_date=target_date,
            output_path=s1_raw_path,
            client_id=client_id,
            client_secret=client_secret,
            days_tolerance=days_tolerance,
            resolution=resolution,
        )

        s1_tasks_status[task_id]["s1_raw_path"] = s1_raw_path
        s1_tasks_status[task_id]["progress"] = "Co-registration S1 pe grila S2..."

        # ── Pas 2: Co-registration ──
        s1_coreg_path = os.path.join(
            DOWNLOAD_DIR, f"s1_coreg_{date_str}_{task_id}.tif"
        )

        success = coregister_s1_to_s2(
            s1_path=s1_raw_path,
            s2_path=s2_path,
            output_path=s1_coreg_path,
        )

        if not success:
            raise Exception("Co-registration eșuată: prea puțini pixeli valizi S1")

        # ── Pas 3: Completat ──
        s1_tasks_status[task_id].update({
            "status": "completed",
            "progress": "S1 descărcat și co-registrat cu succes",
            "s1_coreg_path": s1_coreg_path,
            "metadata": result,
        })
        logger.info(f"S1 task {task_id} completat: {s1_coreg_path}")

    except Exception as e:
        logger.error(f"S1 task {task_id} eșuat: {str(e)}")
        s1_tasks_status[task_id].update({
            "status": "failed",
            "progress": "Descărcare eșuată",
            "error": str(e),
        })

async def process_download(task_id: str, items: List):
    try:
        download_tasks[task_id] = {"status": "processing", "message": "Authenticating..."}

        auth = CopernicusAuth()
        # token = auth.get_access_token()
        token = auth.get_download_token()

        download_tasks[task_id]["message"] = f"Starting download..."
        download_tasks[task_id]["total_items"] = len(items)
        download_tasks[task_id]["downloaded_items"] = 0

        downloader = Sentinel2Downloader(token, download_dir=DOWNLOAD_DIR)
        downloaded_files = []

        for idx, item in enumerate(items):
            download_tasks[task_id]["message"] = f"Downloading {idx + 1}/{len(items)}..."
            file_path = downloader.download_product(item)
            downloaded_files.append(file_path)
            download_tasks[task_id]["downloaded_items"] = idx + 1

        download_tasks[task_id] = {
            "status": "completed",
            "message": f"Successfully downloaded {len(downloaded_files)} products",
            "files": downloaded_files
        }

    except Exception as e:
        logger.error(f"Download task {task_id} failed: {str(e)}")
        download_tasks[task_id] = {
            "status": "failed",
            "message": f"Download failed: {str(e)}"
        }

# ──────────────────────────────────────────────
# Utilități (neschimbate)
# ──────────────────────────────────────────────

def normalize_geometry(geojson: dict) -> dict:
    print(geojson)
    print(geojson.get("type"))
    """Convert Polygon to MultiPolygon and handle FeatureCollection"""
    if geojson.get("type") == "Polygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [geojson["coordinates"]]
        }
    elif geojson.get("type") == "MultiPolygon":
        return geojson
    elif geojson.get("type") == "FeatureCollection":
        features = geojson.get("features", [])
        if features:
            geometry = features[0].get("geometry", {})
            if geometry.get("type") == "Polygon":
                return {
                    "type": "MultiPolygon",
                    "coordinates": [geometry["coordinates"]]
                }
            elif geometry.get("type") == "MultiPolygon":
                return geometry
            else:
                raise ValueError("FeatureCollection must contain a Polygon or MultiPolygon")
        else:
            raise ValueError("FeatureCollection must contain at least one feature")
    else:
        raise ValueError("GeoJSON must be a Polygon, MultiPolygon, or FeatureCollection")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)