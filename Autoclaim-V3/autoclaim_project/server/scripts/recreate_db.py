"""
Simple database recreation script.
Drops all tables and recreates with v3.0 schema.
"""

from app.db.database import Base, engine
from app.db import models

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)

print("Creating all tables with v3.0 schema...")
Base.metadata.create_all(bind=engine)

print("✅ Database recreated successfully with v3.0 schema!")
print("\n📊 ForensicAnalysis v3.0 includes:")
print("  - Identity Extraction: detected_objects, license_plate_visible/obscured")
print("  - Damage Extraction: severity_score, impact_point, rust, paint/glass damage, airbags, etc.")
print("  - Forensics Extraction: screen_recapture, UI elements, image_quality, shadows")
print("  - Scene Extraction: time_of_day, weather, debris, traffic") 
print("  - Rule-Based Decisions: fraud_score, ai_recommendation, risk_flags (all COMPUTED)")
