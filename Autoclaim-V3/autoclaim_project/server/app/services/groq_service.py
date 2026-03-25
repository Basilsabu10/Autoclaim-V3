

import os
import json
import base64
from typing import Dict, Any, List, Optional
from groq import Groq
from app.core.config import settings

# Initialize Groq client
groq_client = None
GROQ_AVAILABLE = False

def init_groq() -> bool:
    """Initialize Groq client."""
    global groq_client, GROQ_AVAILABLE
    
    if not settings.GROQ_API_KEY:
        print("[WARNING] GROQ_API_KEY not set")
        return False
    
    try:
        groq_client = Groq(api_key=settings.GROQ_API_KEY)
        GROQ_AVAILABLE = True
        print("[OK] Groq client initialized")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to initialize Groq: {e}")
        return False


def encode_image_base64(image_path: str) -> Optional[str]:
    """Encode image to base64 with optimal compression."""
    try:
        from PIL import Image
        import io
        
        img = Image.open(image_path)
        
        # Convert to RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # Resize (1920x1080 to preserve fine details like watermarks)
        max_size = (1920, 1080)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Compress to JPEG quality 90 to prevent compression artifacts destroying watermarks
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90, optimize=True)
        buffer.seek(0)
        
        return base64.b64encode(buffer.read()).decode('utf-8')
        
    except Exception as e:
        print(f"[ERROR] Failed to encode image: {e}")
        return None


def build_extraction_prompt(description: str, policy_data: Optional[Dict] = None) -> str:
    """
    Lean prompt for pure data extraction.
    No fluff, no judgment, just facts.
    """
    
    policy_info = ""
    if policy_data:
        policy_info = f"\nPolicy: {policy_data.get('vehicle_make')} {policy_data.get('vehicle_model')} {policy_data.get('vehicle_year')}, Color: {policy_data.get('vehicle_color')}, Plate: {policy_data.get('vehicle_registration')}"
    
    prompt = f"""You are an AI forensics expert. Your task is to detect image integrity issues and verify vehicle identity.
Do not extract damage or license plates (handled by YOLO).

Return data strictly in the JSON schema below. 
If a field cannot be determined, return null or false.

Claim: "{description}"{policy_info}

Return ONLY this JSON:

{{
  "identity": {{
    "vehicle_make": "brand name string or null",
    "vehicle_model": "model name string or null",
    "vehicle_color": "primary color string or null",
    "identification_confidence": "float between 0.0 and 1.0"
  }},
  "forensics": {{
    "is_screen_recapture": true/false,
    "has_ui_elements": true/false,
    "has_watermarks": true/false,
    "image_quality": "high | medium | low",
    "is_blurry": true/false,
    "multiple_light_sources": true/false,
    "shadows_inconsistent": true/false,
    "airbags_deployed": true/false,
    "fluid_leaks_visible": true/false
  }},
  "fraud_analysis": {{
    "fraud_detected": true/false,
    "fraud_score": 0.0 to 1.0,
    "fraud_indicators": ["list", "of", "red", "flags"],
    "reasoning": "textual explanation of forensics findings"
  }}
}}

CRITICAL RULES:
- Respond with ONLY valid JSON.
- No damage assessment.
- Focus on forgery, recapture, and vehicle identity (make, model, color).
- For airbags_deployed: true ONLY if you can see deployed airbag fabric/material in the image.
- For fluid_leaks_visible: true ONLY if you can see liquid pooling, drips, or stains under/around the vehicle."""
    
    return prompt


def extract_vehicle_data(
    image_paths: List[str], 
    description: str = "",
    policy_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Fast data extraction from vehicle damage images.
    Returns facts only - no decisions.
    """
    if not groq_client:
        init_groq()
    
    if not groq_client:
        return {
            "error": "Groq client not initialized",
            "success": False
        }
    
    # Build lean prompt
    prompt = build_extraction_prompt(description, policy_data)
    
    # Prepare all images (no arbitrary limits, ensuring no watermarks/details are skipped)
    image_contents = []
    for path in image_paths:
        if not os.path.exists(path):
            continue
        
        base64_image = encode_image_base64(path)
        if base64_image:
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
    
    if not image_contents:
        return {
            "error": "No valid images provided",
            "success": False
        }
    
    # Build message
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            *image_contents
        ]
    }]
    
    try:
        print(f"[INFO] Extracting data with Groq ({len(image_contents)} images)...")
        
        # Call Groq API - use Llama 4 Scout (supports vision)
        model = "meta-llama/llama-4-scout-17b-16e-instruct"
        
        response = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,  # Zero temperature for deterministic facts
            max_tokens=1500,   # Much less than before
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        
        # Parse JSON
        try:
            data = json.loads(response_text)
            data["success"] = True
            data["provider"] = "groq"
            data["model"] = model
            
            print(f"[OK] Data extracted successfully")
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse failed: {e}")
            print(f"Response: {response_text[:500]}")
            return {
                "error": "Invalid JSON response",
                "raw_response": response_text,
                "success": False
            }
    
    except Exception as e:
        print(f"[ERROR] Groq API call failed: {e}")
        # Fallback to configured model
        if "llama-3.2-11b-vision-preview" in str(e):
            print("[INFO] Falling back to configured model...")
            try:
                response = groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1500,
                    response_format={"type": "json_object"}
                )
                data = json.loads(response.choices[0].message.content)
                data["success"] = True
                data["provider"] = "groq"
                data["model"] = settings.GROQ_MODEL
                return data
            except Exception as e2:
                print(f"[ERROR] Fallback also failed: {e2}")
                return {"error": str(e2), "success": False}
        
        return {
            "error": str(e),
            "success": False
        }


# Alias for backward compatibility
analyze_damage = extract_vehicle_data

# Initialize on module load
init_groq()