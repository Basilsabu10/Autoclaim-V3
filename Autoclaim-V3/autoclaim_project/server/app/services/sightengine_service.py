import os
import requests
from typing import List, Dict, Any
from app.core.config import settings

def _query_sightengine(image_path: str) -> float:
    """
    POST an image to the Sightengine AI-generation detection endpoint.
    Retrieves the likelihood (0.0 - 1.0) that the image is AI-generated.
    Returns 0.0 on error or failure.
    """
    if not settings.SIGHTENGINE_API_USER or not settings.SIGHTENGINE_API_SECRET:
        print("[Sightengine] Credentials not found, skipping AI detection.")
        return 0.0

    url = "https://api.sightengine.com/1.0/check.json"
    
    # Send image via multipart/form-data
    try:
        with open(image_path, "rb") as image_file:
            files = {"media": image_file}
            data = {
                "models": "genai",
                "api_user": settings.SIGHTENGINE_API_USER,
                "api_secret": settings.SIGHTENGINE_API_SECRET
            }
            
            response = requests.post(url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    genai_data = result.get("type", {})
                    # Sightengine returns 'ai_generated' probability
                    ai_score = genai_data.get("ai_generated", 0.0)
                    return float(ai_score)
                else:
                    error_msg = result.get("error", {}).get("message", "Unknown error")
                    print(f"[Sightengine] API returned error: {error_msg}")
            else:
                print(f"[Sightengine] HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[Sightengine] Exception occurred during detection request: {e}")

    return 0.0

def analyze_claim_images_sightengine(image_paths: List[str]) -> Dict[str, Any]:
    """
    Run Sightengine AI generation detection across all submitted images.
    Returns the maximum AI-generated probability across the batch.
    """
    success_count = 0
    max_score = 0.0
    
    if not settings.SIGHTENGINE_API_USER or not settings.SIGHTENGINE_API_SECRET:
        print("[Sightengine] Skipping AI check (no credentials).")
        return {
            "success": False,
            "ai_generated": False,
            "max_ai_score": 0.0,
            "message": "SIGHTENGINE_API_USER or SIGHTENGINE_API_SECRET not set"
        }

    for path in image_paths:
        if not os.path.exists(path):
            continue
            
        try:
            score = _query_sightengine(path)
            # Sightengine documentation says it returns a score between 0 and 1.
            max_score = max(max_score, score)
            success_count += 1
            print(f"[Sightengine] AI score: {score:.4f} for {os.path.basename(path)}")
        except Exception as e:
            print(f"[Sightengine] Validation failed for {os.path.basename(path)}: {e}")

    # If all calls failed (or no images to process), return fail state
    if success_count == 0:
        return {
            "success": False,
            "ai_generated": False,
            "max_ai_score": 0.0,
            "message": "Detection calls failed for all images"
        }

    # If the maximum score found crosses 0.5, classify as AI-generated
    is_ai_gen = max_score > 0.5

    return {
        "success": True,
        "ai_generated": is_ai_gen,
        "max_ai_score": max_score,
        "message": f"Sightengine completed cleanly. AI= {'Yes' if is_ai_gen else 'No'}"
    }
