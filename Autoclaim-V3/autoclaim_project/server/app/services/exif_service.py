"""
EXIF Metadata Extraction Service.
Extracts timestamp and GPS location from image EXIF data.
Falls back to filename parsing when EXIF is not available.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import exifread

# Try to import geocoding
try:
    from geopy.geocoders import Nominatim
    GEOCODING_AVAILABLE = True
except ImportError:
    GEOCODING_AVAILABLE = False

# Initialize geocoder
geolocator = None


def init_geocoder():
    """Initialize the geocoder for reverse geocoding GPS coordinates."""
    global geolocator
    if GEOCODING_AVAILABLE and geolocator is None:
        try:
            geolocator = Nominatim(user_agent="autoclaim_app")
            print("[OK] Geocoder initialized")
        except Exception as e:
            print(f"[ERROR] Geocoder init failed: {e}")


def convert_gps_to_decimal(gps_coords, ref: str) -> Optional[float]:
    """Convert GPS coordinates from EXIF format to decimal degrees."""
    try:
        degrees = float(gps_coords[0])
        minutes = float(gps_coords[1])
        seconds = float(gps_coords[2])
        
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        if ref in ["S", "W"]:
            decimal = -decimal
        
        return round(decimal, 6)
    except:
        return None


def check_exif_anomalies(image_path: str) -> list[str]:
    """Check for missing EXIF data or AI generator software signatures."""
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
        
        red_flags = []
        
        # Real camera photos almost always have these
        if 'Image Make' not in tags:
            red_flags.append("NO_CAMERA_MAKE")
        if 'EXIF DateTimeOriginal' not in tags:
            red_flags.append("NO_CAPTURE_TIMESTAMP")
        
        # AI generators sometimes leave these
        software = str(tags.get('Image Software', ''))
        ai_keywords = ['stable diffusion', 'midjourney', 'dall-e', 'firefly', 'generative']
        if any(kw in software.lower() for kw in ai_keywords):
            red_flags.append(f"AI_SOFTWARE_TAG: {software}")
            
        return red_flags
    except Exception as e:
        print(f"[EXIF Anomalies] failed for {image_path}: {e}")
        return ["EXIF_READ_ERROR"]


def parse_filename_timestamp(filename: str) -> Dict[str, Any]:
    """
    Parse timestamp and camera info from common filename patterns.
    
    Supports:
    - Google Pixel: PXL_20250331_091108066.jpg
    - Samsung: 20250331_091108.jpg or IMG_20250331_091108.jpg
    - iPhone: IMG_1234.jpg or Photo_2025-03-31
    - WhatsApp: IMG-20250331-WA0001.jpg
    - Screenshot: Screenshot_20250331-091108.png
    
    Returns:
        dict with keys: timestamp, camera_type, filename_parsed
    """
    result = {
        "timestamp": None,
        "camera_type": None,
        "filename_parsed": False
    }
    
    if not filename:
        return result
    
    basename = os.path.basename(filename)
    
    patterns = [
        {"pattern": r"PXL_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "camera": "Google Pixel"},
        {"pattern": r"(?:IMG_)?(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "camera": "Samsung/Android"},
        {"pattern": r"IMG-(\d{4})(\d{2})(\d{2})-WA", "camera": "WhatsApp"},
        {"pattern": r"Screenshot_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", "camera": "Screenshot"},
        {"pattern": r"Photo_(\d{4})-(\d{2})-(\d{2})", "camera": "iPhone"},
        {"pattern": r"VID_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", "camera": "Video Screenshot"},
        {"pattern": r"(\d{4})(\d{2})(\d{2})", "camera": "Unknown Camera"}
    ]
    
    for p in patterns:
        match = re.search(p["pattern"], basename)
        if match:
            groups = match.groups()
            try:
                year = int(groups[0])
                month = int(groups[1])
                day = int(groups[2])
                
                if not (2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    continue
                
                hour = int(groups[3]) if len(groups) > 3 else 0
                minute = int(groups[4]) if len(groups) > 4 else 0
                second = int(groups[5]) if len(groups) > 5 else 0
                
                result["timestamp"] = datetime.strftime(datetime(year, month, day, hour, minute, second), "%Y-%m-%dT%H:%M:%S")
                result["camera_type"] = p["camera"]
                result["filename_parsed"] = True
                break
            except (ValueError, IndexError):
                continue
    
    return result


def extract_metadata(image_path: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract EXIF metadata from an image.
    Falls back to filename parsing if EXIF is not available.

    Args:
        image_path: Path to the stored (possibly renamed) image file.
        original_filename: Optional original filename before upload renaming.
                           Used in the fallback when the stored filename is a UUID.

    Returns:
        dict with: timestamp, gps_lat, gps_lon, location_name,
                   camera_make, camera_model, camera_type, filename_parsed, source
    """
    init_geocoder()
    
    result = {
        "timestamp": None,
        "gps_lat": None,
        "gps_lon": None,
        "location_name": None,
        "camera_make": None,
        "camera_model": None,
        "camera_type": None,
        "filename_parsed": False,
        "source": None,
        "anomalies": []
    }
    
    # Check for anomalies
    result["anomalies"] = check_exif_anomalies(image_path)
    
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    if tag == "DateTimeOriginal":
                        try:
                            result["timestamp"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S").isoformat()
                            result["source"] = "exif"
                        except:
                            pass
                    
                    elif tag == "Make":
                        result["camera_make"] = str(value).strip()
                    
                    elif tag == "Model":
                        result["camera_model"] = str(value).strip()
                            
                    elif tag == "GPSInfo":
                        gps_data = {}
                        for gps_tag_id, gps_value in value.items():
                            gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_data[gps_tag] = gps_value
                        
                        if "GPSLatitude" in gps_data and "GPSLongitude" in gps_data:
                            lat = convert_gps_to_decimal(
                                gps_data["GPSLatitude"],
                                gps_data.get("GPSLatitudeRef", "N")
                            )
                            lon = convert_gps_to_decimal(
                                gps_data["GPSLongitude"],
                                gps_data.get("GPSLongitudeRef", "E")
                            )
                            result["gps_lat"] = lat
                            result["gps_lon"] = lon
                            
                            if geolocator and lat and lon:
                                try:
                                    location = geolocator.reverse(f"{lat}, {lon}", timeout=5)
                                    if location:
                                        result["location_name"] = location.address
                                except Exception as e:
                                    print(f"Geocoding failed: {e}")
                
                if result["camera_make"]:
                    result["camera_type"] = f"{result['camera_make']} {result.get('camera_model', '')}".strip()
    
    except Exception as e:
        print(f"EXIF extraction failed for {image_path}: {e}")
    
    # Fallback to filename parsing.
    # Try the original filename first (before upload renaming), then the stored path.
    if result["timestamp"] is None:
        # Prefer original filename if provided (e.g., PXL_20250331_091108066.jpg)
        candidate_for_parsing = original_filename if original_filename else image_path
        filename_info = parse_filename_timestamp(candidate_for_parsing)

        # If original filename didn't yield a result, also try the stored path as a fallback
        if not filename_info["timestamp"] and original_filename:
            filename_info = parse_filename_timestamp(image_path)

        if filename_info["timestamp"]:
            result["timestamp"] = filename_info["timestamp"]
            result["camera_type"] = filename_info["camera_type"]
            result["filename_parsed"] = True
            result["source"] = "filename"
            if original_filename:
                print(f"[EXIF] Timestamp extracted from original filename: {os.path.basename(original_filename)}")

    return result
