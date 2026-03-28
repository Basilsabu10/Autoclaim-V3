

import os
import numpy as np
from PIL import Image
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.core.config import settings

# Try to import dependencies
try:
    from ultralytics import YOLO
    import torch
    YOLO_SEG_AVAILABLE = True
except ImportError:
    YOLO_SEG_AVAILABLE = False
    print("[WARNING] ultralytics not installed. Run: pip install ultralytics torch")

# CLASS DEFINITIONS

# Damage classes (0–4)
DAMAGE_CLASSES = {0: "Broken part", 1: "Scratch", 2: "Cracked", 3: "Dent", 4: "Missing part"}

# Part classes (5–17)
PART_CLASSES = {
    5: "Trunk", 6: "Front-door", 7: "Grille", 8: "Windshield",
    9: "Back-door", 10: "Headlight", 11: "Hood", 12: "Fender",
    13: "Tail-light", 14: "License-plate", 15: "Front-bumper",
    16: "Back-bumper", 17: "Mirror",
}

# Map YOLO class names → canonical panel keys used by repair_estimator_service
PART_TO_PANEL_KEY = {
    "Trunk": "trunk",
    "Front-door": "door_fl",
    "Grille": "grille",
    "Windshield": "windshield",
    "Back-door": "door_rl",
    "Headlight": "headlight_l",
    "Hood": "hood",
    "Fender": "fender_fl",
    "Tail-light": "taillight_l",
    "License-plate": "license_plate",
    "Front-bumper": "front_bumper",
    "Back-bumper": "rear_bumper",
    "Mirror": "side_mirror_l",
}

# Map damage class names → damage_type strings expected downstream
DAMAGE_TYPE_MAP = {
    "Broken part": "crush",
    "Scratch": "scratch",
    "Cracked": "crack",
    "Dent": "dent",
    "Missing part": "missing",
}

# Severity weights per damage type (higher = more severe)
DAMAGE_SEVERITY_WEIGHT = {
    "Broken part": 0.9,
    "Scratch": 0.3,
    "Cracked": 0.6,
    "Dent": 0.5,
    "Missing part": 0.8,
}


# GLOBAL MODEL

seg_model = None
SEG_MODEL_INITIALIZED = False


def check_gpu_available() -> Dict[str, Any]:
    
    if not YOLO_SEG_AVAILABLE:
        return {"available": False, "reason": "ultralytics not installed"}
    try:
        if torch.cuda.is_available():
            return {
                "available": True,
                "device": torch.cuda.get_device_name(0),
                "memory_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
                "cuda_version": torch.version.cuda,
            }
        return {"available": False, "reason": "CUDA not available", "device": "cpu"}
    except Exception as e:
        return {"available": False, "reason": str(e), "device": "cpu"}


def init_seg_model(model_path: str = None) -> bool:
   
    global seg_model, SEG_MODEL_INITIALIZED

    if not YOLO_SEG_AVAILABLE:
        print("[ERROR] Cannot init YOLO seg — ultralytics not installed")
        return False

    if SEG_MODEL_INITIALIZED and seg_model is not None:
        return True

    if model_path is None:
        model_path = settings.YOLO_SEG_MODEL_PATH

    if not os.path.exists(model_path):
        print(f"[ERROR] YOLO seg model not found: {model_path}")
        return False

    try:
        gpu_info = check_gpu_available()
        print(f"[INFO] GPU Status: {gpu_info}")

        seg_model = YOLO(model_path)
        print(f"[OK] YOLO11m-seg model loaded: {model_path}")

        if gpu_info["available"]:
            seg_model.to("cuda")
            print(f"[OK] Model on GPU: {gpu_info['device']}")
        else:
            print("[INFO] Model on CPU")

        SEG_MODEL_INITIALIZED = True
        return True
    except Exception as e:
        print(f"[ERROR] YOLO seg init failed: {e}")
        import traceback
        traceback.print_exc()
        return False



INFER_IMGSZ      = 800   # both phases use the same downscaled size
PARTS_CONF       = 0.10  # lower threshold to catch weaker part activations
DAMAGE_CONF      = 0.10  # lowered: catches average damage confidences (dents, scratches)
BBOX_IOU_MIN     = 0.25  # minimum overlap ratio to call a match
NMS_IOU          = 0.45  # NMS IOU threshold from user script


def detect_damage_and_parts(
    image_path: str, conf_threshold: float = 0.25
) -> Dict[str, Any]:
    
    if not YOLO_SEG_AVAILABLE:
        return {"success": False, "error": "ultralytics not installed"}
    if seg_model is None:
        return {"success": False, "error": "Model not initialized — call init_seg_model()"}
    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image not found: {image_path}"}

    try:
        # 1. Resize image manually to 800px (LANCZOS) as per user strategy
        # This often preserves details better than YOLO's internal resize.
        with Image.open(image_path) as im:
            orig_w, orig_h = im.size
            if max(orig_w, orig_h) <= INFER_IMGSZ:
                processed_path = image_path
            else:
                scale = INFER_IMGSZ / max(orig_w, orig_h)
                new_w, new_h = int(orig_w * scale), int(orig_h * scale)
                # Create a temporary file for the resized image
                fd, processed_path = tempfile.mkstemp(suffix=".jpg")
                os.close(fd)
                resized_im = im.resize((new_w, new_h), Image.LANCZOS)
                if resized_im.mode in ("RGBA", "P"):
                    resized_im = resized_im.convert("RGB")
                resized_im.save(processed_path, quality=95)

        
        # Phase 1 — PART DETECTION  (conf=0.10, imgsz=800)                   #
        
        part_results = seg_model(
            processed_path,
            conf=PARTS_CONF,
            iou=NMS_IOU,
            imgsz=INFER_IMGSZ,
            verbose=False,
        )

        part_dets:  List[Dict] = []
        license_plate_bbox = None
        orig_shape = (orig_h, orig_w)

        for result in part_results:
            
            boxes = result.boxes
            masks = result.masks
            if boxes is None or len(boxes) == 0:
                continue

            # Scale factors
            sx = orig_w / result.orig_shape[1]
            sy = orig_h / result.orig_shape[0]

            for i, box in enumerate(boxes):
                cls_id = int(box.cls[0])
                if cls_id not in PART_CLASSES:
                    continue  # this pass: parts only

                cls_name   = result.names.get(cls_id, f"class_{cls_id}")
                confidence = float(box.conf[0])
                
                # Scale bbox back to original image coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bbox = [x1 * sx, y1 * sy, x2 * sx, y2 * sy]

                area_pct = _calculate_area_pct(bbox, orig_shape)

                mask_area_pct = 0.0
                if masks is not None and i < len(masks):
                    mask = masks[i].data.cpu().numpy().squeeze()
                    mask_area_pct = round(
                        float(mask.sum()) / (mask.shape[0] * mask.shape[1]) * 100, 2
                    )

                det = {
                    "class_id":             cls_id,
                    "class_name":           cls_name,
                    "confidence":           round(confidence, 4),
                    "bbox":                 [round(x, 1) for x in bbox],
                    "area_percentage":      area_pct,
                    "mask_area_percentage": mask_area_pct,
                    "is_damage":            False,
                    "is_part":              True,
                    "phase":                1,
                }
                part_dets.append(det)

                if cls_id == 14 and license_plate_bbox is None:  # License-plate
                    license_plate_bbox = det["bbox"]

       
        # Phase 2 — DAMAGE DETECTION  (conf=0.15, imgsz=800)                 #
        
        dmg_results = seg_model(
            processed_path,
            conf=DAMAGE_CONF,
            iou=NMS_IOU,
            imgsz=INFER_IMGSZ,
            verbose=False,
        )

        damage_dets: List[Dict] = []

        for result in dmg_results:
            boxes = result.boxes
            masks = result.masks
            if boxes is None or len(boxes) == 0:
                continue

            sx = orig_w / result.orig_shape[1]
            sy = orig_h / result.orig_shape[0]

            for i, box in enumerate(boxes):
                cls_id = int(box.cls[0])
                if cls_id not in DAMAGE_CLASSES:
                    continue  # this pass: damage only

                cls_name   = result.names.get(cls_id, f"class_{cls_id}")
                confidence = float(box.conf[0])
                
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bbox = [x1 * sx, y1 * sy, x2 * sx, y2 * sy]

                area_pct = _calculate_area_pct(bbox, orig_shape)

                mask_area_pct = 0.0
                if masks is not None and i < len(masks):
                    mask = masks[i].data.cpu().numpy().squeeze()
                    mask_area_pct = round(
                        float(mask.sum()) / (mask.shape[0] * mask.shape[1]) * 100, 2
                    )

                damage_dets.append({
                    "class_id":             cls_id,
                    "class_name":           cls_name,
                    "confidence":           round(confidence, 4),
                    "bbox":                 [round(x, 1) for x in bbox],
                    "area_percentage":      area_pct,
                    "mask_area_percentage": mask_area_pct,
                    "is_damage":            True,
                    "is_part":              False,
                    "phase":                2,
                })

        # Cleanup temp file
        if processed_path != image_path and os.path.exists(processed_path):
            try:
                os.remove(processed_path)
            except:
                pass

        
        # Merge & correlate                                                   #
        
        all_dets = part_dets + damage_dets

        damage_part_mapping = _correlate_damage_to_parts(damage_dets, part_dets, orig_shape)
        affected_parts  = _extract_affected_parts(part_dets, damage_part_mapping)
        damage_types    = list({d["class_name"] for d in damage_dets})
        dominant_type   = _get_dominant_damage_type(damage_dets)
        severity, severity_score = _compute_severity(damage_dets, damage_part_mapping)
        damaged_panels  = _build_damaged_panels(damage_part_mapping, part_dets)
        summary = _generate_summary(damage_dets, part_dets, severity, damage_part_mapping)

        p1_method = "bbox_overlap" if part_dets else "spatial_heuristic"
        print(
            f"[INFO] Dual-phase: "
            f"{len(part_dets)} parts @conf={PARTS_CONF} | "
            f"{len(damage_dets)} damages @conf={DAMAGE_CONF} | "
            f"assignment={p1_method}"
        )

        return {
            "success":              True,
            "damage_detected":      len(damage_dets) > 0,
            "vehicle_detected":     len(part_dets) > 0,
            "damage_types":         damage_types,
            "dominant_damage_type": dominant_type,
            "affected_parts":       affected_parts,
            "damaged_panels":       damaged_panels,
            # price_api_parts: [{part_key, damage_type}] — used by Price API to
            # decide repair vs replacement per part. Deduped to worst damage per part.
            "price_api_parts":      _build_damage_part_mapping_for_price_api(damage_part_mapping),
            "severity":             severity,
            "severity_score":       severity_score,
            "detections":           all_dets,
            "damage_detections":    damage_dets,
            "part_detections":      part_dets,
            "total_detections":     len(all_dets),
            "damage_part_mapping":  damage_part_mapping,
            "license_plate_bbox":   license_plate_bbox,
            "summary":              summary,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"Detection failed: {str(e)}"}



# LICENSE PLATE CROP (for OCR enhancement)

def get_license_plate_crop(image_path: str) -> Optional[np.ndarray]:
    """
    Detect license plate and return the cropped region as a numpy array.
    Returns None if no plate detected.
    """
    try:
        from PIL import Image
        result = detect_damage_and_parts(image_path, conf_threshold=0.20)
        if not result.get("success") or not result.get("license_plate_bbox"):
            return None

        x1, y1, x2, y2 = result["license_plate_bbox"]
        img = Image.open(image_path)
        # Add small padding
        w, h = img.size
        pad = 10
        crop = img.crop((
            max(0, x1 - pad), max(0, y1 - pad),
            min(w, x2 + pad), min(h, y2 + pad),
        ))
        return np.array(crop)
    except Exception as e:
        print(f"[WARNING] License plate crop failed: {e}")
        return None


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def _calculate_area_pct(bbox: List[float], image_shape: tuple) -> float:
    """Calculate percentage of image covered by bbox."""
    x1, y1, x2, y2 = bbox
    box_area = (x2 - x1) * (y2 - y1)
    img_area = image_shape[0] * image_shape[1]  # h * w
    return round((box_area / img_area) * 100, 2) if img_area > 0 else 0.0


def _box_overlap_ratio(dmg_box: List[float], part_box: List[float]) -> float:
    """What fraction of the damage box's area is covered by the part box?"""
    ix1 = max(dmg_box[0], part_box[0])
    iy1 = max(dmg_box[1], part_box[1])
    ix2 = min(dmg_box[2], part_box[2])
    iy2 = min(dmg_box[3], part_box[3])

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter = (ix2 - ix1) * (iy2 - iy1)
    # Area of the damage box
    dmg_area = max((dmg_box[2] - dmg_box[0]) * (dmg_box[3] - dmg_box[1]), 1e-6)

    return inter / dmg_area


def _estimate_part_from_position(
    bbox: List[float], image_shape: tuple
) -> tuple[str, str]:
    """
    Refined spatial heuristic: estimate car part from normalised centre of damage bbox.
    Matches user's successful test script logic for accurate fallbacks.
    """
    img_h, img_w = image_shape  # (height, width)
    x1, y1, x2, y2 = bbox
    cx = ((x1 + x2) / 2) / img_w
    cy = ((y1 + y2) / 2) / img_h

    if cy < 0.35:
        if cx < 0.4:
            return "Hood", "hood"
        elif cx > 0.6:
            return "Trunk", "trunk"
        else:
            return "Windshield", "windshield"

    if cy > 0.70:
        if cx < 0.35:
            return "Front-bumper", "front_bumper"
        elif cx > 0.65:
            return "Back-bumper", "rear_bumper"
        else:
            return "Front-bumper", "front_bumper"

    if cx < 0.30:
        return ("Front-door", "door_fl") if cy < 0.55 else ("Fender", "fender_fl")
    if cx > 0.70:
        return ("Back-door", "door_rl") if cy < 0.55 else ("Fender", "fender_rl")

    return ("Hood", "hood") if cy < 0.55 else ("Front-door", "door_fl")


def _correlate_damage_to_parts(
    damage_dets: List[Dict], part_dets: List[Dict],
    image_shape: tuple = (1, 1),
) -> List[Dict]:
   
    mapping = []
    for dmg in damage_dets:
        best_part = None
        best_ratio = 0.0
        for part in part_dets:
            ratio = _box_overlap_ratio(dmg["bbox"], part["bbox"])
            if ratio > best_ratio:
                best_ratio = ratio
                best_part = part

        entry = {
            "damage_class": dmg["class_name"],
            "damage_type": DAMAGE_TYPE_MAP.get(dmg["class_name"], dmg["class_name"].lower()),
            "confidence": dmg["confidence"],
            "area_percentage": dmg.get("mask_area_percentage", dmg["area_percentage"]),
        }

        if best_part and best_ratio >= BBOX_IOU_MIN: # BBOX_IOU_MIN=0.25 (now used for overlap ratio)
            entry["part_class"] = best_part["class_name"]
            entry["panel_key"] = PART_TO_PANEL_KEY.get(best_part["class_name"], best_part["class_name"].lower())
            entry["ratio"] = round(best_ratio, 3)
            entry["method"] = "bbox_overlap"
        else:
            est_part, est_key = _estimate_part_from_position(dmg["bbox"], image_shape)
            entry["part_class"] = est_part
            entry["panel_key"] = est_key
            entry["ratio"] = round(best_ratio, 3)
            entry["method"] = "spatial_heuristic"

        mapping.append(entry)

    return mapping


def _extract_affected_parts(
    part_dets: List[Dict], damage_part_mapping: List[Dict]
) -> List[str]:
    """Return canonical panel keys of parts that have associated damage."""
    parts = set()
    for m in damage_part_mapping:
        if m.get("panel_key") and m["panel_key"] != "body_panel":
            parts.add(m["panel_key"])
    # If no specific mapping, fall back to detected parts
    if not parts and part_dets:
        for p in part_dets:
            key = PART_TO_PANEL_KEY.get(p["class_name"])
            if key:
                parts.add(key)
    return list(parts)


def _get_dominant_damage_type(damage_dets: List[Dict]) -> Optional[str]:
    """Return the most common damage type string."""
    if not damage_dets:
        return None
    from collections import Counter
    counts = Counter(d["class_name"] for d in damage_dets)
    top = counts.most_common(1)[0][0]
    return DAMAGE_TYPE_MAP.get(top, top.lower())


def _compute_severity(
    damage_dets: List[Dict],
    damage_part_mapping: Optional[List[Dict]] = None,
) -> tuple[str, float]:
    
    if not damage_dets:
        return "none", 0.0

    # ── Build a part-key lookup from the mapping (damage index → panel key) ──
    # If no mapping supplied, treat every detection as its own unique region.
    idx_to_part: dict = {}
    if damage_part_mapping:
        for i, m in enumerate(damage_part_mapping):
            idx_to_part[i] = m.get("panel_key") or f"unknown_{i}"

    # ── Per-region best detection ────────────────────────────────────────────
    # key: panel_key  →  value: best (confidence_weighted_weight, area)
    region_best: dict = {}   # panel_key → {"weight": float, "area": float}

    for i, d in enumerate(damage_dets):
        raw_weight  = DAMAGE_SEVERITY_WEIGHT.get(d["class_name"], 0.5)
        confidence  = float(d.get("confidence", 1.0))          # 0-1 from YOLO
        conf_weight = raw_weight * confidence                    # scale by conf
        area        = float(d.get("mask_area_percentage", d.get("area_percentage", 0)))

        region_key = idx_to_part.get(i, f"det_{i}")

        existing = region_best.get(region_key)
        if existing is None or conf_weight > existing["weight"]:
            region_best[region_key] = {"weight": conf_weight, "area": area}

    #  Aggregate across unique regions 
    total_weight = sum(r["weight"] for r in region_best.values())
    total_area   = sum(r["area"]   for r in region_best.values())
    unique_regions = len(region_best)

    # Base score — confidence-weighted (max 8.0)
    base_score = min(total_weight * 2, 8.0)

    # Area bonus — based on deduplicated region areas (max 2.0)
    area_bonus = min(total_area / 10.0, 2.0)

    # Count bonus — unique damaged regions only (max 1.5)
    count_bonus = min(unique_regions * 0.3, 1.5)

    score = min(base_score + area_bonus + count_bonus, 10.0)
    score = round(score, 1)

    # Map to label (95% threshold for totaled — requires extreme damage evidence)
    if score <= 0:
        label = "none"
    elif score <= 3:
        label = "minor"
    elif score <= 6:
        label = "moderate"
    elif score < 9.5:
        label = "severe"
    else:
        label = "totaled"   # Only at 9.5+/10 (95%) — needs airbag/fluid confirmation

    return label, score


def _build_damaged_panels(
    damage_part_mapping: List[Dict], part_dets: List[Dict]
) -> List[str]:
    """Build list of damaged panel keys for repair_estimator_service (legacy)."""
    panels = set()
    for m in damage_part_mapping:
        key = m.get("panel_key")
        if key and key != "body_panel":
            panels.add(key)
    return list(panels)


# Severity order for deduplication: higher number = worse damage = replace wins
_DAMAGE_SEVERITY_ORDER = {
    "missing": 5,
    "crush":   4,
    "broken":  4,
    "crack":   3,
    "tear":    3,
    "deform":  3,
    "dent":    2,
    "scratch": 1,
}


def _build_damage_part_mapping_for_price_api(
    damage_part_mapping: List[Dict],
) -> List[Dict]:
    
    seen: Dict[str, str] = {}  # panel_key → damage_type (worst so far)
    for m in damage_part_mapping:
        key = m.get("panel_key")
        dt  = m.get("damage_type", "scratch").lower().strip()
        if not key or key == "body_panel":
            continue
        existing_sev = _DAMAGE_SEVERITY_ORDER.get(seen.get(key, ""), 0)
        new_sev      = _DAMAGE_SEVERITY_ORDER.get(dt, 0)
        if key not in seen or new_sev > existing_sev:
            seen[key] = dt
    return [{"part_key": k, "damage_type": v} for k, v in seen.items()]


def _generate_summary(
    damage_dets: List[Dict],
    part_dets: List[Dict],
    severity: str,
    mapping: List[Dict],
) -> str:
    """Human-readable summary."""
    if not damage_dets:
        if part_dets:
            part_names = list({p["class_name"] for p in part_dets})
            return f"No damage detected. Parts visible: {', '.join(part_names)}"
        return "No damage or vehicle parts detected"

    n_damage = len(damage_dets)
    types = list({d["class_name"] for d in damage_dets})
    avg_conf = sum(d["confidence"] for d in damage_dets) / n_damage

    parts_hit = [m["part_class"] for m in mapping if m.get("part_class") != "unknown"]
    parts_str = f" on {', '.join(set(parts_hit))}" if parts_hit else ""

    return (
        f"{severity.capitalize()} damage detected — "
        f"{n_damage} {', '.join(types)} region(s){parts_str} "
        f"({avg_conf:.0%} avg confidence)"
    )


def get_model_info() -> Dict[str, Any]:
    """Get model + system info."""
    return {
        "yolo_seg_available": YOLO_SEG_AVAILABLE,
        "model_initialized": SEG_MODEL_INITIALIZED,
        "gpu_info": check_gpu_available(),
        "model_type": type(seg_model).__name__ if seg_model else None,
        "classes": {**DAMAGE_CLASSES, **PART_CLASSES},
    }
