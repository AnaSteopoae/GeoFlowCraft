from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
from auth import CopernicusAuth
from stac_search import STACSearch
from downloader import Sentinel2Downloader

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

# Get download directory from environment variable, default to "downloads"
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
logger.info(f"Configured download directory: {DOWNLOAD_DIR}")

app = FastAPI(title = "Copernicus Sentinel-2 Download API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    geojson: Dict[str, Any]
    start_date: Optional[str] = None # (Optional) ISO date string
    end_date: Optional[str] = None # (Optional) ISO date string
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
    

download_tasks = {}

@app.get("/")
async def root():
    return {
        "message": "Copernicus Sentinel-2 Download API",
        "endpoints": {
            "/search": "Search for Sentinel-2 products",
            "/download": "Download Sentinel-2 products for a given area",
            "/status/{task_id}": "Check download task status"
        }
    }

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    try:
        # Normalize geometry to MultiPolygon format
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

def normalize_geometry(geojson: dict) -> dict:
    print(geojson)
    print(geojson.get("type"))
    """Convert Polygon to MultiPolygon and handle FeatureCollection"""
    if geojson.get("type") == "Polygon":
        # Convert Polygon to MultiPolygon
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

async def process_download(task_id: str, items: List):
    try:
        download_tasks[task_id] = {"status": "processing", "message": "Authenticating..."}
        
        auth = CopernicusAuth()
        token = auth.get_access_token()
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)