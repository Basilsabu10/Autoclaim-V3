"""Script to view detailed forensic analysis data"""
from app.db.database import SessionLocal
from app.db import models
import json

db = SessionLocal()

print('='*80)
print('FORENSIC ANALYSIS TABLE - DETAILED VIEW')
print('='*80)

forensics = db.query(models.ForensicAnalysis).all()
print(f'\nTotal Records: {len(forensics)}\n')

for i, f in enumerate(forensics, 1):
    print(f'--- Record {i} (ID: {f.id}) ---')
    print(f'  Claim ID: {f.claim_id}')
    
    # EXIF Metadata
    print(f'\n  📍 EXIF Metadata:')
    print(f'    Timestamp: {f.exif_timestamp}')
    print(f'    GPS: ({f.exif_gps_lat}, {f.exif_gps_lon})')
    print(f'    Location: {f.exif_location_name}')
    print(f'    Camera: {f.exif_camera_make} {f.exif_camera_model}')
    
    # OCR Results
    print(f'\n  🔤 OCR Results:')
    print(f'    Plate Text: {f.ocr_plate_text}')
    print(f'    Confidence: {f.ocr_plate_confidence}')
    print(f'    Plate Visible: {f.license_plate_visible}')
    print(f'    Plate Obscured: {f.license_plate_obscured}')
    
    # AI Extraction (v3.0)
    print(f'\n  🔍 AI Extraction Results:')
    print(f'    Detected Objects: {f.detected_objects}')
    print(f'    Vehicle: {f.vehicle_make} {f.vehicle_model} {f.vehicle_year} ({f.vehicle_color})')
    print(f'    Damage Type: {f.ai_damage_type}')
    print(f'    Severity Score: {f.damage_severity_score}')
    print(f'    Impact Point: {f.impact_point}')
    print(f'    Affected Panels: {f.ai_damaged_panels}')
    
    # Forensics (v3.0)
    print(f'\n  🔬 Image Forensics:')
    print(f'    Screen Recapture: {f.is_screen_recapture}')
    print(f'    Has UI Elements: {f.has_ui_elements}')
    print(f'    Image Quality: {f.image_quality}')
    print(f'    Is Blurry: {f.is_blurry}')
    print(f'    Rust Present: {f.is_rust_present}')
    print(f'    Dirt in Damage: {f.is_dirt_in_damage}')
    
    # Rule-Based Decisions (v3.0)
    print(f'\n  ⚖️ Rule-Based Decisions:')
    print(f'    Recommendation: {f.ai_recommendation}')
    print(f'    Fraud Probability: {f.fraud_probability}')
    print(f'    Fraud Score: {f.fraud_score}')
    print(f'    Risk Flags: {f.ai_risk_flags}')
    print(f'    Overall Confidence: {f.overall_confidence_score}')
    print(f'    Review Priority: {f.human_review_priority}')
    print(f'    Cost Range: ₹{f.ai_cost_min} - ₹{f.ai_cost_max}')
    
    # Reasoning (truncated if too long)
    reasoning = f.ai_reasoning or "N/A"
    if len(reasoning) > 200:
        reasoning = reasoning[:200] + "..."
    print(f'    Reasoning: {reasoning}')
    
    # Metadata
    print(f'\n  ℹ️ Analysis Metadata:')
    print(f'    Analyzed At: {f.analyzed_at}')
    print(f'    Version: {f.analysis_version}')
    print(f'    Provider: {f.ai_provider}')
    print(f'    Model: {f.ai_model}')
    
    print('\n' + '-'*80 + '\n')

db.close()
print('='*80)
print('END OF FORENSIC ANALYSIS DATA')
print('='*80)
