"""
Rule-Based Verification Engine for AutoClaim — v2.0
Deterministic decision logic for claim approval / flagging / rejection.

DESIGN PRINCIPLES
-----------------
1. AI only extracts structured facts — it NEVER makes decisions.
2. Every decision is auditable: rule ID, reason, severity, score.
3. Rules are grouped into phases matching the SRS (FR-2.x).
4. New rules added in v2.0 are clearly marked with # NEW.
5. Thresholds live in RuleConfig so they can be tuned without touching logic.

DECISION MATRIX
---------------
APPROVED     → no failures, OR only LOW severity (score < FLAG_THRESHOLD)
FLAGGED      → score >= FLAG_THRESHOLD but < REJECT_THRESHOLD
REJECTED     → any CRITICAL failure, OR score >= REJECT_THRESHOLD
MONITORED    → approved with only LOW issues (score 1 – FLAG_THRESHOLD-1)

v2.0 additions vs v1.x
-----------------------
• CHECK 9  – Image Quality Gate            (blocks blurry/screen-recaptures early)
• CHECK 10 – YOLO Damage Corroboration     (cross-validates AI vs rule-based)
• CHECK 11 – Damage-Severity vs Cost Sanity (catches inflated estimates)
• CHECK 12 – Multi-Image Consistency       (detects mixed-incident photos)
• CHECK 13 – Policy Active & Coverage Gate (verifies policy is valid/covers event)
• CHECK 14 – Airbag/Fluid Totalled-Vehicle (flags totalled claims missing markers)
• CHECK 15 – Duplicate / Repeat-Claim Guard (fraud ring detection)
• Refined scoring: compounding multiplier for correlated failures
• Weighted confidence score (0-100) returned alongside binary decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import math



# CONFIGURATION
#

@dataclass
class RuleConfig:
    

    # ── Amount threshold ────────────────────────────────────────────────────
    AUTO_APPROVAL_AMOUNT_THRESHOLD: int = 20_000   # ₹ 20,000

    # ── Confidence thresholds ───────────────────────────────────────────────
    MIN_VEHICLE_DETECTION_CONFIDENCE: float = 0.60
    MIN_OCR_PLATE_CONFIDENCE: float = 0.80
    MIN_CHASE_NUMBER_CONFIDENCE: float = 0.75
    MIN_OVERALL_IMAGE_QUALITY_SCORE: float = 0.40  # NEW: below = reject image

    # ── Severity weights ────────────────────────────────────────────────────
    SEVERITY_WEIGHTS: Dict[str, int] = field(default_factory=lambda: {
        "CRITICAL": 10,
        "HIGH":      5,
        "MEDIUM":    2,
        "LOW":       1,
    })

    # ── Decision thresholds ─────────────────────────────────────────────────
    AUTO_REJECT_SCORE_THRESHOLD: int = 10   # score >= 10 → REJECTED
    FLAG_FOR_REVIEW_SCORE_THRESHOLD: int = 2  # score >= 2  → FLAGGED

    # ── Stock-photo ─────────────────────────────────────────────────────────
    STOCK_PHOTO_REJECT_LEVELS: List[str] = field(
        default_factory=lambda: ["high", "very_high"]
    )

    # ── Damage–cost sanity ──────────────────────────────────────────────────
    # NEW: maximum ₹ per panel per damage type before flagging as inflated
    COST_PER_PANEL_LIMITS: Dict[str, int] = field(default_factory=lambda: {
        "none":     0,
        "minor":    15_000,
        "moderate": 60_000,
        "severe":   1_50_000,
        "totaled":  10_00_000,
    })
    # NEW: maximum allowed ratio of claim_amount / AI estimated max before flag
    MAX_CLAIM_TO_ESTIMATE_RATIO: float = 2.0

    # ── Severity corroboration ──────────────────────────────────────────────
    # NEW: YOLO and AI must agree on severity; weight of disagreement
    YOLO_AI_SEVERITY_MISMATCH_PENALTY: int = 3   # added directly to score

    # ── Duplicate guard ─────────────────────────────────────────────────────
    # NEW: within how many days the same plate + user triggers duplication flag
    DUPLICATE_CLAIM_WINDOW_DAYS: int = 30

    # ── Accident date ───────────────────────────────────────────────────────
    # NEW: maximum allowed days between accident date and image timestamp
    MAX_DAYS_BETWEEN_ACCIDENT_AND_IMAGE: int = 14

    # ── Compounding multiplier ──────────────────────────────────────────────
    # NEW: if >= N distinct HIGH/CRITICAL failures, multiply score
    COMPOUND_FAILURE_THRESHOLD: int = 3
    COMPOUND_MULTIPLIER: float = 1.5



# RESULT TYPES


@dataclass
class FailedRule:
    rule_id: str
    rule_name: str
    reason: str
    severity: str       # CRITICAL | HIGH | MEDIUM | LOW
    phase: str          


@dataclass
class VerificationResult:
    status: str                          # APPROVED | FLAGGED | REJECTED
    decision_reason: str
    confidence_level: str                # HIGH | MEDIUM | LOW
    confidence_score: float              # 0 – 100 (weighted)
    auto_approved: bool
    requires_human_review: bool
    requires_monitoring: bool
    severity_score: float
    passed_checks: List[str]
    failed_checks: List[FailedRule]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "decision_reason": self.decision_reason,
            "confidence_level": self.confidence_level,
            "confidence_score": round(self.confidence_score, 2),
            "auto_approved": self.auto_approved,
            "requires_human_review": self.requires_human_review,
            "requires_monitoring": self.requires_monitoring,
            "passed_checks_count": len(self.passed_checks),
            "failed_checks_count": len(self.failed_checks),
            "severity_score": round(self.severity_score, 2),
            "passed_checks": self.passed_checks,
            "failed_checks": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "reason": r.reason,
                    "severity": r.severity,
                    "phase": r.phase,
                }
                for r in self.failed_checks
            ],
            "timestamp": self.timestamp,
        }



# MAIN ENGINE
# ===========================================================================

class VerificationRules:
    

    def __init__(self, config: Optional[RuleConfig] = None) -> None:
        self.config = config or RuleConfig()
        self._reset()

    # ── Public API ───────────────────────────────────────────────────────────

    def verify_claim(
        self,
        claim_amount: int,
        ai_analysis: Dict[str, Any],
        policy_data: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        weather_data: Optional[Dict[str, Any]] = None,   # kept for compat
        accident_date: Optional[datetime] = None,
    ) -> VerificationResult:
        """
        Run all verification checks and return a VerificationResult.

        Parameters
        ----------
        claim_amount : int
            Claimed repair/loss amount in ₹.
        ai_analysis : dict
            Structured output from the Groq / YOLO / OCR / EXIF pipeline.
            Expected top-level keys — see _ai() helper for schema.
        policy_data : dict
            Policy row from DB (vehicle_make, vehicle_model,
            vehicle_registration, chase_number, status, plan_coverage,
            location, start_date, end_date, …).
        history : list[dict], optional
            Prior claims for the same user (used for duplicate detection).
        weather_data : dict, optional
            Deprecated — not used; kept for backward compatibility.
        """
        self._reset()

        # ── PHASE A: Integrity & Source Checks ───────────────────────────
        self._check_1_image_quality_gate(ai_analysis)        # NEW (must run first)
        self._check_2_metadata_verification(ai_analysis, policy_data)
        self._check_3_reverse_image_search(ai_analysis)
        self._check_4_digital_forgery(ai_analysis)
        self._check_4_5_sightengine_ai_detection(ai_analysis)

        # ── PHASE B: Vehicle & Damage Verification ────────────────────────
        self._check_5_vehicle_match(ai_analysis, policy_data)
        self._check_6_license_plate_match(ai_analysis, policy_data)
        self._check_7_chase_number_match(ai_analysis, policy_data)
        self._check_8_pre_existing_damage(ai_analysis)
        self._check_9_yolo_damage_corroboration(ai_analysis)
        self._check_10_totalled_vehicle_markers(ai_analysis)   # NEW

        # ── PHASE C: Contextual Consistency ──────────────────────────────
        self._check_11_narrative_consistency(ai_analysis)
        self._check_12_multi_image_consistency(ai_analysis)    # NEW

        # ── PHASE D: Financial Sanity ─────────────────────────────────────
        self._check_13_amount_threshold(claim_amount)
        self._check_14_damage_cost_sanity(claim_amount, ai_analysis)  # NEW

        # ── PHASE E: Policy & History Validation ──────────────────────────
        self._check_15_policy_active_and_coverage(policy_data, claim_amount)  # NEW
        self._check_16_duplicate_claim_guard(ai_analysis, policy_data, history)  # NEW
        self._check_17_accident_date_validation(ai_analysis, accident_date)  # NEW

        # ── Final decision ────────────────────────────────────────────────
        return self._make_final_decision(claim_amount)

    # ── Internal state ───────────────────────────────────────────────────────

    def _reset(self) -> None:
        self._passed: List[str] = []
        self._failed: List[FailedRule] = []
        self._raw_score: float = 0.0

    # ── Accessor helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _ai(analysis: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        """Safe nested dict getter: _ai(d, 'a', 'b') → d['a']['b']"""
        val = analysis
        for k in keys:
            if not isinstance(val, dict):
                return default
            val = val.get(k, default)
        return val

    def _pass(self, rule_id: str) -> None:
        self._passed.append(rule_id)

    def _fail(
        self,
        rule_id: str,
        rule_name: str,
        reason: str,
        severity: str,
        phase: str,
    ) -> None:
        self._failed.append(
            FailedRule(
                rule_id=rule_id,
                rule_name=rule_name,
                reason=reason,
                severity=severity,
                phase=phase,
            )
        )
        self._raw_score += self.config.SEVERITY_WEIGHTS.get(severity, 0)

    # =========================================================================
    # PHASE A — Integrity & Source Checks
    # =========================================================================

    # CHECK 1 (NEW): Image Quality Gate
    # ─────────────────────────────────
    def _check_1_image_quality_gate(self, ai: Dict[str, Any]) -> None:
        """
        Reject or flag images that are too degraded for reliable analysis.

        Checks:
        • is_blurry (ForensicAnalysis field)
        • is_screen_recapture (photo of a photo / screenshot)
        • has_ui_elements (on-screen app artifacts)
        • image_quality (high | medium | low)

        Severity rationale
        ------------------
        Screen-recaptures are CRITICAL because they nullify ALL metadata checks.
        Blurry images are HIGH — they impair every downstream AI check.
        Low quality alone is MEDIUM — analysis can continue with caution.
        """
        is_screen = self._ai(ai, "forensic_indicators", "is_screen_recapture", default=False)
        has_ui    = self._ai(ai, "forensic_indicators", "has_ui_elements",     default=False)
        is_blurry = self._ai(ai, "forensic_indicators", "is_blurry",           default=False)
        quality   = (self._ai(ai, "forensic_indicators", "image_quality", default="high") or "high").lower()

        if is_screen or has_ui:
            self._fail(
                rule_id="SCREEN_RECAPTURE",
                rule_name="Image Quality Gate — Screen Recapture (v2 NEW)",
                reason=(
                    "Image appears to be a screen-capture or photo of a screen. "
                    "EXIF metadata is stripped and AI results are unreliable."
                ),
                severity="CRITICAL",
                phase="A",
            )
            return  # No point checking downstream on a screen-shot

        if is_blurry:
            self._fail(
                rule_id="IMAGE_BLURRY",
                rule_name="Image Quality Gate — Blur Detection (v2 NEW)",
                reason="Image is excessively blurry. Damage and plate recognition are unreliable.",
                severity="HIGH",
                phase="A",
            )
        elif quality == "low":
            self._fail(
                rule_id="IMAGE_LOW_QUALITY",
                rule_name="Image Quality Gate — Low Quality (v2 NEW)",
                reason="Image quality is low. AI analysis may be inaccurate.",
                severity="MEDIUM",
                phase="A",
            )
        else:
            self._pass("IMAGE_QUALITY_OK")

    # CHECK 2: Metadata Verification (FR-2.1)
    # ─────────────────────────────────────────
    def _check_2_metadata_verification(
        self, ai: Dict[str, Any], policy: Dict[str, Any]
    ) -> None:
        """
        Verify EXIF timestamp and GPS coordinates.

        Fails:
        • No timestamp → HIGH (could be edited image)
        • No GPS       → LOW  (common on older phones; not conclusive)
        • GPS mismatch → MEDIUM (location doesn't match policy address)
        """
        exif = ai.get("exif_metadata", {}) or {}

        if not exif.get("timestamp"):
            self._fail(
                "METADATA_MISSING",
                "Metadata Verification (FR-2.1)",
                "No EXIF timestamp — possible screenshot or digitally edited image.",
                "HIGH",
                "A",
            )
        else:
            self._pass("METADATA_TIMESTAMP")

        gps = exif.get("gps_coordinates", {}) or {}
        if gps.get("latitude") and gps.get("longitude"):
            policy_loc   = (policy.get("location") or "").lower()
            detected_loc = (exif.get("location_name") or "").lower()
            if policy_loc and detected_loc:
                if not self._location_matches(policy_loc, detected_loc):
                    self._fail(
                        "GPS_LOCATION_MISMATCH",
                        "GPS Location Verification",
                        f"Location mismatch — Policy: '{policy_loc}', GPS: '{detected_loc}'.",
                        "MEDIUM",
                        "A",
                    )
                else:
                    self._pass("GPS_LOCATION")
            else:
                self._pass("GPS_EXISTS")
        else:
            self._fail(
                "GPS_MISSING",
                "GPS Verification",
                "No GPS coordinates in image metadata.",
                "LOW",
                "A",
            )

    # CHECK 3: Reverse Image Search (FR-2.2)
    # ─────────────────────────────────────────
    def _check_3_reverse_image_search(self, ai: Dict[str, Any]) -> None:
        """Detect stock or recycled internet photos."""
        auth = ai.get("authenticity_indicators", {}) or {}
        likelihood = (auth.get("stock_photo_likelihood") or "unknown").lower()

        if likelihood in self.config.STOCK_PHOTO_REJECT_LEVELS:
            self._fail(
                "STOCK_PHOTO_DETECTED",
                "Reverse Image Search (FR-2.2)",
                f"Image highly likely to be a stock/internet photo (likelihood: {likelihood}).",
                "CRITICAL",
                "A",
            )
        elif likelihood == "medium":
            self._fail(
                "STOCK_PHOTO_SUSPICIOUS",
                "Stock Photo Check (FR-2.2)",
                "Image has stock-photo characteristics — original source unconfirmed.",
                "MEDIUM",
                "A",
            )
        else:
            self._pass("REVERSE_IMAGE_SEARCH")

    # CHECK 4: Digital Forgery Detection (FR-2.3)
    # ─────────────────────────────────────────────
    def _check_4_digital_forgery(self, ai: Dict[str, Any]) -> None:
        """
        Detect digital manipulation: editing software artifacts,
        compression anomalies, watermarks, and AI generation markers.
        """
        auth = ai.get("authenticity_indicators", {}) or {}
        forensic = ai.get("forensic_indicators", {}) or {}
        exif = ai.get("exif_metadata", {}) or {}
        indicators = forensic.get("fraud_indicators", [])

        # 1. Critical Editing & Manipulation Check
        if "MANIPULATED OR GENERATED IMAGE" in indicators:
            self._fail(
                "IMAGE_MANIPULATION_ELA",
                "Digital Forgery Detection — Error Level Analysis",
                "High Error Level Analysis (ELA) score indicates the image has been digitally manipulated or artificially generated.",
                "CRITICAL",
                "A",
            )
        elif auth.get("editing_detected", False) or forensic.get("fraud_detected", False):
            self._fail(
                "DIGITAL_EDITING",
                "Digital Forgery Detection — Software Manipulation",
                "Direct evidence of digital editing or fraud detected.",
                "CRITICAL",
                "A",
            )

        # 2. EXIF Anomalies (AI Generator detection)
        anomalies = exif.get("anomalies", [])
        has_missing_exif = False
        for anomaly in anomalies:
            if "AI_SOFTWARE_TAG" in anomaly:
                self._fail(
                    "AI_GENERATED_IMAGE",
                    "Digital Forgery Detection — AI Generation",
                    f"AI generator software detected in metadata: {anomaly}.",
                    "CRITICAL",
                    "A",
                )
            elif anomaly in ("NO_CAMERA_MAKE", "NO_CAPTURE_TIMESTAMP"):
                has_missing_exif = True

        # Only fire MISSING_EXIF_DATA if there is genuinely no timestamp.
        # If a timestamp was found in EXIF, the image came from a real camera
        # session and should not be penalised for missing EXIF, even if the
        # anomalies list contains NO_CAPTURE_TIMESTAMP (e.g. a secondary anomaly
        # tag that doesn't reflect the primary timestamp field).
        has_timestamp = bool(exif.get("timestamp"))
        if has_missing_exif and not has_timestamp:
            self._fail(
                "MISSING_EXIF_DATA",
                "Digital Forgery Detection — Missing EXIF",
                "Missing core EXIF data (Make/Timestamp) common in AI generated or stripped images.",
                "MEDIUM",
                "A",
            )

        # 3. Compression & Watermarks
        if not auth.get("compression_uniform", True):
            self._fail(
                "NON_UNIFORM_COMPRESSION",
                "Digital Forgery Detection — Compression Analysis",
                "Non-uniform compression artifacts detected, suggesting possible local editing.",
                "HIGH",
                "A",
            )
        
        if forensic.get("has_watermarks", False):
            self._fail(
                "WATERMARKS_DETECTED",
                "Digital Forgery Detection — Watermarks",
                "Watermarks or brand overlays detected (possible recycled internet media-assets).",
                "HIGH",
                "A",
            )

        if not self._failed_rule_exists("DIGITAL_EDITING") and \
           not self._failed_rule_exists("AI_GENERATED_IMAGE") and \
           not self._failed_rule_exists("MISSING_EXIF_DATA") and \
           not self._failed_rule_exists("NON_UNIFORM_COMPRESSION") and \
           not self._failed_rule_exists("WATERMARKS_DETECTED"):
            self._pass("DIGITAL_FORGERY_CHECK")

    def _failed_rule_exists(self, rule_id: str) -> bool:
        """Helper to check if a specific rule has already failed."""
        return any(f.rule_id == rule_id for f in self._failed)

    # CHECK 4.5 (NEW): Sightengine AI-Generated Image Detection
    # ───────────────────────────────────────────────────────
    def _check_4_5_sightengine_ai_detection(self, ai: Dict[str, Any]) -> None:
        """
        Reject claims where Sightengine AI detector flags image as
        synthetically generated (score > 0.85).

        Severity: CRITICAL — synthetic images nullify all downstream checks.
        Skips silently if API was not available (success=False).
        """
        sight = ai.get("ai_detection", {}) or {}

        if not sight.get("success"):
            # API not configured or failed — give benefit of the doubt
            self._pass("SIGHTENGINE_AI_DETECTION_SKIPPED")
            return

        if sight.get("ai_generated") and float(sight.get("max_ai_score", 0) or 0) > 0.85:
            score = float(sight.get("max_ai_score", 0))
            self._fail(
                rule_id="AI_GENERATED_IMAGE_SIGHTENGINE",
                rule_name="Sightengine AI-Generated Image Detection (NEW)",
                reason=(
                    f"Sightengine AI detector flagged claim image as "
                    f"synthetically generated (score: {score:.2f}). "
                    f"Image is highly likely to be AI-generated and not a real photograph."
                ),
                severity="CRITICAL",
                phase="A",
            )
        else:
            self._pass("SIGHTENGINE_AI_DETECTION_OK")

    # =========================================================================
    # PHASE B — Vehicle & Damage Verification
    # =========================================================================

    # CHECK 5: Vehicle Match (FR-2.4)
    # ──────────────────────────────────
    def _check_5_vehicle_match(
        self, ai: Dict[str, Any], policy: Dict[str, Any]
    ) -> None:
        """Confirm make/model in image matches the insured vehicle."""
        detected   = ai.get("vehicle_identification", {}) or {}
        p_make     = (policy.get("vehicle_make")  or "").lower()
        p_model    = (policy.get("vehicle_model") or "").lower()
        d_make     = (detected.get("make")  or "").lower()
        d_model    = (detected.get("model") or "").lower()
        confidence = detected.get("detected_confidence") or 0.0

        # v2: also check vehicle_color consistency if policy stores it
        p_color = (policy.get("vehicle_color") or "").lower()
        d_color = (detected.get("color") or "").lower()

        make_ok  = bool(p_make)  and (p_make in d_make  or d_make in p_make)
        model_ok = bool(p_model) and (p_model in d_model or d_model in p_model)

        # NEW: Check if the license plate was successfully extracted and matches policy
        ocr         = ai.get("ocr_data", {}) or {}
        raw_text    = ocr.get("plate_text") or ""
        ocr_text    = raw_text.upper().replace(" ", "").replace("-", "")
        policy_plate = (
            (policy.get("vehicle_registration") or "")
            .upper().replace(" ", "").replace("-", "")
        )
        plate_match = bool(ocr_text) and bool(policy_plate) and ocr_text == policy_plate

        # REDEFINED: Only flag low confidence or mismatch if BOTH fail (Lenient v3.0)
        # SUPREME LENIENCY: If the exact license plate matches, bypass the vehicle match check entirely.
        if plate_match:
            self._pass("VEHICLE_MATCH_BYPASSED_BY_PLATE_MATCH")
        elif not (make_ok or model_ok):
            # Guard: if make+model are both absent AND confidence is 0, the AI simply
            # could not extract vehicle identity (e.g. YOLO-only mode, Groq unavailable).
            # Treat as "unverifiable" rather than a mismatch — prevents false positives.
            identity_not_extracted = not d_make and not d_model and confidence == 0.0
            if identity_not_extracted:
                self._pass("VEHICLE_MATCH_IDENTITY_NOT_AVAILABLE")
            else:
                if confidence < self.config.MIN_VEHICLE_DETECTION_CONFIDENCE:
                    self._fail(
                        "VEHICLE_LOW_CONFIDENCE",
                        "Vehicle Detection Confidence",
                        (
                            f"Vehicle ID confidence {confidence*100:.0f}% is low and "
                            f"neither brand nor model match policy data."
                        ),
                        "MEDIUM",
                        "B",
                    )

                self._fail(
                    "VEHICLE_MISMATCH",
                    "Vehicle Match (FR-2.4)",
                    (
                        f"Vehicle mismatch — Policy: {p_make} {p_model}, "
                        f"Detected: {d_make} {d_model}. Neither brand nor model could be verified."
                    ),
                    "CRITICAL",
                    "B",
                )
        else:
            self._pass("VEHICLE_MATCH")

        # NEW: color check (MEDIUM — AI color detection is approximate)
        if p_color and d_color and p_color not in d_color and d_color not in p_color:
            self._fail(
                "VEHICLE_COLOR_MISMATCH",
                "Vehicle Color Verification (v2 NEW)",
                f"Color mismatch — Policy: {p_color}, Detected: {d_color}.",
                "MEDIUM",
                "B",
            )

    # CHECK 6: License Plate Match (FR-2.5)
    # ───────────────────────────────────────
    def _check_6_license_plate_match(
        self, ai: Dict[str, Any], policy: Dict[str, Any]
    ) -> None:
        """Strict exact OCR match against policy registration."""
        ocr         = ai.get("ocr_data", {}) or {}
        raw_text    = ocr.get("plate_text") or ""
        ocr_text    = raw_text.upper().replace(" ", "").replace("-", "")
        ocr_conf    = ocr.get("confidence") or 0.0
        policy_plate = (
            (policy.get("vehicle_registration") or "")
            .upper().replace(" ", "").replace("-", "")
        )
        plate_obscured = self._ai(ai, "vehicle_identification", "license_plate_obscured",
                                  default=False)

        if not ocr_text:
            severity = "HIGH" if not plate_obscured else "MEDIUM"
            self._fail(
                "PLATE_NOT_DETECTED",
                "License Plate Detection (FR-2.5)",
                (
                    "License plate not visible or unreadable"
                    + (" (plate may be obscured)." if plate_obscured else ".")
                ),
                severity,
                "B",
            )
            return

        if ocr_conf < self.config.MIN_OCR_PLATE_CONFIDENCE:
            self._fail(
                "PLATE_LOW_CONFIDENCE",
                "License Plate OCR Confidence",
                (
                    f"OCR confidence {ocr_conf*100:.0f}% below threshold "
                    f"{self.config.MIN_OCR_PLATE_CONFIDENCE*100:.0f}%."
                ),
                "MEDIUM",
                "B",
            )

        if policy_plate and ocr_text != policy_plate:
            self._fail(
                "PLATE_MISMATCH",
                "License Plate Verification (FR-2.5)",
                f"Plate mismatch — Policy: {policy_plate}, OCR: {ocr_text}.",
                "CRITICAL",
                "B",
            )
        else:
            self._pass("LICENSE_PLATE")

    # CHECK 7: Chase Number (VIN) Verification (FR-2.8 / original check 8)
    # ───────────────────────────────────────────────────────────────────────
    def _check_7_chase_number_match(
        self, ai: Dict[str, Any], policy: Dict[str, Any]
    ) -> None:
        """Chase / VIN number exact match."""
        ocr         = ai.get("ocr_data", {}) or {}
        ocr_chase   = (ocr.get("chase_number") or "").upper().strip()
        chase_conf  = ocr.get("chase_number_confidence") or 0.0
        policy_chase = (policy.get("chase_number") or "").upper().strip()

        if not ocr_chase:
            self._pass("CHASE_NUMBER_NOT_PROVIDED")
            return

        if chase_conf < self.config.MIN_CHASE_NUMBER_CONFIDENCE:
            self._fail(
                "CHASE_NUMBER_LOW_CONFIDENCE",
                "Chase Number OCR Confidence",
                (
                    f"Chase number OCR confidence {chase_conf*100:.0f}% below "
                    f"threshold {self.config.MIN_CHASE_NUMBER_CONFIDENCE*100:.0f}%."
                ),
                "MEDIUM",
                "B",
            )

        if policy_chase and ocr_chase != policy_chase:
            self._fail(
                "CHASE_NUMBER_MISMATCH",
                "Chase Number Verification (FR-2.8)",
                f"Chase number mismatch — Policy: {policy_chase}, OCR: {ocr_chase}.",
                "HIGH",
                "B",
            )
        else:
            self._pass("CHASE_NUMBER_MATCH")

    # CHECK 8: Pre-Existing Damage (FR-2.6)
    # ───────────────────────────────────────
    def _check_8_pre_existing_damage(self, ai: Dict[str, Any]) -> None:
        """Detect rust, paint fading, old repairs — indicators of prior damage."""
        pre = ai.get("pre_existing_indicators", {}) or {}
        # Also read directly from ForensicAnalysis flat fields
        forensic = ai.get("forensic_indicators", {}) or {}

        indicators: List[str] = []
        if pre.get("rust_detected") or forensic.get("is_rust_present"):
            indicators.append("rust in damaged area")
        # Paint fading and dirt accumulation removed — not reliable pre-existing indicators
        if pre.get("old_repairs_visible"):
            indicators.append("evidence of previous repairs")

        if indicators:
            self._fail(
                "PRE_EXISTING_DAMAGE",
                "Pre-Existing Damage Detection (FR-2.6)",
                f"Pre-existing damage indicators: {', '.join(indicators)}.",
                "HIGH",
                "B",
            )
        else:
            self._pass("PRE_EXISTING_DAMAGE")

    # CHECK 9: YOLO Damage Required
    # ────────────────────────────────────────────────────
    def _check_9_yolo_damage_corroboration(self, ai: Dict[str, Any]) -> None:
        """
        Instantly reject the claim if YOLO does not detect any damage.
        """
        yolo_results = ai.get("yolo_results", {}) or {}
        yolo_damage_detected = yolo_results.get("yolo_damage_detected", False)
        
        if not yolo_damage_detected:
            self._fail(
                "YOLO_NO_DAMAGE_DETECTED",
                "YOLO Damage Detection (v2.1 NEW)",
                "YOLO model did not detect any damage in the provided images.",
                "CRITICAL",
                "B",
            )
        else:
            self._pass("YOLO_DAMAGE_DETECTED")

    # CHECK 10 (NEW): Totalled-Vehicle Marker Validation
    # ────────────────────────────────────────────────────
    def _check_10_totalled_vehicle_markers(self, ai: Dict[str, Any]) -> None:
        """
        Structural damage is confirmed primarily by Groq's physical marker detection:
          • airbags_deployed  — Groq sees deployed airbag fabric in the image
          • fluid_leaks_visible — Groq sees liquid pooling/drips under/around vehicle

        TOTALED_NO_PHYSICAL_MARKERS fires when:
          - YOLO severity is 'totaled' (score >= 9.5 / 10  i.e. 95%)
          - AND neither airbags nor fluid leaks are visible

        Below 9.5 YOLO score → always PASS (classified as 'severe' max, not totaled).
        """
        ai_severity    = (self._ai(ai, "damage_assessment", "ai_severity") or "none").lower()
        severity_score = float(self._ai(ai, "damage_assessment", "severity_score", default=0) or 0)
        airbags        = self._ai(ai, "damage_assessment", "airbags_deployed",    default=False)
        fluid_leaks    = self._ai(ai, "damage_assessment", "fluid_leaks_visible", default=False)
        parts_missing  = self._ai(ai, "damage_assessment", "parts_missing",       default=False)

        # Physical markers found → always pass, regardless of severity label
        physical_markers = []
        if airbags:       physical_markers.append("airbag deployment")
        if fluid_leaks:   physical_markers.append("fluid leaks")
        if parts_missing: physical_markers.append("missing parts")

        if physical_markers:
            self._pass("TOTALED_MARKERS_PRESENT")
            return

        # Only fire if severity is both labeled 'totaled' AND score confirms 95%+
        if ai_severity == "totaled" and severity_score >= 9.5:
            self._fail(
                "TOTALED_NO_PHYSICAL_MARKERS",
                "Totalled Vehicle — No Physical Markers Detected",
                (
                    f"YOLO severity 'totaled' at {severity_score:.1f}/10 (≥95%) but "
                    "no physical markers (airbag deployment, fluid leaks, missing parts) "
                    "are visible. HIGH likelihood of severity inflation or staged damage."
                ),
                "HIGH",
                "B",
            )
        else:
            self._pass("TOTAL_VEHICLE_CHECK_NA")


    # =========================================================================
    # PHASE C — Contextual Consistency
    # =========================================================================

    # CHECK 11: Narrative Consistency (FR-2.7)
    # ─────────────────────────────────────────
    def _check_11_narrative_consistency(self, ai: Dict[str, Any]) -> None:
        """User narrative must align with visual evidence."""
        narrative = ai.get("narrative_consistency", {}) or {}

        if not narrative.get("visual_evidence_matches", False):
            inconsistencies: List[str] = narrative.get("inconsistencies", [])
            self._fail(
                "NARRATIVE_MISMATCH",
                "Narrative Consistency (FR-2.7)",
                (
                    f"Narrative inconsistent with evidence: {'; '.join(inconsistencies)}"
                    if inconsistencies
                    else "User narrative does not match visual evidence."
                ),
                "HIGH",
                "C",
            )
        else:
            self._pass("NARRATIVE_CONSISTENCY")

    # CHECK 12 (NEW): Multi-Image Consistency
    # ─────────────────────────────────────────
    def _check_12_multi_image_consistency(self, ai: Dict[str, Any]) -> None:
        """
        When multiple images are submitted, verify:
        • Same vehicle (plate/color/make across all images)
        • Consistent lighting / time-of-day metadata
        • Consistent damage location across angles

        This check relies on the multi_image_analysis key populated by the
        orchestrator after aggregating individual image results.
        """
        multi = ai.get("multi_image_analysis", {}) or {}
        if not multi:
            self._pass("MULTI_IMAGE_NOT_APPLICABLE")
            return

        issues: List[str] = []
        if not multi.get("plates_consistent", True):
            issues.append("different license plates across images")
        if not multi.get("vehicle_consistent", True):
            issues.append("vehicle make/model differs across images")
        if not multi.get("lighting_consistent", True):
            issues.append("time-of-day / lighting differs across images")
        if not multi.get("damage_location_consistent", True):
            issues.append("damage location contradicts across angles")

        if issues:
            self._fail(
                "MULTI_IMAGE_INCONSISTENCY",
                "Multi-Image Consistency Check (v2 NEW)",
                f"Cross-image inconsistencies detected: {', '.join(issues)}.",
                "HIGH",
                "C",
            )
        else:
            self._pass("MULTI_IMAGE_CONSISTENT")

    # =========================================================================
    # PHASE D — Financial Sanity
    # =========================================================================

    # CHECK 13: Amount Threshold (FR-3.1)
    # ─────────────────────────────────────
    def _check_13_amount_threshold(self, claim_amount: int) -> None:
        """Claim amount vs auto-approval threshold."""
        if claim_amount <= self.config.AUTO_APPROVAL_AMOUNT_THRESHOLD:
            self._pass("AMOUNT_THRESHOLD")
        else:
            self._fail(
                "AMOUNT_EXCEEDS_THRESHOLD",
                "Amount Threshold Check (FR-3.1)",
                (
                    f"Claim ₹{claim_amount:,} exceeds auto-approval limit "
                    f"₹{self.config.AUTO_APPROVAL_AMOUNT_THRESHOLD:,}."
                ),
                "MEDIUM",
                "D",
            )

    # CHECK 14 (NEW): Damage–Cost Sanity
    # ─────────────────────────────────────
    def _check_14_damage_cost_sanity(
        self, claim_amount: int, ai: Dict[str, Any]
    ) -> None:
        """
        Cross-validate claimed amount against AI cost estimate range.

        Flags:
        • Claim > AI max estimate × MAX_CLAIM_TO_ESTIMATE_RATIO → HIGH
        • Claim < AI min estimate / 2 (possibly under-declared) → LOW
        • Damage severity = none but claim > 0 → CRITICAL
        """
        damage = ai.get("damage_assessment", {}) or {}
        ai_severity = (damage.get("ai_severity") or "none").lower()
        ai_min = damage.get("ai_cost_min")   # int or None
        ai_max = damage.get("ai_cost_max")   # int or None

        # No damage but claim submitted
        if ai_severity == "none" and claim_amount > 0:
            self._fail(
                "CLAIM_NO_DAMAGE_DETECTED",
                "Damage–Cost Sanity — No Damage (v2 NEW)",
                (
                    f"AI detected no damage but claim of ₹{claim_amount:,} submitted. "
                    "Possible fraud."
                ),
                "CRITICAL",
                "D",
            )
            return

        # Compare against estimated range
        if ai_max is not None and ai_max > 0:
            ratio = claim_amount / ai_max
            if ratio > self.config.MAX_CLAIM_TO_ESTIMATE_RATIO:
                self._fail(
                    "CLAIM_INFLATED",
                    "Damage–Cost Sanity — Inflated Claim (v2 NEW)",
                    (
                        f"Claim ₹{claim_amount:,} is {ratio:.1f}× the AI max estimate "
                        f"₹{ai_max:,} (limit: {self.config.MAX_CLAIM_TO_ESTIMATE_RATIO}×). "
                        "Possible claim inflation."
                    ),
                    "HIGH",
                    "D",
                )
            elif ai_min is not None and claim_amount < ai_min / 2:
                self._fail(
                    "CLAIM_SUSPICIOUSLY_LOW",
                    "Damage–Cost Sanity — Under-declared (v2 NEW)",
                    (
                        f"Claim ₹{claim_amount:,} is far below AI min estimate "
                        f"₹{ai_min:,}. Possible under-declaration or incorrect images."
                    ),
                    "LOW",
                    "D",
                )
            else:
                self._pass("DAMAGE_COST_SANITY")
        else:
            self._pass("DAMAGE_COST_SANITY_NO_ESTIMATE")

    # =========================================================================
    # PHASE E — Policy & History Validation
    # =========================================================================

    # CHECK 15 (NEW): Policy Active & Coverage Gate
    # ───────────────────────────────────────────────
    def _check_15_policy_active_and_coverage(
        self, policy: Dict[str, Any], claim_amount: int
    ) -> None:
        """
        Validate that the policy is active and covers the claimed amount.

        Checks:
        • policy.status == 'active'
        • claim date (today) is between policy start_date and end_date
        • claim_amount <= policy.plan_coverage (or plan.coverage_amount)
        """
        status      = (policy.get("status") or "").lower()
        coverage    = policy.get("plan_coverage") or policy.get("coverage_amount") or 0
        start_str   = policy.get("start_date")
        end_str     = policy.get("end_date")
        today       = datetime.utcnow().date()

        if status != "active":
            self._fail(
                "POLICY_INACTIVE",
                "Policy Status Check (v2 NEW)",
                f"Policy status is '{status}' — must be 'active' for claim processing.",
                "CRITICAL",
                "E",
            )
        else:
            self._pass("POLICY_ACTIVE")

        # Date window
        in_window = True
        try:
            if start_str:
                start = datetime.fromisoformat(str(start_str)).date()
                if today < start:
                    in_window = False
            if end_str:
                end = datetime.fromisoformat(str(end_str)).date()
                if today > end:
                    in_window = False
        except (ValueError, TypeError):
            in_window = True  # Cannot parse → don't penalise

        if not in_window:
            self._fail(
                "POLICY_EXPIRED_OR_NOT_STARTED",
                "Policy Date Window Check (v2 NEW)",
                f"Incident date {today} falls outside policy window {start_str} – {end_str}.",
                "CRITICAL",
                "E",
            )
        else:
            self._pass("POLICY_DATE_WINDOW")

        # Coverage ceiling
        if coverage and claim_amount > coverage:
            self._fail(
                "CLAIM_EXCEEDS_COVERAGE",
                "Policy Coverage Limit Check (v2 NEW)",
                (
                    f"Claim ₹{claim_amount:,} exceeds policy coverage "
                    f"₹{coverage:,}. Requires agent to assess partial payout."
                ),
                "MEDIUM",
                "E",
            )
        else:
            self._pass("COVERAGE_ADEQUATE")

    # CHECK 16 (NEW): Duplicate / Repeat-Claim Guard
    # ─────────────────────────────────────────────────
    def _check_16_duplicate_claim_guard(
        self,
        ai: Dict[str, Any],
        policy: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]],
    ) -> None:
        """
        Flag if the same license plate or policy has an open/recent claim.

        history : list of dicts, each with keys:
            { claim_id, status, created_at (ISO str), vehicle_registration }
        """
        if not history:
            self._pass("DUPLICATE_CLAIM_NOT_APPLICABLE")
            return

        ocr          = ai.get("ocr_data", {}) or {}
        this_plate   = (
            (ocr.get("plate_text") or policy.get("vehicle_registration") or "")
            .upper().replace(" ", "").replace("-", "")
        )
        window_days  = self.config.DUPLICATE_CLAIM_WINDOW_DAYS
        now          = datetime.utcnow()

        recent_open: List[int] = []
        same_plate_recent: List[int] = []

        for prior in history:
            prior_status = (prior.get("status") or "").lower()
            prior_plate  = (
                (prior.get("vehicle_registration") or "")
                .upper().replace(" ", "").replace("-", "")
            )
            try:
                prior_date = datetime.fromisoformat(str(prior.get("created_at", "")))
                age_days   = (now - prior_date).days
            except (ValueError, TypeError):
                age_days = 999

            if prior_status in ("pending", "processing"):
                recent_open.append(prior.get("claim_id", 0))

            if (
                this_plate
                and prior_plate == this_plate
                and age_days <= window_days
                and prior_status not in ("rejected",)
            ):
                same_plate_recent.append(prior.get("claim_id", 0))

        if recent_open:
            self._fail(
                "DUPLICATE_OPEN_CLAIM",
                "Duplicate Claim Guard — Open Claim (v2 NEW)",
                (
                    f"Policy already has open/processing claim(s): "
                    f"{recent_open}. New claim flagged for review."
                ),
                "HIGH",
                "E",
            )

        if same_plate_recent:
            self._fail(
                "DUPLICATE_PLATE_RECENT",
                "Duplicate Claim Guard — Recent Plate (v2 NEW)",
                (
                    f"Plate {this_plate!r} has {len(same_plate_recent)} recent "
                    f"claim(s) within {window_days} days: {same_plate_recent}. "
                    "Possible staged-accident fraud ring."
                ),
                "HIGH",
                "E",
            )
            
        # ================= NEW: IMAGE HASH COMPARISON =================
        current_hashes = ai.get("metadata", {}).get("image_hashes", [])
        hash_collisions = []
        
        if current_hashes:
            from app.services.image_hashing import calculate_hamming_distance
            for prior in history:
                prior_hashes = prior.get("image_hashes") or []
                for curr_h in current_hashes:
                    for old_h in prior_hashes:
                        # Distance <= 5 indicates highly likely identical/cropped image
                        if calculate_hamming_distance(curr_h, old_h) <= 5:
                            if prior.get("claim_id") not in hash_collisions:
                                hash_collisions.append(prior.get("claim_id"))
                                
        if hash_collisions:
            self._fail(
                "IMAGE_HASH_COLLISION",
                "Duplicate Image Detection (v4 NEW)",
                (
                    f"Uploaded image(s) cryptographically match image(s) from "
                    f"prior claim(s): {hash_collisions}. HIGH PROBABILITY OF FRAUD."
                ),
                "CRITICAL",
                "E",
            )

        if not recent_open and not same_plate_recent and not hash_collisions:
            self._pass("NO_DUPLICATE_CLAIMS")

    # CHECK 17 (NEW): Accident Date Validation
    # ─────────────────────────────────────────────────
    def _check_17_accident_date_validation(
        self, ai: Dict[str, Any], accident_date: Optional[datetime]
    ) -> None:
        """
        Verify that the image EXIF timestamp is within MAX_DAYS_BETWEEN_ACCIDENT_AND_IMAGE
        of the user-reported accident date.
        """
        if not accident_date:
            self._pass("ACCIDENT_DATE_NOT_PROVIDED")
            return

        exif_ts_str = self._ai(ai, "exif_metadata", "timestamp")
        if not exif_ts_str:
            self._pass("NO_EXIF_TIMESTAMP_FOR_DATE_CHECK")
            return

        try:
            # Parse the EXIF timestamp string
            exif_date_str = str(exif_ts_str)
            # Handle forms like 'YYYY:MM:DD HH:MM:SS'
            if len(exif_date_str) >= 10 and exif_date_str[4] == ':' and exif_date_str[7] == ':':
                exif_date_str = exif_date_str[:10].replace(':', '-') + exif_date_str[10:]
            
            # Use isoformat parse or naive datetime parse depending on string format
            if 'T' not in exif_date_str and ' ' in exif_date_str:
                exif_date = datetime.strptime(exif_date_str, "%Y-%m-%d %H:%M:%S").date()
            else:
                exif_date = datetime.fromisoformat(exif_date_str.replace('Z', '+00:00')).date()
            
            acc_date = accident_date.date() if isinstance(accident_date, datetime) else accident_date

            diff_days = abs((exif_date - acc_date).days)

            if diff_days > self.config.MAX_DAYS_BETWEEN_ACCIDENT_AND_IMAGE:
                self._fail(
                    "ACCIDENT_DATE_MISMATCH",
                    "Accident Date Validation (v2 NEW)",
                    f"Image date ({exif_date}) is {diff_days} days away from reported accident date ({acc_date}), exceeding the {self.config.MAX_DAYS_BETWEEN_ACCIDENT_AND_IMAGE}-day limit.",
                    "HIGH",
                    "E",
                )
            else:
                self._pass("ACCIDENT_DATE_MATCH")
        except (ValueError, TypeError, AttributeError) as e:
            # If parsing fails, skip the check instead of failing the claim improperly
            self._pass("ACCIDENT_DATE_PARSE_ERROR")

    # =========================================================================
    # FINAL DECISION
    # =========================================================================

    def _make_final_decision(self, claim_amount: int) -> VerificationResult:
        """
        Compute the final decision using:
        1. Raw severity score (with optional compounding)
        2. Critical-failure fast path
        3. Weighted confidence score (0-100)
        """
        critical_count = sum(1 for r in self._failed if r.severity == "CRITICAL")
        high_count     = sum(1 for r in self._failed if r.severity == "HIGH")

        # Compounding multiplier for correlated failures
        severe_failure_count = critical_count + high_count
        final_score = self._raw_score
        if severe_failure_count >= self.config.COMPOUND_FAILURE_THRESHOLD:
            final_score *= self.config.COMPOUND_MULTIPLIER

        # Weighted confidence score (100 = perfect, 0 = total failure)
        max_possible = len(self._passed) + len(self._failed)
        raw_pass_rate = (len(self._passed) / max_possible) if max_possible else 1.0
        # Penalise by severity: each CRITICAL reduces confidence more than LOW
        severity_penalty = min(final_score / 50.0, 1.0)   # cap at 1.0
        confidence_score = max(0.0, (raw_pass_rate - severity_penalty)) * 100.0

        # Decision logic
        if not self._failed:
            return self._build(
                "APPROVED",
                "All verification checks passed.",
                "HIGH",
                confidence_score,
                auto_approved=True,
                review=False,
                monitor=False,
                score=final_score,
            )

        if critical_count > 0:
            return self._build(
                "REJECTED",
                f"{critical_count} critical fraud indicator(s) detected.",
                "HIGH",
                confidence_score,
                auto_approved=False,
                review=True,
                monitor=False,
                score=final_score,
            )

        if final_score >= self.config.AUTO_REJECT_SCORE_THRESHOLD:
            return self._build(
                "REJECTED",
                f"Multiple fraud indicators accumulated (severity score: {final_score:.1f}).",
                "HIGH",
                confidence_score,
                auto_approved=False,
                review=True,
                monitor=False,
                score=final_score,
            )

        if final_score >= self.config.FLAG_FOR_REVIEW_SCORE_THRESHOLD:
            return self._build(
                "FLAGGED",
                "Verification issues require human review.",
                "MEDIUM",
                confidence_score,
                auto_approved=False,
                review=True,
                monitor=False,
                score=final_score,
            )

        # Only LOW issues
        return self._build(
            "APPROVED",
            "Minor verification issues within acceptable range.",
            "MEDIUM",
            confidence_score,
            auto_approved=True,
            review=False,
            monitor=True,
            score=final_score,
        )

    def _build(
        self,
        status: str,
        reason: str,
        confidence_level: str,
        confidence_score: float,
        auto_approved: bool,
        review: bool,
        monitor: bool,
        score: float,
    ) -> VerificationResult:
        return VerificationResult(
            status=status,
            decision_reason=reason,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            auto_approved=auto_approved,
            requires_human_review=review,
            requires_monitoring=monitor,
            severity_score=score,
            passed_checks=list(self._passed),
            failed_checks=list(self._failed),
            timestamp=datetime.utcnow().isoformat(),
        )

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _location_matches(loc1: str, loc2: str) -> bool:
        """Token overlap location match (enhance with geocoding if needed)."""
        tokens1 = set(loc1.lower().replace(",", " ").split())
        tokens2 = set(loc2.lower().replace(",", " ").split())
        stopwords = {"the", "of", "and", "in", "at", "near"}
        tokens1 -= stopwords
        tokens2 -= stopwords
        return bool(tokens1 & tokens2)
