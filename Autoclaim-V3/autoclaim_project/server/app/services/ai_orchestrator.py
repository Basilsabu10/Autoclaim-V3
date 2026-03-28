

import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.config import settings

# Import always-available services
from app.services.exif_service import extract_metadata
from app.services.ocr_service import extract_number_plate
from app.services.ela_service import analyze_claim_images_ela
from app.services.sightengine_service import analyze_claim_images_sightengine

# Import new YOLO11m-seg service
try:
    from app.services.yolo11_seg_service import (
        detect_damage_and_parts,
        init_seg_model,
        get_model_info,
        get_license_plate_crop,
        YOLO_SEG_AVAILABLE,
        DAMAGE_TYPE_MAP,
    )
except ImportError:
    YOLO_SEG_AVAILABLE = False
    print("[WARNING] YOLO11m-seg service not available")

# Import Groq service 
GROQ_AVAILABLE = False
try:
    from app.services.groq_service import extract_vehicle_data, GROQ_AVAILABLE as GROQ_STATUS
    GROQ_AVAILABLE = GROQ_STATUS
except ImportError:
    print("[WARNING] Groq service not available")

# DATA PREPARATION FOR VERIFICATION ENGINE


def prepare_verification_data(
    extracted_data: Dict[str, Any],
    metadata: Dict[str, Any],
    ocr: Dict[str, Any],
    yolo_seg: Dict[str, Any],
) -> Dict[str, Any]:
    
    identity = extracted_data.get("identity", {})
    damage = extracted_data.get("damage", {})
    forensics = extracted_data.get("forensics", {})
    fraud = extracted_data.get("fraud_analysis", {})

    # Derive severity label from numeric score if text severity is missing.
    # Prefer Groq damage data, but fall back to YOLO seg results if Groq is absent.
    _severity_text = damage.get("severity") or damage.get("damage_severity")
    if not _severity_text:
        _score = float(damage.get("severity_score", 0) or 0)
        if _score >= 0.9:
            _severity_text = "totaled"
        elif _score >= 0.7:
            _severity_text = "severe"
        elif _score >= 0.4:
            _severity_text = "moderate"
        elif _score > 0:
            _severity_text = "minor"
        else:
            # Groq found no damage — fall back to YOLO severity
            _yolo_severity = (yolo_seg.get("severity") or "").lower()
            _severity_text = _yolo_severity if _yolo_severity and _yolo_severity != "none" else "none"

    # Also use YOLO for damage_detected and damaged_panels if Groq is empty
    _groq_damage_detected = damage.get("damage_detected", False)
    _yolo_damage_detected = yolo_seg.get("damage_detected", False)
    _damage_detected = _groq_damage_detected or _yolo_damage_detected

    _groq_panels = damage.get("damaged_panels", [])
    _yolo_panels = yolo_seg.get("damaged_panels", [])
    _damaged_panels = _groq_panels if _groq_panels else _yolo_panels

    ai_analysis = {
        # Raw metadata including hashes
        "metadata": {
            "image_hashes": metadata.get("image_hashes", []),
        },

        # EXIF Metadata
        "exif_metadata": {
            "timestamp": metadata.get("timestamp"),
            "gps_coordinates": {
                "latitude": metadata.get("gps_lat"),
                "longitude": metadata.get("gps_lon"),
            },
            "location_name": metadata.get("location_name"),
            "camera_make": metadata.get("camera_make"),
            "camera_model": metadata.get("camera_model"),
            "anomalies": metadata.get("anomalies", []),
        },

        # OCR Data
        "ocr_data": {
            "plate_text": ocr.get("plate_text"),
            "confidence": ocr.get("confidence") or 0.0,
            "chase_number": None,
            "chase_number_confidence": 0.0,
        },

        # YOLO Results (now from segmentation model)
        "yolo_results": {
            "yolo_damage_detected": yolo_seg.get("damage_detected", False),
            "yolo_severity": yolo_seg.get("severity", "none"),
            "yolo_detections": yolo_seg.get("detections", []),
        },

        # Vehicle Identification
        "vehicle_identification": {
            "make": identity.get("vehicle_make"),
            "model": identity.get("vehicle_model"),
            "year": identity.get("vehicle_year"),
            "color": identity.get("vehicle_color"),
            "detected_confidence": identity.get("identification_confidence", 0.0),
            "license_plate_visible": identity.get("license_plate_visible", False),
            "license_plate_obscured": identity.get("license_plate_obscured", False),
        },

        # Forensic Indicators
        "forensic_indicators": {
            "is_screen_recapture": forensics.get("is_screen_recapture", False),
            "has_ui_elements": forensics.get("has_ui_elements", False),
            "has_watermarks": forensics.get("has_watermarks", False),
            "image_quality": forensics.get("image_quality", "high"),
            "is_blurry": forensics.get("is_blurry", False),
            "multiple_light_sources": forensics.get("multiple_light_sources", False),
            "shadows_inconsistent": forensics.get("shadows_inconsistent", False),
            "fraud_detected": fraud.get("fraud_detected", False),
            "fraud_score": fraud.get("fraud_score", 0.0),
            "fraud_indicators": fraud.get("fraud_indicators", []),
            "reasoning": fraud.get("reasoning", ""),
        },

        # Authenticity Indicators
        "authenticity_indicators": {
            "stock_photo_likelihood": "unknown",
            "editing_detected": False,
            "lighting_consistent": not forensics.get("multiple_light_sources", False),
            "shadows_natural": not forensics.get("shadows_inconsistent", False),
            "compression_uniform": True,
        },

        # Damage Assessment — merge Groq and YOLO so neither is lost
        "damage_assessment": {
            "ai_damage_detected": _damage_detected,
            "ai_severity": _severity_text,
            "damaged_panels": _damaged_panels,
            "damage_type": damage.get("damage_type") or yolo_seg.get("dominant_damage_type"),
            "severity_score": damage.get("severity_score", 0.0) or yolo_seg.get("severity_score", 0.0),
            # Physical markers — Groq vision reads these directly from the image
            # (Groq's forensics section is the source since the damage section was removed)
            "airbags_deployed": (
                damage.get("airbags_deployed", False) or
                forensics.get("airbags_deployed", False)
            ),
            "fluid_leaks_visible": (
                damage.get("fluid_leaks_visible", False) or
                forensics.get("fluid_leaks_visible", False)
            ),
            "parts_missing": damage.get("parts_missing", False),
            "ai_cost_min": damage.get("cost_estimate_min"),
            "ai_cost_max": damage.get("cost_estimate_max"),
        },

        # Pre-existing Indicators
        "pre_existing_indicators": {
            "rust_detected": damage.get("is_rust_present", False),
            "paint_fading": damage.get("is_paint_faded_around_damage", False),
            "dirt_accumulation": damage.get("is_dirt_in_damage", False),
            "old_repairs_visible": False,
        },

        # Narrative Consistency
        "narrative_consistency": {
            "visual_evidence_matches": True,
            "inconsistencies": [],
        },

        # Multi-image Analysis
        "multi_image_analysis": {},

        # HuggingFace AI-generated image detection results
        "ai_detection": extracted_data.get("ai_detection", {}),
    }

    return ai_analysis



# BUILD EXTRACTION DATA DEFAULTS (yolo_only or fallback)


def _build_extraction_defaults(yolo_seg: Dict[str, Any], ocr: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a standard 'extracted_data' dict using YOLO results + sensible defaults.
    """
    damage_detected = yolo_seg.get("damage_detected", False)
    damaged_panels = yolo_seg.get("damaged_panels", [])
    severity = yolo_seg.get("severity", "none")
    severity_score = yolo_seg.get("severity_score", 0.0)
    dominant_type = yolo_seg.get("dominant_damage_type")
    mapping = yolo_seg.get("damage_part_mapping", [])
    plate_detected = yolo_seg.get("license_plate_bbox") is not None

    # Check for "Missing part" in damage types
    parts_missing = any(d.get("class_name") == "Missing part" for d in yolo_seg.get("damage_detections", []))

    # Build damage description from mapping
    damage_descriptions = []
    for m in mapping:
        if m.get("part_class") != "unknown":
            damage_descriptions.append(f"{m['damage_class']} on {m['part_class']}")
        else:
            damage_descriptions.append(m["damage_class"])

    return {
        "success": True,
        "provider": "yolo_seg",
        "model": "yolo11m-seg",
        "identity": {
            "vehicle_color": None,
            "license_plate_text": ocr.get("plate_text"),
            "license_plate_visible": plate_detected,
        },
        "damage": {
            "damage_detected": damage_detected,
            "damage_type": dominant_type,
            "severity_score": severity_score,
            "severity": severity,
            "damaged_panels": damaged_panels,
            "parts_missing": parts_missing,
            "damage_descriptions": damage_descriptions,
        },
        "forensics": {
            "is_screen_recapture": False,
            "has_ui_elements": False,
            "has_watermarks": False,
            "image_quality": "high",
            "is_blurry": False,
        },
        "damage_assessment": {
            "ai_damage_detected": damage_detected,
            "ai_severity": severity,
            "damaged_panels": damaged_panels,
            "damage_type": dominant_type,
            "severity_score": severity_score,
            "parts_missing": parts_missing,
            "ai_cost_min": 0,
            "ai_cost_max": 0,
        }
    }



# MAIN ANALYSIS FUNCTION


def analyze_claim(
    damage_image_paths: List[str],
    front_image_path: Optional[str],
    description: str,
    claim_amount: int = 0,
    policy_data: Optional[Dict] = None,
    claim_history: Optional[List[Dict]] = None,
    original_filenames: Optional[Dict[str, str]] = None,
    accident_date: Optional[datetime] = None,
    rule_config=None,  # Optional RuleConfig override (e.g. admin-set threshold)
) -> Dict[str, Any]:
   
    from app.services.verification_rules import VerificationRules
    from app.services.image_hashing import hash_claim_images
    print(f"[AI] Running Unified YOLO + Groq Pipeline")

    result = {
        "metadata": {
            "timestamp": None, "gps_lat": None, "gps_lon": None,
            "location_name": None, "camera_type": None,
            "filename_parsed": False, "source": None,
            "image_hashes": [],  # Store the new perceptual hashes
            "anomalies": [],
        },
        "ocr": {"plate_text": None, "confidence": None},
        "yolo_damage": {
            "success": False, "damage_detected": False, "detections": [],
            "severity": "none", "affected_parts": [], "summary": "Not run",
        },
        "ai_analysis": {
            "damage_type": None, "severity": None, "affected_parts": [],
            "recommendation": "review", "cost_min": None, "cost_max": None,
            "analysis_text": None, "risk_flags": [], "provider": None,
        },
        "verification": None,
    }

    # ── 1. EXIF metadata & Hashing 
    if damage_image_paths:
        
        # Calculate perceptual hashes for duplicate detection
        all_images_to_hash = list(damage_image_paths)
        if front_image_path:
            all_images_to_hash.append(front_image_path)
        result["metadata"]["image_hashes"] = hash_claim_images(all_images_to_hash)
        
        for path in damage_image_paths:
            if os.path.exists(path):
                original_fn = (original_filenames or {}).get(path)
                exif = extract_metadata(path, original_filename=original_fn)
                if exif.get("timestamp") or exif.get("gps_lat") or exif.get("filename_parsed"):
                    result["metadata"].update(exif)
                    break

    # ── 1.5. ELA Analysis (Error Level Analysis) ──
    # Run ELA immediately to ensure images are analyzed before any compression or cropping occurs
    print("[AI] Running Error Level Analysis (ELA) for image manipulation...")
    ela_res = analyze_claim_images_ela(damage_image_paths)

    # ── 1.6. AI Generation Detection (Sightengine) ──
    print("[AI] Running Sightengine AI-image detection...")
    sightengine_res = analyze_claim_images_sightengine(damage_image_paths)
    print(f"[Sightengine] Result → ai_generated={sightengine_res.get('ai_generated')}, score={sightengine_res.get('max_ai_score')}")



    # ── 2. OCR — try YOLO crop first, then fall back to full image ─────
    if front_image_path and os.path.exists(front_image_path):
        result["ocr"] = extract_number_plate(front_image_path)

    # If OCR confidence is low and YOLO can detect license plate, try cropped OCR
    if YOLO_SEG_AVAILABLE and (result["ocr"].get("confidence") or 0.0) < 0.5:
        # Try YOLO license-plate crop on all images
        candidate_images = ([front_image_path] if front_image_path else []) + (damage_image_paths or [])
        for img_path in candidate_images:
            if img_path and os.path.exists(img_path):
                plate_crop = get_license_plate_crop(img_path)
                if plate_crop is not None:
                    try:
                        # Save temp crop for OCR
                        import tempfile
                        from PIL import Image
                        temp_path = os.path.join(tempfile.gettempdir(), "yolo_plate_crop.jpg")
                        Image.fromarray(plate_crop).save(temp_path)
                        crop_ocr = extract_number_plate(temp_path)
                        if (crop_ocr.get("confidence") or 0) > (result["ocr"].get("confidence") or 0):
                            result["ocr"] = crop_ocr
                            print(f"[OCR] YOLO-cropped plate improved: {crop_ocr.get('plate_text')} ({crop_ocr.get('confidence'):.2f})")
                            break
                    except Exception as e:
                        print(f"[OCR] YOLO crop OCR failed: {e}")

    # ── 3. YOLO11m-seg damage + parts segmentation ────────────────────
    yolo_seg_result = {"success": False}
    # Include front image in YOLO damage detection if it exists
    yolo_images = list(damage_image_paths) if damage_image_paths else []
    if front_image_path:
        yolo_images.append(front_image_path)
        
    if YOLO_SEG_AVAILABLE and yolo_images:
        # Ensure model is initialized (lazy init on first use)
        try:
            init_seg_model()
        except Exception as e:
            print(f"[YOLO-Seg] Model init warning: {e}")
        # Run segmentation on each image and pick the best
        for path in yolo_images:
            if os.path.exists(path):
                seg_res = detect_damage_and_parts(path)
                if seg_res.get("success"):
                    yolo_seg_result = seg_res
                    # Map to legacy yolo_damage format for backward compatibility
                    result["yolo_damage"] = {
                        "success": True,
                        "vehicle_detected": seg_res.get("vehicle_detected", False),
                        "damage_detected": seg_res.get("damage_detected", False),
                        "detections": seg_res.get("detections", []),
                        "total_detections": seg_res.get("total_detections", 0),
                        "severity": seg_res.get("severity", "none"),
                        "severity_score": seg_res.get("severity_score", 0.0),
                        "affected_parts": seg_res.get("affected_parts", []),
                        "damaged_panels": seg_res.get("damaged_panels", []),
                        "price_api_parts": seg_res.get("price_api_parts", []),  # ← was missing!
                        "damage_part_mapping": seg_res.get("damage_part_mapping", []),
                        "summary": seg_res.get("summary", ""),
                    }
                    print(f"[YOLO-Seg] {seg_res.get('summary', 'Detection complete')}")
                    break
    else:
        result["yolo_damage"]["summary"] = (
            "YOLO seg not available" if not YOLO_SEG_AVAILABLE else "No images provided"
        )

    # Initialize extraction_result with YOLO defaults
    extraction_result = _build_extraction_defaults(yolo_seg_result, result["ocr"])

    # ── 4. Forensic & Fraud Extraction (Groq) 
    if GROQ_AVAILABLE:
        print("[AI] Running Groq Forensic & Fraud Check...")
        all_images = (damage_image_paths or []).copy()
        if front_image_path:
            all_images.append(front_image_path)

        groq_result = extract_vehicle_data(
            image_paths=all_images,
            description=description,
            policy_data=policy_data,
        )

        if groq_result.get("success"):
            # Update forensics, identity, and fraud analysis from Groq
            groq_forensics = groq_result.get("forensics")
            if isinstance(groq_forensics, dict):
                extraction_result["forensics"].update(groq_forensics)
            
            groq_identity = groq_result.get("identity")
            if isinstance(groq_identity, dict):
                extraction_result["identity"]["vehicle_make"] = groq_identity.get("vehicle_make")
                extraction_result["identity"]["vehicle_model"] = groq_identity.get("vehicle_model")
                extraction_result["identity"]["vehicle_color"] = groq_identity.get("vehicle_color")

            groq_fraud = groq_result.get("fraud_analysis")
            if isinstance(groq_fraud, dict):
                extraction_result["fraud_analysis"] = groq_fraud
            
            extraction_result["provider"] = "unified"
            print("[AI] Groq forensic/fraud data integrated")
        else:
            print(f"[AI] Groq failed: {groq_result.get('error')}. Using technical defaults.")
    else:
        print("[AI] Groq not available. technical-only analysis.")

    # ── 4.5. ELA Analysis Results Integration ──
    if ela_res.get("success"):
        extraction_result["forensics"]["ela_score"] = ela_res.get("highest_ela_score")
        if ela_res.get("editing_detected"):
            extraction_result["fraud_analysis"]["fraud_detected"] = True
            
            # Boost fraud score
            current_fraud = float(extraction_result["fraud_analysis"].get("fraud_score") or 0.0)
            extraction_result["fraud_analysis"]["fraud_score"] = max(current_fraud, 0.8)
            
            # Add indicator
            indicators = extraction_result["fraud_analysis"].get("fraud_indicators") or []
            if "MANIPULATED OR GENERATED IMAGE" not in indicators:
                indicators.append("MANIPULATED OR GENERATED IMAGE")
            extraction_result["fraud_analysis"]["fraud_indicators"] = indicators
            
            reasoning = extraction_result["fraud_analysis"].get("reasoning") or ""
            ela_msg = " MANIPULATED OR GENERATED IMAGE: High ELA score suggests artificial composite."
            if reasoning:
                reasoning += ela_msg
            else:
                reasoning = ela_msg.strip()
            extraction_result["fraud_analysis"]["reasoning"] = reasoning

    # ── 4.6. Sightengine AI Detection Results Integration ──
    extraction_result["ai_detection"] = sightengine_res
    if sightengine_res.get("ai_generated"):
        extraction_result["fraud_analysis"]["fraud_detected"] = True
        current_fraud = float(extraction_result["fraud_analysis"].get("fraud_score") or 0.0)
        extraction_result["fraud_analysis"]["fraud_score"] = max(current_fraud, 0.95)
        indicators = extraction_result["fraud_analysis"].get("fraud_indicators") or []
        if "SIGHTENGINE AI GENERATED" not in indicators:
            indicators.append("SIGHTENGINE AI GENERATED")
        extraction_result["fraud_analysis"]["fraud_indicators"] = indicators
        reasoning = extraction_result["fraud_analysis"].get("reasoning") or ""
        sight_msg = (
            f" Sightengine AI detector flagged image as synthetic "
            f"(score: {sightengine_res.get('max_ai_score', 0):.2f})."
        )
        extraction_result["fraud_analysis"]["reasoning"] = (reasoning + sight_msg).strip()



    # ── Store extraction results 
    if extraction_result and extraction_result.get("success"):
        result["ai_analysis"] = extraction_result

        # ── 5. Rule-based verification 
        try:
            verification_data = prepare_verification_data(
                extracted_data=extraction_result,
                metadata=result["metadata"],
                ocr=result["ocr"],
                yolo_seg=result["yolo_damage"],
            )

            engine = VerificationRules(config=rule_config)
            vr = engine.verify_claim(
                claim_amount=claim_amount,
                ai_analysis=verification_data,
                policy_data=policy_data or {},
                history=claim_history,
                accident_date=accident_date,
            )

            result["verification"] = vr.to_dict()

            print(
                f"[Verification] Status: {vr.status}, "
                f"Confidence: {vr.confidence_level}, "
                f"Score: {vr.severity_score:.1f}, "
                f"Passed: {len(vr.passed_checks)}, "
                f"Failed: {len(vr.failed_checks)}"
            )

            # Backward-compat fields on ai_analysis
            result["ai_analysis"]["verification_status"] = vr.status
            result["ai_analysis"]["ai_recommendation"] = vr.status
            result["ai_analysis"]["overall_confidence_score"] = vr.confidence_score
            result["ai_analysis"]["fraud_probability"] = (
                "HIGH" if vr.status == "REJECTED"
                else "MEDIUM" if vr.status == "FLAGGED"
                else "LOW"
            )
            result["ai_analysis"]["ai_risk_flags"] = [f.rule_id for f in vr.failed_checks]
            result["ai_analysis"]["human_review_priority"] = (
                "CRITICAL" if vr.status == "REJECTED"
                else "HIGH" if vr.requires_human_review
                else "LOW"
            )
            result["ai_analysis"]["ai_reasoning"] = vr.decision_reason

        except Exception as e:
            print(f"[Verification] Error: {e}")
            import traceback
            traceback.print_exc()
            result["verification"] = {"error": str(e)}
            result["ai_analysis"]["ai_reasoning"] = f"Verification error: {e}"
    else:
        result["ai_analysis"]["analysis_text"] = "No AI service produced valid results"
        result["ai_analysis"]["provider"] = "none"

    return result



# SERVICE INITIALIZATION


def initialize_services() -> Dict[str, bool]:
    """Register AI service availability (models load lazily on first request)."""
    
    status = {
        "yolo_seg": YOLO_SEG_AVAILABLE,  # Available but not loaded yet
        "groq": GROQ_AVAILABLE,
        "ai_mode": "unified",
    }

    # Don't load YOLO model here — it will init lazily on first analyze call
    print(f"[AI Services] YOLO-Seg: {'available' if YOLO_SEG_AVAILABLE else 'NOT AVAILABLE'}, "
          f"Groq: {status['groq']}, Mode: unified (lazy loading)")

    return status
