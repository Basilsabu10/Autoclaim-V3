"""
Unit tests for the VerificationRules engine.

Each test builds a minimal ai_analysis dict that triggers (or passes)
a specific rule, then asserts on the VerificationResult status/failures.
No DB or HTTP calls — pure unit tests.
"""

import pytest
from datetime import datetime, timedelta
from app.services.verification_rules import VerificationRules, RuleConfig


# Convenience helpers
def make_ai(**overrides) -> dict:
    """
    Return a 'clean' ai_analysis dict that passes all checks by default.
    Override only the specific sub-dict keys you need — other sibling keys
    in the same section are preserved through a deep merge.
    """
    base = {
        "forensic_indicators": {
            "is_screen_recapture": False,
            "has_ui_elements": False,
            "is_blurry": False,
            "image_quality": "high",
            "fraud_detected": False,
            "fraud_indicators": [],
            "is_rust_present": False,
            "has_watermarks": False,
        },
        "exif_metadata": {
            "timestamp": "2025-01-15T10:30:00",
            "gps_coordinates": {"latitude": 10.0, "longitude": 76.0},
            "location_name": "ernakulam, kerala",
            "anomalies": [],
        },
        "authenticity_indicators": {
            "stock_photo_likelihood": "low",
            "editing_detected": False,
            "compression_uniform": True,
        },
        "vehicle_identification": {
            "make": "Toyota",
            "model": "Innova",
            "color": "white",
            "detected_confidence": 0.92,
            "license_plate_obscured": False,
        },
        "ocr_data": {
            "plate_text": "KL01AB1234",
            "confidence": 0.95,
            "chase_number": "",
            "chase_number_confidence": 0.0,
        },
        "pre_existing_indicators": {
            "rust_detected": False,
            "old_repairs_visible": False,
        },
        "yolo_results": {
            "yolo_damage_detected": True,
        },
        "damage_assessment": {
            "ai_severity": "moderate",
            "severity_score": 5.0,
            "airbags_deployed": False,
            "fluid_leaks_visible": False,
            "parts_missing": False,
        },
        "narrative_consistency": {
            "visual_evidence_matches": True,
            "inconsistencies": [],
        },
        "multi_image_consistency": {
            "consistent": True,
            "issues": [],
        },
    }
    # Deep-merge: merge sub-dict keys individually so only specified keys
    # are overridden; siblings that were not specified remain at defaults.
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            # Merge only the keys provided; keep the rest from base
            merged = dict(base[k])       # shallow copy of base section
            merged.update(v)             # apply only the caller's overrides
            base[k] = merged
        else:
            base[k] = v
    return base


CLEAN_POLICY = {
    "vehicle_make": "Toyota",
    "vehicle_model": "Innova",
    "vehicle_color": "white",
    "vehicle_registration": "KL01AB1234",
    "chase_number": "",
    "status": "active",
    # Only numeric coverage so rule-15 can do int comparison without TypeError.
    # (The rule does plan_coverage OR coverage_amount — a truthy string would win.)
    "coverage_amount": 500_000,
    "location": "ernakulam",
    "start_date": (datetime.now() - timedelta(days=365)).isoformat(),
    "end_date": (datetime.now() + timedelta(days=365)).isoformat(),
}


def run(ai=None, policy=None, amount=10_000, history=None, accident_date=None):
    engine = VerificationRules()
    return engine.verify_claim(
        claim_amount=amount,
        ai_analysis=ai or make_ai(),
        policy_data=policy or CLEAN_POLICY,
        history=history or [],
        accident_date=accident_date,
    )


def failed_rule_ids(result) -> set:
    return {f["rule_id"] for f in result.to_dict()["failed_checks"]}


# =========================================================================== #
# CHECK 1 — Image Quality Gate                                                 #
# =========================================================================== #

class TestImageQualityGate:

    def test_screen_recapture_is_critical(self):
        ai = make_ai(forensic_indicators={"is_screen_recapture": True})
        result = run(ai=ai)
        assert result.status == "REJECTED"
        assert "SCREEN_RECAPTURE" in failed_rule_ids(result)

    def test_blurry_image_flagged(self):
        ai = make_ai(forensic_indicators={"is_blurry": True})
        result = run(ai=ai)
        assert "IMAGE_BLURRY" in failed_rule_ids(result)

    def test_low_quality_medium_severity(self):
        ai = make_ai(forensic_indicators={"image_quality": "low"})
        result = run(ai=ai)
        checks = {f["rule_id"]: f["severity"] for f in result.to_dict()["failed_checks"]}
        assert "IMAGE_LOW_QUALITY" in checks
        assert checks["IMAGE_LOW_QUALITY"] == "MEDIUM"

    def test_clean_image_passes(self):
        result = run()
        assert "IMAGE_QUALITY_OK" in result.passed_checks


# =========================================================================== #
# CHECK 2 — Metadata Verification                                             #
# =========================================================================== #

class TestMetadataVerification:

    def test_missing_timestamp_flagged(self):
        ai = make_ai(exif_metadata={"timestamp": None, "gps_coordinates": {}, "anomalies": []})
        result = run(ai=ai)
        assert "METADATA_MISSING" in failed_rule_ids(result)

    def test_gps_location_mismatch_flagged(self):
        ai = make_ai(exif_metadata={
            "timestamp": "2025-01-15T10:30:00",
            "gps_coordinates": {"latitude": 28.0, "longitude": 77.0},
            "location_name": "new delhi, delhi",
            "anomalies": [],
        })
        policy = {**CLEAN_POLICY, "location": "ernakulam"}
        result = run(ai=ai, policy=policy)
        assert "GPS_LOCATION_MISMATCH" in failed_rule_ids(result)

    def test_missing_gps_is_low_severity(self):
        ai = make_ai(exif_metadata={
            "timestamp": "2025-01-15T10:30:00",
            "gps_coordinates": {},
            "anomalies": [],
        })
        result = run(ai=ai)
        checks = {f["rule_id"]: f["severity"] for f in result.to_dict()["failed_checks"]}
        assert checks.get("GPS_MISSING") == "LOW"


# =========================================================================== #
# CHECK 3 — Stock Photo Detection                                             #
# =========================================================================== #

class TestStockPhotoDetection:

    def test_high_stock_likelihood_is_critical(self):
        ai = make_ai(authenticity_indicators={"stock_photo_likelihood": "high"})
        result = run(ai=ai)
        assert "STOCK_PHOTO_DETECTED" in failed_rule_ids(result)
        assert result.status == "REJECTED"

    def test_medium_stock_likelihood_is_medium(self):
        ai = make_ai(authenticity_indicators={"stock_photo_likelihood": "medium"})
        result = run(ai=ai)
        checks = {f["rule_id"]: f["severity"] for f in result.to_dict()["failed_checks"]}
        assert "STOCK_PHOTO_SUSPICIOUS" in checks

    def test_low_stock_likelihood_passes(self):
        result = run()
        assert "REVERSE_IMAGE_SEARCH" in result.passed_checks


# =========================================================================== #
# CHECK 4 — Digital Forgery                                                    #
# =========================================================================== #

class TestDigitalForgery:

    def test_ela_manipulation_critical(self):
        ai = make_ai(forensic_indicators={
            "fraud_indicators": ["MANIPULATED OR GENERATED IMAGE"],
        })
        result = run(ai=ai)
        assert "IMAGE_MANIPULATION_ELA" in failed_rule_ids(result)

    def test_missing_exif_fired_only_without_timestamp(self):
        """MISSING_EXIF_DATA must NOT fire if a timestamp exists."""
        ai = make_ai(exif_metadata={
            "timestamp": "2025-01-15T10:30:00",
            "anomalies": ["NO_CAMERA_MAKE", "NO_CAPTURE_TIMESTAMP"],
            "gps_coordinates": {},
        })
        result = run(ai=ai)
        assert "MISSING_EXIF_DATA" not in failed_rule_ids(result)

    def test_missing_exif_fired_when_no_timestamp(self):
        """MISSING_EXIF_DATA fires when timestamp is absent."""
        ai = make_ai(exif_metadata={
            "timestamp": None,
            "anomalies": ["NO_CAMERA_MAKE", "NO_CAPTURE_TIMESTAMP"],
            "gps_coordinates": {},
        })
        result = run(ai=ai)
        assert "MISSING_EXIF_DATA" in failed_rule_ids(result)

    def test_watermark_detected(self):
        ai = make_ai(forensic_indicators={"has_watermarks": True})
        result = run(ai=ai)
        assert "WATERMARKS_DETECTED" in failed_rule_ids(result)


# =========================================================================== #
# CHECK 6 — License Plate Match                                               #
# =========================================================================== #

class TestLicensePlateMatch:

    def test_plate_match_passes(self):
        result = run()
        assert "LICENSE_PLATE" in result.passed_checks

    def test_plate_mismatch_is_critical(self):
        ai = make_ai(ocr_data={"plate_text": "KL99ZZ9999", "confidence": 0.95})
        result = run(ai=ai)
        assert "PLATE_MISMATCH" in failed_rule_ids(result)
        assert result.status == "REJECTED"

    def test_no_plate_detected_is_high(self):
        ai = make_ai(ocr_data={"plate_text": "", "confidence": 0.0})
        result = run(ai=ai)
        checks = {f["rule_id"]: f["severity"] for f in result.to_dict()["failed_checks"]}
        assert "PLATE_NOT_DETECTED" in checks
        assert checks["PLATE_NOT_DETECTED"] == "HIGH"

    def test_low_confidence_ocr_flagged(self):
        ai = make_ai(ocr_data={"plate_text": "KL01AB1234", "confidence": 0.50})
        result = run(ai=ai)
        assert "PLATE_LOW_CONFIDENCE" in failed_rule_ids(result)


# =========================================================================== #
# CHECK 8 — Pre-Existing Damage                                               #
# =========================================================================== #

class TestPreExistingDamage:

    def test_rust_detected_fails(self):
        ai = make_ai(pre_existing_indicators={"rust_detected": True})
        result = run(ai=ai)
        assert "PRE_EXISTING_DAMAGE" in failed_rule_ids(result)

    def test_old_repairs_detected_fails(self):
        ai = make_ai(pre_existing_indicators={"old_repairs_visible": True})
        result = run(ai=ai)
        assert "PRE_EXISTING_DAMAGE" in failed_rule_ids(result)

    def test_clean_vehicle_passes(self):
        result = run()
        assert "PRE_EXISTING_DAMAGE" in result.passed_checks


# =========================================================================== #
# CHECK 9 — YOLO Damage Corroboration                                         #
# =========================================================================== #

class TestYoloDamageCorroboration:

    def test_no_yolo_damage_is_critical(self):
        ai = make_ai(yolo_results={"yolo_damage_detected": False})
        result = run(ai=ai)
        assert "YOLO_NO_DAMAGE_DETECTED" in failed_rule_ids(result)
        assert result.status == "REJECTED"

    def test_yolo_damage_detected_passes(self):
        result = run()
        assert "YOLO_DAMAGE_DETECTED" in result.passed_checks


# =========================================================================== #
# CHECK 10 — Totalled Vehicle Markers                                         #
# =========================================================================== #

class TestTotalledVehicleMarkers:

    def test_totaled_no_markers_flagged(self):
        ai = make_ai(damage_assessment={
            "ai_severity": "totaled",
            "severity_score": 9.8,
            "airbags_deployed": False,
            "fluid_leaks_visible": False,
            "parts_missing": False,
        })
        result = run(ai=ai)
        assert "TOTALED_NO_PHYSICAL_MARKERS" in failed_rule_ids(result)

    def test_totaled_with_airbags_passes(self):
        ai = make_ai(damage_assessment={
            "ai_severity": "totaled",
            "severity_score": 9.8,
            "airbags_deployed": True,
            "fluid_leaks_visible": False,
            "parts_missing": False,
        })
        result = run(ai=ai)
        assert "TOTALED_MARKERS_PRESENT" in result.passed_checks

    def test_severe_but_not_totaled_passes(self):
        ai = make_ai(damage_assessment={
            "ai_severity": "severe",
            "severity_score": 8.0,
            "airbags_deployed": False,
            "fluid_leaks_visible": False,
            "parts_missing": False,
        })
        result = run(ai=ai)
        assert "TOTALED_NO_PHYSICAL_MARKERS" not in failed_rule_ids(result)


# =========================================================================== #
# CHECK 11 — Narrative Consistency                                             #
# =========================================================================== #

class TestNarrativeConsistency:

    def test_narrative_mismatch_flagged(self):
        ai = make_ai(narrative_consistency={
            "visual_evidence_matches": False,
            "inconsistencies": ["Claimed front damage but only rear damage visible"],
        })
        result = run(ai=ai)
        assert "NARRATIVE_MISMATCH" in failed_rule_ids(result)

    def test_consistent_narrative_passes(self):
        result = run()
        assert "NARRATIVE_CONSISTENCY" in result.passed_checks


# =========================================================================== #
# Final Decision — APPROVED / FLAGGED / REJECTED                              #
# =========================================================================== #

class TestFinalDecision:

    def test_clean_claim_approved(self):
        """A perfectly clean claim below auto-approval threshold is APPROVED."""
        result = run(amount=5_000)
        assert result.status == "APPROVED"
        assert result.auto_approved is True

    def test_high_amount_requires_review(self):
        """Amount above threshold always requires human review."""
        result = run(amount=50_000)
        assert result.requires_human_review is True

    def test_critical_failure_always_rejects(self):
        """Any CRITICAL failure → REJECTED regardless of amount."""
        ai = make_ai(authenticity_indicators={"stock_photo_likelihood": "high"})
        result = run(ai=ai, amount=1_000)
        assert result.status == "REJECTED"

    def test_result_has_confidence_score(self):
        result = run()
        d = result.to_dict()
        assert 0 <= d["confidence_score"] <= 100

    def test_result_to_dict_serializable(self):
        """to_dict() must return only JSON-safe types."""
        import json
        result = run()
        # Should not raise
        json.dumps(result.to_dict())
