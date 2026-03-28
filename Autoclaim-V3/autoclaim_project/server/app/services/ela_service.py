import io
import os
from typing import Dict, Any, Optional
try:
    from PIL import Image, ImageChops, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARNING] Pillow is not installed. ELA Analysis will be disabled.")

def ela_analysis(image_path: str, quality: int = 95) -> Dict[str, Any]:
    
    if not PIL_AVAILABLE:
        return {"success": False, "error": "Pillow not available"}
        
    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image not found: {image_path}"}
        
    try:
        original = Image.open(image_path).convert('RGB')
        
        buffer = io.BytesIO()
        original.save(buffer, 'JPEG', quality=quality)
        buffer.seek(0)
        resaved = Image.open(buffer)
        
        ela_image = ImageChops.difference(original, resaved)
        
        # Calculate manipulation score based on extrema
        extrema = ela_image.getextrema()
        max_diff = max([ex[1] for ex in extrema])
        
        # Calculate average difference to determine general noise vs localized spikes
        # A high max_diff with low average could indicate localized editing
        stat = ImageChops.difference(original, resaved).getextrema()
        
        # Simplify score: 0.0 to 1.0 where >0.8 might be suspicious
        # This is a basic proxy. In a real system, you'd analyze the histogram or regions.
        normalized_score = min(max_diff / 255.0, 1.0)
        
        # Generate the visual ELA image for reference if needed
        scale = 255.0 / max_diff if max_diff != 0 else 1
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
        
        # Save ELA output map for debugging/review
        ela_output_path = f"{image_path}_ela.jpg"
        ela_image.save(ela_output_path, "JPEG", quality=90)
        
        return {
            "success": True,
            "ela_score": normalized_score,
            "max_difference": max_diff,
            "is_suspicious": normalized_score > 0.8, # Simple threshold
            "ela_map_path": ela_output_path
        }
        
    except Exception as e:
        print(f"[ERROR] ELA Analysis failed for {image_path}: {e}")
        return {"success": False, "error": str(e)}

def analyze_claim_images_ela(image_paths: list[str]) -> Dict[str, Any]:
    """Analyze multiple images and return the highest risk result."""
    if not image_paths:
        return {"success": False, "error": "No images provided"}
        
    results = []
    highest_score = 0.0
    is_suspicious = False
    
    for path in image_paths:
        res = ela_analysis(path)
        if res.get("success"):
            results.append(res)
            score = res.get("ela_score", 0.0)
            if score > highest_score:
                highest_score = score
            if res.get("is_suspicious"):
                is_suspicious = True
                
    if not results:
        return {"success": False, "error": "All ELA analyses failed"}
        
    return {
        "success": True,
        "highest_ela_score": highest_score,
        "editing_detected": is_suspicious,
        "details": results
    }
