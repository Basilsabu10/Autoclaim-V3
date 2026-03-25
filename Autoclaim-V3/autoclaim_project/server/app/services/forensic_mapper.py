

from typing import Dict, Any


def map_forensic_to_db(ai_result: Dict[str, Any], policy_data: Dict[str, Any] = None) -> Dict[str, Any]:
    
    
    # Extract sub-sections from AI extraction (works for both Groq and YOLO-only)
    ai_analysis_data = ai_result.get("ai_analysis", {})
    
    identity = ai_analysis_data.get("identity") or ai_result.get("identity", {})
    damage = ai_analysis_data.get("damage") or ai_result.get("damage", {})
    forensics = ai_analysis_data.get("forensics") or ai_result.get("forensics", {})
    fraud = ai_analysis_data.get("fraud_analysis") or {}
    
    # Extract orchestrator sections (metadata, OCR, YOLO)
    metadata = ai_result.get("metadata", {})
    ocr = ai_result.get("ocr", {})
    yolo_damage = ai_result.get("yolo_damage", {})
    
    # YOLO-seg specific: damage-to-part mapping and damaged panels
    damage_part_mapping = yolo_damage.get("damage_part_mapping", [])
    yolo_damaged_panels = yolo_damage.get("damaged_panels", [])
    
    # Extract computed decisions (from rule-based logic or verification engine)
    decisions = ai_result.get("decisions", {})
    verification = ai_result.get("verification", {})
    
    # === DECISION MERGING LOGIC [NEW] ===
    # 1. Initialize with rule-based Verification results (if available)
    if verification and not verification.get("error"):
        ai_recommendation_value = verification.get("status")  # APPROVED, FLAGGED, REJECTED
        fraud_probability_value = _map_status_to_fraud_probability(verification.get("status"))
        fraud_score_value = verification.get("severity_score", 0.0) / 10.0  # Scale to 0-1
        confidence_score_value = verification.get("confidence_score")
        risk_flags_value = [failure["rule_id"] for failure in verification.get("failed_checks", [])]
        reasoning_value = verification.get("decision_reason")
        review_priority_value = "CRITICAL" if verification.get("status") == "REJECTED" else \
                                 "HIGH" if verification.get("requires_human_review") else \
                                 "LOW" if verification.get("status") == "APPROVED" else "MEDIUM"
    else:
        # Fall back to legacy decisions format or defaults
        ai_recommendation_value = decisions.get("ai_recommendation", "FLAGGED")
        fraud_probability_value = decisions.get("fraud_probability", "UNKNOWN")
        fraud_score_value = decisions.get("fraud_score", 0.0)
        confidence_score_value = decisions.get("overall_confidence_score", identity.get("detected_confidence", 0.5) * 100)
        risk_flags_value = decisions.get("ai_risk_flags", [])
        reasoning_value = decisions.get("ai_reasoning", "Analysis in progress.")
        review_priority_value = decisions.get("human_review_priority", "MEDIUM")

    # 2. Merge with Groq Fraud Analysis (AI indicators)
    if fraud:
        # Combine Risk Flags (avoid duplicates)
        ai_flags = fraud.get("fraud_indicators", [])
        for flag in ai_flags:
            if flag not in risk_flags_value:
                risk_flags_value.append(flag)
        
        # Merge Recommendation (Most conservative takes priority)
        # REJECTED > FLAGGED > APPROVED
        groq_rec = "REJECTED" if fraud.get("fraud_detected") else "APPROVED"
        if "REJECTED" in (ai_recommendation_value, groq_rec):
            ai_recommendation_value = "REJECTED"
        elif "FLAGGED" in (ai_recommendation_value, groq_rec):
            ai_recommendation_value = "FLAGGED"
            
        # Merge Fraud Probability (Highest takes priority)
        # HIGH > MEDIUM > LOW > VERY_LOW
        groq_prob = "HIGH" if fraud.get("fraud_detected") else "VERY_LOW"
        prob_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "VERY_LOW": 0, "UNKNOWN": 0}
        if prob_order.get(groq_prob, 0) > prob_order.get(fraud_probability_value, 0):
            fraud_probability_value = groq_prob
            
        # Merge Score (Take max for caution)
        fraud_score_value = max(fraud_score_value, fraud.get("fraud_score", 0.0))
        
        # Merge Reasoning
        if fraud.get("reasoning"):
            reasoning_value = f"{reasoning_value}\n\n[AI Analysis] {fraud.get('reasoning')}"
            
        # Review Priority
        if fraud.get("fraud_detected") or ai_recommendation_value == "REJECTED":
            review_priority_value = "CRITICAL"
        elif ai_recommendation_value == "FLAGGED":
            review_priority_value = "HIGH"
    
    # Ensure exif_timestamp is a datetime object for SQLite
    ts = metadata.get("timestamp")
    if isinstance(ts, str):
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            pass

    # Build field mapping
    forensic_data = {
        # ============================================================
        # EXIF METADATA
        # ============================================================
        "exif_timestamp": ts,
        "exif_gps_lat": metadata.get("gps_lat"),
        "exif_gps_lon": metadata.get("gps_lon"),
        "exif_location_name": metadata.get("location_name"),
        "exif_camera_make": metadata.get("camera_make"),
        "exif_camera_model": metadata.get("camera_model"),
        
        # ============================================================
        # OCR RESULTS
        # ============================================================
        "ocr_plate_text": ocr.get("plate_text"),
        "ocr_plate_confidence": ocr.get("confidence"),
        
        # ============================================================
        # YOLO DETECTION (YOLO11m-seg segmentation results)
        # ============================================================
        "yolo_damage_detected": yolo_damage.get("damage_detected", False),
        "yolo_detections": yolo_damage.get("detections", []),
        "yolo_severity": yolo_damage.get("severity"),
        "yolo_summary": yolo_damage.get("summary"),
        
        # ============================================================
        # IDENTITY EXTRACTION
        # ============================================================
        "vehicle_make": identity.get("vehicle_make"),
        "vehicle_model": identity.get("vehicle_model"),
        "vehicle_year": identity.get("vehicle_year"),
        "vehicle_color": identity.get("vehicle_color"),
        "license_plate_text": identity.get("license_plate_text") or ocr.get("plate_text"),
        
        # ============================================================
        # DAMAGE EXTRACTION
        # ============================================================
        "ai_damage_detected": damage.get("damage_detected", False),
        "ai_damage_type": damage.get("damage_type"),
        # Prefer YOLO-seg damaged panels over Groq's if available
        "ai_damaged_panels": yolo_damaged_panels or damage.get("damaged_panels", []),
        "airbags_deployed": damage.get("airbags_deployed", False) or forensics.get("airbags_deployed", False),
        "fluid_leaks_visible": damage.get("fluid_leaks_visible", False) or forensics.get("fluid_leaks_visible", False),
        "parts_missing": damage.get("parts_missing", False),
        
        # Computed severity label and structural damage flag
        # ai_structural_damage is driven PRIMARILY by physical markers (Groq vision):
        #   - airbag deployed: visible airbag fabric in image
        #   - fluid leaks: liquid pooling/drips under/around vehicle
        # YOLO severity only contributes at 95%+ score (extreme destruction)
        "ai_severity": _compute_severity_label(damage.get("severity_score")),
        "ai_structural_damage": (
            damage.get("airbags_deployed", False) or
            forensics.get("airbags_deployed", False) or
            damage.get("fluid_leaks_visible", False) or
            forensics.get("fluid_leaks_visible", False) or
            # Use YOLO's deduplicated+confidence-weighted severity_score (canonical)
            # Falls back to Groq severity_score if YOLO is unavailable
            (float(yolo_damage.get("severity_score") or damage.get("severity_score") or 0) >= 9.5)
        ),
        
        # Cost estimation from AI
        "ai_cost_min": damage.get("estimated_cost_range_INR", {}).get("min"),
        "ai_cost_max": damage.get("estimated_cost_range_INR", {}).get("max"),
        
        # ============================================================
        # FORENSICS EXTRACTION (Image Integrity)
        # ============================================================
        "is_screen_recapture": forensics.get("is_screen_recapture", False),
        "has_ui_elements": forensics.get("has_ui_elements", False),
        "has_watermarks": forensics.get("has_watermarks", False),
        "image_quality": forensics.get("image_quality"),
        "is_blurry": forensics.get("is_blurry", False),
        "multiple_light_sources": forensics.get("multiple_light_sources", False),
        "shadows_inconsistent": forensics.get("shadows_inconsistent", False),
        "ela_score": forensics.get("ela_score"),
        
        "forgery_detected": forensics.get("is_screen_recapture", False) or forensics.get("has_ui_elements", False),
        "authenticity_score": _compute_authenticity_score(forensics),
        
        # SCENE EXTRACTION (Removed as per user request)
        # ------------------------------------------------------------
        
        # PRE-EXISTING DAMAGE (Computed from indicators)
        # PRE-EXISTING DAMAGE (Computed from indicators)
        # ============================================================
        "pre_existing_damage_detected": damage.get("is_rust_present", False) or 
                                        damage.get("is_dirt_in_damage", False) or 
                                        damage.get("is_paint_faded_around_damage", False),
        "pre_existing_indicators": _build_pre_existing_indicators(damage),
        "pre_existing_description": _build_pre_existing_description(damage),
        "pre_existing_confidence": _compute_pre_existing_confidence(damage),
        
        # ============================================================
        # RULE-BASED DECISIONS / VERIFICATION RESULTS (Computed)
        # ============================================================
        "ai_risk_flags": risk_flags_value,
        "fraud_probability": fraud_probability_value,
        "fraud_score": fraud_score_value,
        "overall_confidence_score": confidence_score_value,
        "ai_recommendation": ai_recommendation_value,
        "ai_reasoning": reasoning_value,
        "human_review_priority": review_priority_value,
        
        # ============================================================
        # License plate match status (compare OCR vs policy)
        "license_plate_match_status": _compute_plate_match(
            ocr.get("plate_text") or identity.get("license_plate_text"),
            policy_data
        ),
    }
    
    # Remove None values and empty strings/lists to use database defaults safely
    # avoiding "truth value of an array is ambiguous" error with numpy arrays
    clean_data = {}
    for k, v in forensic_data.items():
        if v is None:
            continue
        if isinstance(v, str) and v == "":
            continue
        if isinstance(v, (list, dict, tuple)) and len(v) == 0:
            continue
        clean_data[k] = v
        
    return clean_data


def _build_forgery_indicators(forensics: Dict[str, Any]) -> list:
    """Build list of forgery indicators from extracted forensics data."""
    indicators = []
    
    if forensics.get("is_screen_recapture"):
        indicators.append("SCREEN_RECAPTURE")
    if forensics.get("has_ui_elements"):
        indicators.append("UI_ELEMENTS")
    if forensics.get("has_watermarks"):
        indicators.append("WATERMARKS")
    if forensics.get("shadows_inconsistent"):
        indicators.append("INCONSISTENT_SHADOWS")
    if forensics.get("multiple_light_sources"):
        indicators.append("MULTIPLE_LIGHT_SOURCES")
    
    return indicators


def _build_pre_existing_indicators(damage: Dict[str, Any]) -> list:
    """Build list of pre-existing damage indicators from extracted damage data."""
    indicators = []
    
    if damage.get("is_rust_present"):
        indicators.append("RUST")
        if damage.get("rust_locations"):
            indicators.extend([f"RUST_{loc.upper()}" for loc in damage.get("rust_locations", [])])
    
    if damage.get("is_dirt_in_damage"):
        indicators.append("DIRT_IN_DAMAGE")
    
    if damage.get("is_paint_faded_around_damage"):
        indicators.append("FADED_PAINT")
    
    return indicators


def extract_simple_fields(ai_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract simplified fields for Claim table (denormalized for quick access).
    
    Args:
        ai_result: Complete analysis result
        
    Returns:
        dict with simplified fields for Claim model
    """
    ocr = ai_result.get("ocr", {})
    identity = ai_result.get("identity", {})
    damage = ai_result.get("damage", {})
    decisions = ai_result.get("decisions", {})
    verification = ai_result.get("verification", {})
    
    # Use verification if available
    if verification and not verification.get("error"):
        ai_recommendation = verification.get("status")
    else:
        ai_recommendation = decisions.get("ai_recommendation")
    
    return {
        "vehicle_number_plate": ocr.get("plate_text") or identity.get("license_plate_text"),
        "ai_recommendation": ai_recommendation,
        "estimated_cost_min": damage.get("estimated_cost_range_INR", {}).get("min"),
        "estimated_cost_max": damage.get("estimated_cost_range_INR", {}).get("max")
    }


def _map_status_to_fraud_probability(status: str) -> str:
    """
    Map verification status to fraud probability category.
    
    Args:
        status: Verification status (APPROVED, FLAGGED, REJECTED)
        
    Returns:
        Fraud probability category (VERY_LOW, LOW, MEDIUM, HIGH)
    """
    if status == "REJECTED":
        return "HIGH"
    elif status == "FLAGGED":
        return "MEDIUM"
    elif status == "APPROVED":
        return "VERY_LOW"
    else:
        return "LOW"


def _compute_severity_label(score) -> str:
    """
    Map severity_score (0-10) to a human-readable label.
    """
    if score is None:
        return None
    score = float(score)
    if score <= 0:
        return "none"
    elif score <= 3:
        return "minor"
    elif score <= 6:
        return "moderate"
    elif score <= 8:
        return "severe"
    else:
        return "totaled"


def _compute_authenticity_score(forensics: Dict[str, Any]) -> float:
    """
    Compute an authenticity score (0-100) from forensic indicators.
    Starts at 100 and deducts points for red flags.
    """
    score = 100.0
    
    if forensics.get("is_screen_recapture"):
        score -= 30
    if forensics.get("has_ui_elements"):
        score -= 20
    if forensics.get("has_watermarks"):
        score -= 10
    if forensics.get("shadows_inconsistent"):
        score -= 15
    if forensics.get("multiple_light_sources"):
        score -= 10
    if forensics.get("is_blurry"):
        score -= 5
    if (forensics.get("image_quality") or "").lower() == "low":
        score -= 10
    
    return max(0.0, score)


def _build_pre_existing_description(damage: Dict[str, Any]) -> str:
    """
    Build a human-readable description of pre-existing damage indicators.
    """
    parts = []
    
    if damage.get("is_rust_present"):
        locs = damage.get("rust_locations", [])
        if locs:
            parts.append(f"Rust detected on {', '.join(locs)}")
        else:
            parts.append("Rust detected on damaged area")
    
    if damage.get("is_dirt_in_damage"):
        parts.append("Dirt accumulation found inside damaged area, suggesting the damage is not recent")
    
    if damage.get("is_paint_faded_around_damage"):
        parts.append("Paint fading observed around the damaged area, indicating prolonged exposure")
    
    return ". ".join(parts) + "." if parts else None


def _compute_pre_existing_confidence(damage: Dict[str, Any]) -> float:
    """
    Compute a confidence percentage based on how many pre-existing indicators are present.
    """
    indicators = [
        damage.get("is_rust_present", False),
        damage.get("is_dirt_in_damage", False),
        damage.get("is_paint_faded_around_damage", False),
    ]
    count = sum(1 for i in indicators if i)
    if count == 0:
        return None
    # 1 indicator = 40%, 2 = 70%, 3 = 95%
    return {1: 40.0, 2: 70.0, 3: 95.0}[count]


def _compute_plate_match(detected_plate: str, policy_data: Dict[str, Any] = None) -> str:
    """
    Compare detected plate text against policy vehicle registration.
    Returns MATCH, MISMATCH, or UNKNOWN.
    """
    if not detected_plate:
        return "UNKNOWN"
    if not policy_data or not policy_data.get("vehicle_registration"):
        return "UNKNOWN"
    
    # Normalize: strip spaces, dashes, uppercase
    norm_detected = detected_plate.upper().replace(" ", "").replace("-", "")
    norm_policy = policy_data["vehicle_registration"].upper().replace(" ", "").replace("-", "")
    
    if norm_detected == norm_policy:
        return "MATCH"
    # Partial match — if one contains the other (handles OCR truncation)
    elif norm_detected in norm_policy or norm_policy in norm_detected:
        return "MATCH"
    else:
        return "MISMATCH"
