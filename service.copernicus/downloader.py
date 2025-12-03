import requests
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Sentinel2Downloader:
    def __init__(self, access_token: str, download_dir: str = "downloads"):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}"
        }
        # Use configured download directory (can be shared volume in Docker)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Download directory: {self.download_dir.absolute()}")
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def download_product(
        self,
        item: Dict[str, Any]
    ) -> str:
        
        try:
            product_id = item["id"]
            # Use product_id directly as directory name (already has .SAFE extension)
            product_dir = self.download_dir / product_id
            product_dir.mkdir(exist_ok=True, parents=True)
            
            logger.info(f"Downloading full product '{product_id}' to '{product_dir}'")
            
            # First, get the UUID from the STAC item or search for it using OData API
            uuid = self._get_product_uuid(product_id)
            if not uuid:
                logger.error(f"Could not find UUID for product {product_id}")
                return ""
            
            # Download the full SAFE product using OData API
            output_file = product_dir / f"{product_id}.zip"
            success = self._download_full_product(uuid, output_file)
            
            if success and output_file.exists():
                logger.info(f"Successfully downloaded full product: {output_file.stat().st_size} bytes")
                # Return path to ZIP file - AI processor will handle extraction
                return str(output_file)
            else:
                logger.error(f"Failed to download full product {product_id}")
                return ""
                
        except Exception as e:
            logger.error(f"Failed to download product {product_id}: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")
        
    def _download_full_product(self, uuid: str, output_file: Path) -> bool:
        """Download the full SAFE product using OData API"""
        try:
            # Use the OData download URL
            download_url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({uuid})/$value"
            
            logger.info(f"Downloading full product from: {download_url}")
            logger.info(f"Output file: {output_file}")
            
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            logger.info(f"Starting download, expected size: {total_size/1024/1024:.1f} MB")
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (10 * 1024 * 1024) < 8192:  # Log every 10MB
                                logger.info(f"Download progress: {progress:.1f}% ({downloaded/1024/1024:.1f} MB)")
            
            logger.info(f"Download completed: {downloaded/1024/1024:.1f} MB")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download full product: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading product: {str(e)}")
            return False
        
    def _get_product_uuid(self, product_id: str) -> Optional[str]:
        """Get the UUID for a product from the OData API"""
        try:
            # Search for the product using OData API
            odata_url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter=Name eq '{product_id}'"
            
            logger.info(f"Searching for product UUID: {product_id}")
            response = requests.get(odata_url)
            response.raise_for_status()
            
            data = response.json()
            if data.get("value") and len(data["value"]) > 0:
                uuid = data["value"][0]["Id"]
                logger.info(f"Found UUID for {product_id}: {uuid}")
                return uuid
            else:
                logger.error(f"Product {product_id} not found in OData catalog")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get UUID for {product_id}: {str(e)}")
            return None