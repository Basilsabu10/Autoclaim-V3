"""Seed sample policy plans into the database"""
from database import SessionLocal
import models

def seed_policy_plans():
    db = SessionLocal()
    
    # Check if plans already exist
    existing = db.query(models.PolicyPlan).first()
    if existing:
        print("Policy plans already exist!")
        db.close()
        return
    
    plans = [
        {
            "name": "Basic",
            "description": "Essential coverage for budget-conscious drivers. Covers collision and liability.",
            "coverage_amount": 25000,
            "premium_monthly": 49.99,
            "premium_yearly": 499.99,
            "deductible": 1000,
            "coverage_types": ["collision", "liability"]
        },
        {
            "name": "Standard",
            "description": "Balanced protection with theft and vandalism coverage included.",
            "coverage_amount": 50000,
            "premium_monthly": 89.99,
            "premium_yearly": 899.99,
            "deductible": 500,
            "coverage_types": ["collision", "liability", "theft", "vandalism"]
        },
        {
            "name": "Premium",
            "description": "Comprehensive coverage including natural disasters and uninsured motorist.",
            "coverage_amount": 100000,
            "premium_monthly": 149.99,
            "premium_yearly": 1499.99,
            "deductible": 250,
            "coverage_types": ["collision", "liability", "theft", "vandalism", "flood", "fire", "uninsured"]
        },
        {
            "name": "Ultimate",
            "description": "Full coverage with zero deductible and roadside assistance.",
            "coverage_amount": 250000,
            "premium_monthly": 249.99,
            "premium_yearly": 2499.99,
            "deductible": 0,
            "coverage_types": ["collision", "liability", "theft", "vandalism", "flood", "fire", "uninsured", "roadside", "rental"]
        }
    ]
    
    for plan_data in plans:
        plan = models.PolicyPlan(**plan_data)
        db.add(plan)
    
    db.commit()
    print(f"Created {len(plans)} policy plans!")
    db.close()

if __name__ == "__main__":
    seed_policy_plans()
