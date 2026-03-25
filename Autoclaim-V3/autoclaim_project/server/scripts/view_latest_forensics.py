"""View forensic analysis of the latest claim."""

from app.db.database import SessionLocal
from app.db.models import Claim, ForensicAnalysis, User
from datetime import datetime
import json

db = SessionLocal()

try:
    # Get the most recent claim
    latest_claim = db.query(Claim).order_by(Claim.created_at.desc()).first()
    
    if not latest_claim:
        print("\n❌ No claims found in the database.\n")
    else:
        print("\n" + "=" * 80)
        print("  LATEST CLAIM - FORENSIC ANALYSIS")
        print("=" * 80 + "\n")
        
        # Claim basic info
        user = db.query(User).filter(User.id == latest_claim.user_id).first()
        print(f"📋 Claim ID: {latest_claim.id}")
        print(f"👤 User: {user.email if user else 'Unknown'}")
        print(f"📅 Submitted: {latest_claim.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📝 Status: {latest_claim.status.upper()}")
        print(f"🔢 Vehicle Plate: {latest_claim.vehicle_number_plate or 'Not detected'}")
        print(f"\n📄 Description:\n{latest_claim.description[:200]}..." if len(latest_claim.description or '') > 200 else f"\n📄 Description:\n{latest_claim.description or 'No description'}")
        
        # Forensic analysis
        forensics = db.query(ForensicAnalysis).filter(
            ForensicAnalysis.claim_id == latest_claim.id
        ).first()
        
        print("\n" + "-" * 80)
        
        if not forensics:
            print("⚠️  No forensic analysis found for this claim.")
            print("   (Analysis may still be in progress)")
        else:
            print("🔬 FORENSIC ANALYSIS RESULTS")
            print("-" * 80 + "\n")
            
            # AI Recommendation
            print(f"🎯 AI Recommendation: {forensics.ai_recommendation or 'N/A'}")
            print(f"📊 Overall Confidence: {forensics.overall_confidence_score or 'N/A'}%")
            print(f"⚠️  Fraud Probability: {forensics.fraud_probability or 'N/A'}")
            
            # Vehicle Identification
            print(f"\n🚗 VEHICLE IDENTIFICATION")
            print(f"   Make: {forensics.vehicle_make or 'N/A'}")
            print(f"   Model: {forensics.vehicle_model or 'N/A'}")
            print(f"   Year: {forensics.vehicle_year or 'N/A'}")
            print(f"   Color: {forensics.vehicle_color or 'N/A'}")
            
            # License Plate
            print(f"\n🔢 LICENSE PLATE")
            print(f"   Detected: {forensics.license_plate_detected}")
            print(f"   Text: {forensics.license_plate_text or 'N/A'}")
            print(f"   Confidence: {forensics.license_plate_confidence or 'N/A'}%")
            print(f"   Match Status: {forensics.license_plate_match_status or 'N/A'}")
            
            # OCR Results
            print(f"\n📖 OCR RESULTS")
            print(f"   Plate Text: {forensics.ocr_plate_text or 'N/A'}")
            print(f"   Confidence: {forensics.ocr_plate_confidence or 'N/A'}%")
            
            # Damage Assessment
            print(f"\n💥 DAMAGE ASSESSMENT")
            print(f"   Damage Detected: {forensics.ai_damage_detected}")
            print(f"   Damage Type: {forensics.ai_damage_type or 'N/A'}")
            print(f"   Severity: {forensics.ai_severity or 'N/A'}")
            print(f"   Structural Damage: {forensics.ai_structural_damage}")
            
            # Cost Estimation
            if forensics.ai_cost_min and forensics.ai_cost_max:
                print(f"\n💰 COST ESTIMATION")
                print(f"   Range: ₹{forensics.ai_cost_min:,} - ₹{forensics.ai_cost_max:,}")
                print(f"   Confidence: {forensics.ai_cost_confidence or 'N/A'}%")
            
            # Damaged Panels
            if forensics.ai_damaged_panels:
                print(f"\n🔧 DAMAGED PANELS")
                try:
                    panels = forensics.ai_damaged_panels if isinstance(forensics.ai_damaged_panels, list) else json.loads(forensics.ai_damaged_panels)
                    for panel in panels[:5]:  # Show first 5
                        if isinstance(panel, dict):
                            print(f"   • {panel.get('panel', 'Unknown')}: {panel.get('severity', 'N/A')} ({panel.get('confidence', 'N/A')}% confidence)")
                        else:
                            print(f"   • {panel}")
                except:
                    print(f"   {forensics.ai_damaged_panels}")
            
            # EXIF Metadata
            print(f"\n📷 EXIF METADATA")
            print(f"   Timestamp: {forensics.exif_timestamp or 'N/A'}")
            print(f"   Location: {forensics.exif_location_name or 'N/A'}")
            print(f"   Camera: {forensics.exif_camera_make or 'N/A'} {forensics.exif_camera_model or ''}")
            
            # Risk Assessment
            if forensics.ai_risk_flags:
                print(f"\n🚨 RISK FLAGS")
                try:
                    flags = forensics.ai_risk_flags if isinstance(forensics.ai_risk_flags, list) else json.loads(forensics.ai_risk_flags)
                    for flag in flags[:5]:
                        print(f"   ⚠️  {flag}")
                except:
                    print(f"   {forensics.ai_risk_flags}")
            
            # AI Reasoning
            if forensics.ai_reasoning:
                print(f"\n🧠 AI REASONING")
                print(f"   {forensics.ai_reasoning[:300]}..." if len(forensics.ai_reasoning) > 300 else f"   {forensics.ai_reasoning}")
            
            # Analysis Metadata
            print(f"\n📊 ANALYSIS METADATA")
            print(f"   Provider: {forensics.ai_provider or 'N/A'}")
            print(f"   Model: {forensics.ai_model or 'N/A'}")
            print(f"   Version: {forensics.analysis_version or 'N/A'}")
            print(f"   Analyzed At: {forensics.analyzed_at.strftime('%Y-%m-%d %H:%M:%S') if forensics.analyzed_at else 'N/A'}")
        
        print("\n" + "=" * 80 + "\n")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
