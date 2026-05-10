from fastapi import FastAPI, Form, Query
from fastapi.responses import JSONResponse
from predictor import run_inference
import sys
import logging
import os
from pydantic import BaseModel
from typing import List


# Configure logging corect pentru docker + uvicorn
logger = logging.getLogger("uvicorn")
logger.handlers.clear()  # Curăță handler-ele implicite

# Creează un handler care scrie în stdout (captat de docker logs)
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

# Get input data directory from environment variable, default to "test_data"
INPUT_DATA_DIR = os.getenv("INPUT_DATA_DIR", "test_data")
logger.info(f"Input data directory: {INPUT_DATA_DIR}")

app = FastAPI()

# Schema de request JSON
class PredictionRequest(BaseModel):
    image_filenames: List[str]

@app.get("/health")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "model": "Canopy Height Processor",
        "version": "1.0.0"
    })

@app.post("/predict/")
async def predict(request: PredictionRequest):
    # Rulează predicția (aceeași logică ca scriptul tău)
    try:
        results = []
        for image_filename in request.image_filenames:
            # Use configurable input directory
            input_path = os.path.join(INPUT_DATA_DIR, image_filename)
            logger.info(f"Received image path: {input_path}")  
            result_path = run_inference(image_path=input_path)
            logger.info(f"Returning result path: {result_path}")
            results.append(result_path)
        return JSONResponse(content={"message": "Results", "paths" : results})
    except Exception as e:
        logger.exception("Error during prediction")
        return JSONResponse(status_code=500, content={"message": str(e)})
    