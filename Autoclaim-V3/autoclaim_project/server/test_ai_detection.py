"""
Standalone test: Run the full AutoClaim AI pipeline on the 3 AI-generated
Baleno test images and report whether the pipeline correctly identifies them.

Run from the server/ directory (where .env lives):
    python test_ai_detection.py
"""

import os
import sys
import json

# ── Make sure the app package is importable ───────────────────────────────────
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SERVER_DIR)

# ── Load .env manually so settings work without a running FastAPI app ─────────
from dotenv import load_dotenv
load_dotenv(os.path.join(SERVER_DIR, ".env"))

# ── Now import our pipeline ───────────────────────────────────────────────────
from app.services.ai_orchestrator import analyze_claim

# ── Image paths ───────────────────────────────────────────────────────────────
TEST_DIR = os.path.join(SERVER_DIR, "test_images", "kia_seltos")
IMAGE_FILES = [
    "PXL_20260131_143041.jpg.jpg",
]

image_paths = []
for name in IMAGE_FILES:
    full = os.path.join(TEST_DIR, name)
    if os.path.exists(full):
        image_paths.append(full)
    else:
        print(f"[WARN] Image not found: {full}")

if not image_paths:
    print("[ERROR] No test images found. Aborting.")
    sys.exit(1)

print("=" * 70)
print("AutoClaim AI Pipeline — AI-Generated Image Detection Test")
print("=" * 70)
print(f"Images to test ({len(image_paths)}):")
for p in image_paths:
    print(f"  • {os.path.basename(p)}")
print()

# ── Run the full pipeline ─────────────────────────────────────────────────────
# Use the first image also as the "front" image; all 3 as damage images.
result = analyze_claim(
    damage_image_paths=image_paths,
    front_image_path=image_paths[0],   # first image doubles as front view
    description="Test: Kia Seltos image — checking detection pipeline",
    claim_amount=0,
    policy_data={},     # no policy — only forensics check matters here
    claim_history=[],
)

# ── Extract key results ───────────────────────────────────────────────────────
ai_analysis  = result.get("ai_analysis", {})
forensics    = ai_analysis.get("forensics", {})
fraud        = ai_analysis.get("fraud_analysis", {})
verification = result.get("verification", {})

print("=" * 70)
print("FORENSICS (Groq Vision)")
print("=" * 70)
ai_gen       = forensics.get("ai_generated")
ai_gen_conf  = forensics.get("ai_generation_confidence")
ai_gen_why   = forensics.get("ai_generation_indicators", [])

print(f"  ai_generated             : {ai_gen}")
print(f"  ai_generation_confidence : {ai_gen_conf}")
print(f"  ai_generation_indicators : {ai_gen_why}")
print(f"  image_quality            : {forensics.get('image_quality')}")
print(f"  is_blurry                : {forensics.get('is_blurry')}")
print(f"  is_screen_recapture      : {forensics.get('is_screen_recapture')}")
print(f"  has_watermarks           : {forensics.get('has_watermarks')}")
print(f"  shadows_inconsistent     : {forensics.get('shadows_inconsistent')}")
print(f"  multiple_light_sources   : {forensics.get('multiple_light_sources')}")
print()

print("=" * 70)
print("FRAUD ANALYSIS (Groq)")
print("=" * 70)
print(f"  fraud_detected  : {fraud.get('fraud_detected')}")
print(f"  fraud_score     : {fraud.get('fraud_score')}")
print(f"  fraud_indicators: {fraud.get('fraud_indicators', [])}")
print(f"  reasoning       : {fraud.get('reasoning', '')[:300]}")
print()

print("=" * 70)
print("ELA ANALYSIS")
print("=" * 70)
ela_score = forensics.get("ela_score")
print(f"  ela_score       : {ela_score}")
print()

print("=" * 70)
print("SIGHTENGINE AI DETECTION")
print("=" * 70)
sight_detection = ai_analysis.get("ai_detection", {})
print(f"  success         : {sight_detection.get('success')}")
print(f"  ai_generated    : {sight_detection.get('ai_generated')}")
print(f"  max_ai_score    : {sight_detection.get('max_ai_score')}")
print()

print("=" * 70)
print("VERIFICATION RESULT (Rule Engine)")
print("=" * 70)
if isinstance(verification, dict) and not verification.get("error"):
    print(f"  STATUS          : {verification.get('status')}")
    print(f"  confidence_score: {verification.get('confidence_score')}")
    print(f"  severity_score  : {verification.get('severity_score')}")
    print(f"  auto_approved   : {verification.get('auto_approved')}")
    print()
    failed = verification.get("failed_checks", [])
    if failed:
        print(f"  FAILED CHECKS ({len(failed)}):")
        for f in failed:
            print(f"    [{f.get('severity')}] {f.get('rule_id')} — {f.get('reason')}")
    else:
        print("  No failed checks.")
    passed = verification.get("passed_checks", [])
    print(f"\n  PASSED CHECKS ({len(passed)}): {passed}")
else:
    print(f"  Verification error or not run: {verification}")

# ── Verdict ───────────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
detected_as_ai = bool(ai_gen) or (ai_gen_conf is not None and float(ai_gen_conf) >= 0.5)
rule_rejected  = isinstance(verification, dict) and verification.get("status") == "REJECTED"
fraud_flag     = bool(fraud.get("fraud_detected"))

if detected_as_ai:
    print("✅  Groq correctly flagged these images as AI-GENERATED.")
else:
    print("❌  Groq did NOT detect these images as AI-generated.")

if rule_rejected:
    print("✅  Rule engine REJECTED the claim (as expected for AI-generated images).")
else:
    print(f"⚠️   Rule engine verdict: {verification.get('status', 'N/A')} (expected REJECTED).")

if fraud_flag:
    print("✅  Fraud detection triggered.")
else:
    print("ℹ️   Fraud detection did NOT explicitly trigger.")

print("=" * 70)
print("Full result JSON saved to: test_ai_detection_result.json")
with open(os.path.join(SERVER_DIR, "test_ai_detection_result.json"), "w") as f:
    json.dump(result, f, indent=2, default=str)
print("Done.")
