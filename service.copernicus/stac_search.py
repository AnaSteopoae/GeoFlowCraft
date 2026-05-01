import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from shapely.geometry import shape, MultiPolygon
import json

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

class STACSearch:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.stac_url = "https://catalogue.dataspace.copernicus.eu/stac"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def search_sentinel2_odata(
        self,
        geometry: Dict[str, Any],
        start_date: str,
        end_date: str,
        max_cloud_cover: float = 20.0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search using OData API which has better Sentinel-2 support"""
        try:
            from shapely.geometry import shape
            geom = shape(geometry)
            bbox = list(geom.bounds)  # [minx, miny, maxx, maxy]
            
            # Format dates for OData
            if isinstance(start_date, str):
                start_date = start_date.replace('Z', '')
            if isinstance(end_date, str):
                end_date = end_date.replace('Z', '')
            
            # OData query for Sentinel-2
            odata_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
            
            # Build filter - search for Sentinel-2 products
            filter_query = (
                f"Collection/Name eq 'SENTINEL-2' and "
                f"ContentDate/Start ge {start_date} and "
                f"ContentDate/Start le {end_date} and "
                f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
                f"{bbox[0]} {bbox[1]},{bbox[2]} {bbox[1]},{bbox[2]} {bbox[3]},"
                f"{bbox[0]} {bbox[3]},{bbox[0]} {bbox[1]}))')"
            )
            
            if max_cloud_cover < 100:
                filter_query += f" and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {max_cloud_cover})"
            
            params = {
                "$filter": filter_query,
                "$top": limit,
                "$orderby": "ContentDate/Start desc"
            }
            
            logger.info(f"Searching OData API for Sentinel-2 with date range: {start_date} to {end_date}")
            
            response = requests.get(odata_url, params=params, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"OData search failed: {response.status_code} - {response.text}")
                # Fall back to STAC search
                return self.search_sentinel2_stac(geometry, start_date, end_date, max_cloud_cover, limit)
            
            response.raise_for_status()
            results = response.json()
            products = results.get("value", [])
            
            logger.info(f"Found {len(products)} Sentinel-2 products via OData")
            
            # Convert to our format (matching STAC format for frontend compatibility)
            filtered_items = []
            for product in products:
                # Extract cloud cover from attributes
                cloud_cover = 0
                for attr in product.get("Attributes", []):
                    if attr.get("Name") == "cloudCover":
                        cloud_cover = attr.get("Value", 0)
                        break
                 # Fallback: check in ContentDate or other fields
                if cloud_cover == 0:
                    # Try S3Path-based extraction or online attribute
                    online_attrs = product.get("Attributes", [])
                    for attr in online_attrs:
                        name = attr.get("Name", "")
                        if "cloud" in name.lower():
                            cloud_cover = attr.get("Value", 0)
                            logger.info(f"  Cloud cover found via '{name}': {cloud_cover}")
                            break
                
                # Extract bbox from Footprint geometry
                product_bbox = None
                footprint = product.get("Footprint")
                if footprint:
                    try:
                        from shapely import wkt
                        # OData format: geography'SRID=4326;POLYGON((...))'
                        wkt_str = footprint
                        if "geography'" in wkt_str:
                            wkt_str = wkt_str.replace("geography'", "").rstrip("'")
                        if wkt_str.startswith("SRID="):
                            wkt_str = wkt_str.split(";", 1)[1]
                        geom = wkt.loads(wkt_str)
                        product_bbox = list(geom.bounds)
                    except Exception as e:
                        logger.warning(f"Could not parse footprint: {e}")
                
                if not product_bbox:
                    # Fallback la bbox-ul zonei de search
                    product_bbox = bbox
                
                # Create a STAC-like structure for frontend compatibility
                stac_item = {
                    "id": product.get("Name"),
                    "properties": {
                        "datetime": product.get("ContentDate", {}).get("Start"),
                        "cloudCover": cloud_cover,
                        "platform": "sentinel-2"
                    },
                    "bbox": product_bbox,
                    "assets": {},
                    "original_odata": product
                }
                
                item_info = {
                    "id": product.get("Name"),
                    "datetime": product.get("ContentDate", {}).get("Start"),
                    "cloud_cover": cloud_cover,
                    "platform": "sentinel-2",
                    "bbox": product_bbox,
                    "assets": {},
                    "stac_item": stac_item  # STAC-compatible format
                }
                filtered_items.append(item_info)
                logger.info(f"✓ Found Sentinel-2: {item_info['id']}")
                logger.info(f"  Product attributes: {json.dumps(product.get('Attributes', [])[:3], default=str)}")

            # Deduplicare — păstrează o singură intrare per tile+dată
            # Prioritate: L2A > L1C (L2A e corectat atmosferic)
            seen = {}
            deduplicated = []
            for item in filtered_items:
                # Extrage tile ID și data din numele produsului
                # Ex: S2B_MSIL2A_20260427T092029_N0511_R093_T34TGR_20260427T112850
                parts = item["id"].split("_")
                if len(parts) >= 6:
                    tile_id = parts[5]  # T34TGR
                    date_str = parts[2][:8]  # 20260427
                    key = f"{tile_id}_{date_str}"
                    
                    if key not in seen:
                        seen[key] = item
                    else:
                        # Păstrează L2A peste L1C
                        existing = seen[key]
                        if "MSIL1C" in existing["id"] and "MSIL2A" in item["id"]:
                            seen[key] = item
                            logger.info(f"  Replaced L1C with L2A: {item['id']}")
                else:
                    seen[item["id"]] = item
            
            deduplicated = list(seen.values())
            logger.info(f"Deduplicated: {len(filtered_items)} → {len(deduplicated)} items")
            filtered_items = deduplicated
            
            return filtered_items
            
        except Exception as e:
            logger.error(f"OData search failed: {str(e)}")
            # Fall back to STAC
            return self.search_sentinel2_stac(geometry, start_date, end_date, max_cloud_cover, limit)
    
    def search_sentinel2_stac(
        self,
        geometry: Dict[str, Any],
        start_date: str,
        end_date: str,
        max_cloud_cover: float = 20.0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        
        try:
            if isinstance(start_date, datetime):
                start_date = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            elif isinstance(start_date, str) and not start_date.endswith('Z'):
                try:
                    dt = datetime.fromisoformat(start_date.replace('Z', ''))
                    start_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except:
                    start_date = start_date
            
            if isinstance(end_date, datetime):
                end_date = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            elif isinstance(end_date, str) and not end_date.endswith('Z'):
                try:
                    dt = datetime.fromisoformat(end_date.replace('Z', ''))
                    end_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except:
                    end_date = end_date
            
            # Convert MultiPolygon to bbox for now (Copernicus STAC may not support intersects)
            from shapely.geometry import shape
            geom = shape(geometry)
            bbox = list(geom.bounds)  # [minx, miny, maxx, maxy]
            
            # Collect all items with pagination
            all_items = []
            page = 1
            max_pages = 10  # Limit to 10 pages to avoid infinite loop
            
            search_body = {
                "datetime": f"{start_date}/{end_date}",
                "bbox": bbox,
                "limit": 100  # Items per page
            }
            
            logger.info(f"Searching STAC catalog with date range: {start_date} to {end_date}")
            logger.info(f"Will paginate through results to find Sentinel-2")
            
            while page <= max_pages:
                response = requests.post(
                    f"{self.stac_url}/search",
                    json=search_body,
                    headers=self.headers
                )
                
                if response.status_code != 200:
                    logger.error(f"STAC search response: {response.status_code} - {response.text}")
                    break
                
                response.raise_for_status()
                results = response.json()
                items = results.get("features", [])
                
                if not items:
                    logger.info(f"No more items at page {page}")
                    break
                
                all_items.extend(items)
                logger.info(f"Page {page}: Got {len(items)} items (total: {len(all_items)})")
                
                # Check for next page link
                links = results.get("links", [])
                next_link = None
                for link in links:
                    if link.get("rel") == "next":
                        next_link = link.get("href")
                        break
                
                if not next_link:
                    logger.info(f"No more pages available")
                    break
                
                # Update search body with next page token if available
                # Or break if we already have enough Sentinel-2 products
                sentinel2_count = sum(1 for item in all_items if item.get("id", "").startswith(("S2A_", "S2B_")))
                if sentinel2_count >= limit:
                    logger.info(f"Found enough Sentinel-2 products ({sentinel2_count}), stopping pagination")
                    break
                
                page += 1
            
            logger.info(f"Total items collected: {len(all_items)}")
            
            # Filter for Sentinel-2 only
            sentinel2_items = []
            for item in all_items:
                item_id = item.get("id", "")
                if item_id.startswith("S2A_") or item_id.startswith("S2B_"):
                    sentinel2_items.append(item)
                    logger.info(f"✓ Found Sentinel-2: {item_id}")
            
            logger.info(f"Filtered to {len(sentinel2_items)} Sentinel-2 products")
            
            # Apply cloud cover filter and build response
            filtered_items = []
            for item in sentinel2_items:
                cloud_cover = item["properties"].get("eo:cloud_cover", 0)
                
                if cloud_cover <= max_cloud_cover:
                    item_info = {
                        "id": item["id"],
                        "datetime": item["properties"].get("datetime"),
                        "cloud_cover": cloud_cover,
                        "platform": item["properties"].get("platform"),
                        "bbox": item.get("bbox"),
                        "assets": self._get_relevant_assets(item.get("assets", {})),
                        "stac_item": item
                    }
                    filtered_items.append(item_info)
            
            logger.info(f"Final result: {len(filtered_items)} Sentinel-2 products with cloud cover <= {max_cloud_cover}%")
            
            return filtered_items
            
        except requests.exceptions.RequestException as e:
            logger.error(f"STAC search failed: {str(e)}")
            raise Exception(f"Failed to search STAC catalog: {str(e)}")
    
    def _get_relevant_assets(self, assets: Dict[str, Any]) -> Dict[str, str]:
        relevant_assets = {}
        
        band_names = [
            "B01", "B02", "B03", "B04", "B05", "B06", 
            "B07", "B08", "B8A", "B09", "B11", "B12",
            "visual", "true_color", "SCL", "AOT", "WVP"
        ]
        
        for band in band_names:
            if band in assets:
                relevant_assets[band] = assets[band].get("href", "")
            elif band.lower() in assets:
                relevant_assets[band] = assets[band.lower()].get("href", "")
        
        for key, asset in assets.items():
            if "tif" in key.lower() or "geotiff" in key.lower():
                relevant_assets[key] = asset.get("href", "")
        
        return relevant_assets
    
    def get_product_metadata(self, product_id: str) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{self.stac_url}/collections/SENTINEL-2/items/{product_id}",
                headers=self.headers
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get product metadata: {str(e)}")
            raise Exception(f"Failed to get product metadata: {str(e)}")