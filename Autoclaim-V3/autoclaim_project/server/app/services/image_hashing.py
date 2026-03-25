import os
import imagehash
from PIL import Image
from typing import Dict, List, Optional

def compute_phash(image_path: str) -> Optional[str]:
   
    if not os.path.exists(image_path):
        return None
        
    try:
        with Image.open(image_path) as img:
            
            hash_val = imagehash.phash(img)
            return str(hash_val)
    except Exception as e:
        print(f"[Image Hashing] Failed to hash {image_path}: {e}")
        return None

def hash_claim_images(image_paths: List[str]) -> List[str]:
    
    hashes = []
    for path in image_paths:
        h = compute_phash(path)
        if h:
            hashes.append(h)
    return hashes

def calculate_hamming_distance(hash1_str: str, hash2_str: str) -> int:
    
    try:
        h1 = imagehash.hex_to_hash(hash1_str)
        h2 = imagehash.hex_to_hash(hash2_str)
        return h1 - h2
    except Exception as e:
        print(f"[Image Hashing] Error comparing hashes {hash1_str} and {hash2_str}: {e}")
        # Return a large distance on failure
        return 999
