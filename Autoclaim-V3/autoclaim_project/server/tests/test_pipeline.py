"""
Test script for AI pipeline.
Tests the complete analysis flow with YOLO, OCR, and LLM services.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import ai_orchestrator

# Test image path
image_path = 'test_images/kia_seltos/IMG_1028 (1).jpg'

print('=== TESTING AI PIPELINE ===')
print('Services Status:')
status = ai_orchestrator.initialize_services()
print(f"  YOLO-Seg: {'OK' if status['yolo_seg'] else 'N/A'}")
print(f"  Groq: {'OK' if status['groq'] else 'N/A'}")

print('\nRunning analysis on damage image...')
result = ai_orchestrator.analyze_claim(
    damage_image_paths=[image_path],
    front_image_path=None,
    description='Scratch on car door'
)

print('\n=== YOLO DETECTION ===')
yolo = result.get('yolo_damage', {})
print(f"Vehicle Detected: {yolo.get('vehicle_detected', False)}")
print(f"Summary: {yolo.get('summary', 'N/A')}")
for det in yolo.get('detections', [])[:5]:
    # Corrected key search in YOLO result
    cls = det.get('class') or det.get('class_name', 'unknown')
    conf = det.get('confidence', 0.0)
    print(f"  - {cls}: {conf*100:.1f}%")

print('\n=== AI DAMAGE ANALYSIS ===')
ai = result.get('ai_analysis', {})
damage = ai.get('damage', {})
identity = ai.get('identity', {})

print(f"Provider: {ai.get('provider', 'N/A')}")
print(f"Brand: {identity.get('vehicle_make', 'N/A')}")
print(f"Model: {identity.get('vehicle_model', 'N/A')}")
print(f"Color: {identity.get('vehicle_color', 'N/A')}")
print(f"Damage Type: {damage.get('damage_type', 'N/A')}")
print(f"Severity: {damage.get('severity', 'N/A')}")
print(f"Recommendation: {ai.get('ai_recommendation', 'N/A')}")

fraud = ai.get('fraud_analysis', {})
print(f"\n=== FRAUD ANALYSIS ===")
print(f"Fraud Detected: {fraud.get('fraud_detected', False)}")
print(f"Fraud Score: {fraud.get('fraud_score', 0.0)}")
print(f"Indicators: {', '.join(fraud.get('fraud_indicators', []))}")
print(f"Reasoning: {fraud.get('reasoning', 'N/A')}")

print(f"\nYOLO Summary: {yolo.get('summary', 'N/A')}")

print('\n=== DONE ===')
