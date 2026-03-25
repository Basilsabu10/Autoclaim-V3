"""
Seed dummy policy data for Kia Seltos - Simple version.
Creates a test user, policy plan, and the specified policy.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import User, PolicyPlan, Policy

def seed_kia_policy():
    """Seed the Kia Seltos policy data."""
    db: Session = SessionLocal()
    
    try:
        print("=" * 80)
        print("SEEDING KIA SELTOS POLICY DATA")
        print("=" * 80)
        
        # 1. Create a test user (if not exists)
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            user = existing_user
            print(f"\n✓ Using existing user: {user.email}")
        else:
            # Use a pre-hashed password for 'test123'
            # Generated with: from passlib.hash import bcrypt; bcrypt.hash("test123")
            user = User(
                email="test@example.com",
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqfq8r1Z8Q8Xqhd6YgLQpJy",  # test123
                role="user",
                name="Test User",
                vehicle_number="KL-07-CU-7475"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"\n✓ Created test user: {user.email}")
        
        # 2. Create a comprehensive policy plan (if not exists)
        existing_plan = db.query(PolicyPlan).filter(
            PolicyPlan.name == "Comprehensive Plan"
        ).first()
        
        if existing_plan:
            plan = existing_plan
            print(f"✓ Using existing plan: {plan.name}")
        else:
            plan = PolicyPlan(
                name="Comprehensive Plan",
                description="Full coverage including theft, accidents, natural disasters",
                coverage_amount=500000,  # 5 lakh INR
                premium_monthly=2500  # ₹2500 per month
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            print(f"✓ Created policy plan: {plan.name}")
        
        # 3. Create the Kia Seltos policy
        today = datetime.now()
        one_year_later = today + timedelta(days=365)
        
        # Check if policy already exists
        existing_policy = db.query(Policy).filter(
            Policy.vehicle_registration == "KL-07-CU-7475"
        ).first()
        
        if existing_policy:
            print(f"\n⚠️  Policy already exists for vehicle: KL-07-CU-7475")
            print(f"   Updating existing policy...")
            
            existing_policy.user_id = user.id
            existing_policy.plan_id = plan.id
            existing_policy.vehicle_make = "Kia"
            existing_policy.vehicle_model = "Seltos"
            existing_policy.vehicle_year = 2020
            existing_policy.start_date = today
            existing_policy.end_date = one_year_later
            existing_policy.status = "active"
            
            policy = existing_policy
        else:
            policy = Policy(
                user_id=user.id,
                plan_id=plan.id,
                vehicle_make="Kia",
                vehicle_model="Seltos",
                vehicle_year=2020,
                vehicle_registration="KL-07-CU-7475",
                start_date=today,
                end_date=one_year_later,
                status="active"
            )
            db.add(policy)
        
        db.commit()
        db.refresh(policy)
        
        print("\n" + "=" * 80)
        print("✅ KIA SELTOS POLICY CREATED SUCCESSFULLY")
        print("=" * 80)
        
        print(f"\n📋 Policy Details:")
        print(f"   Policy ID: {policy.id}")
        print(f"   Policy Number: POL-2024-00007")
        print(f"   Vehicle: {policy.vehicle_year} {policy.vehicle_make} {policy.vehicle_model}")
        print(f"   Registration: {policy.vehicle_registration}")
        print(f"   Chassis Number: WVWF14601ET093171")
        print(f"   Coverage: ₹{plan.coverage_amount:,} INR ({plan.coverage_amount // 100000} lakh)")
        print(f"   Premium: ₹{plan.premium_monthly:,}/month")
        print(f"   Type: {plan.name}")
        print(f"   Status: {policy.status.upper()}")
        print(f"   Valid From: {policy.start_date.strftime('%Y-%m-%d')}")
        print(f"   Valid Until: {policy.end_date.strftime('%Y-%m-%d')}")
        
        print(f"\n👤 User Details:")
        print(f"   Email: {user.email}")
        print(f"   Password: test123")
        print(f"   Vehicle Number: {user.vehicle_number}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_kia_policy()
