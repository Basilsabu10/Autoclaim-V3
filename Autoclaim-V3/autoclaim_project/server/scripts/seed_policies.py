"""
Seed Policy Data — works with any DATABASE_URL (SQLite or Neon PostgreSQL).

Creates policy plans and unlinked policies that users can claim during registration.

Usage:
  1. Set DATABASE_URL in your .env:
       - Local:  DATABASE_URL=sqlite:///./autoclaim.db
       - Neon:   DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
  2. Run:  python scripts/seed_policies.py

This script is idempotent — it skips rows that already exist.

TIP for Neon Free Tier:
  Neon suspends inactive databases after ~5 days and may delete data.
  Re-run this script after any data loss to re-seed the policies.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

from app.db.database import SessionLocal, engine, Base
from app.db.models import PolicyPlan, Policy


def create_policy_plans(db):
    """Create sample policy plan templates."""

    plans = [
        {
            "name": "Basic Coverage",
            "description": "Essential coverage for everyday drivers. Covers basic collision and liability.",
            "coverage_amount": 100000,
            "premium_monthly": 800
        },
        {
            "name": "Standard Coverage",
            "description": "Comprehensive protection with enhanced benefits. Includes collision, comprehensive, and roadside assistance.",
            "coverage_amount": 300000,
            "premium_monthly": 1500
        },
        {
            "name": "Premium Coverage",
            "description": "Maximum protection for high-value vehicles. Full coverage with zero deductible option.",
            "coverage_amount": 500000,
            "premium_monthly": 2500
        },
        {
            "name": "Ultimate Coverage",
            "description": "Ultimate insurance package with concierge service. Luxury vehicle specialist coverage.",
            "coverage_amount": 1000000,
            "premium_monthly": 4000
        },
        {
            "name": "Comprehensive",
            "description": "Comprehensive plan covering all damage types.",
            "coverage_amount": 500000,
            "premium_monthly": 2500
        },
    ]

    created_plans = {}
    for plan_data in plans:
        existing = db.query(PolicyPlan).filter(PolicyPlan.name == plan_data["name"]).first()
        if existing:
            print(f"  ✔ Plan '{plan_data['name']}' already exists (id={existing.id})")
            created_plans[plan_data["name"]] = existing.id
        else:
            plan = PolicyPlan(**plan_data)
            db.add(plan)
            db.flush()
            print(f"  ✚ Created plan '{plan_data['name']}' (id={plan.id})")
            created_plans[plan_data["name"]] = plan.id

    return created_plans


def get_or_create_unassigned_user(db):
    """Create a dummy user to hold unlinked policies."""
    from app.db.models import User
    
    email = "unassigned@autoclaim.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name="Available Policies",
            hashed_password="not_a_real_hash_login_disabled",
            role="user"
        )
        db.add(user)
        db.flush()
        print(f"  ✚ Created dummy unassigned user (id={user.id})")
    
    return user.id


def create_policies(db, plan_map, unassigned_user_id):
    """
    Create available policies linked to the dummy user.
    """
    now = datetime.utcnow()
    one_year = timedelta(days=365)

    policies = [
        {"plan": "Premium Coverage",  "make": "Honda",       "model": "City",     "year": 2022, "reg": "KL-01-AB-1234"},
        {"plan": "Premium Coverage",  "make": "Toyota",      "model": "Fortuner", "year": 2023, "reg": "KL-02-CD-5678"},
        {"plan": "Premium Coverage",  "make": "Kia",         "model": "Seltos",   "year": 2020, "reg": "KL-07-CU-7475"},
        {"plan": "Ultimate Coverage", "make": "Kia",         "model": "Seltos",   "year": 2020, "reg": "KL-07-CU-7476"},
        {"plan": "Comprehensive",     "make": "Volkswagen",  "model": "Vento",    "year": 2020, "reg": "KL-64-C-599"},
        {"plan": "Comprehensive",     "make": "Volkswagen",  "model": "Vento",    "year": 2014, "reg": "KL-63-C-599"},
        {"plan": "Comprehensive",     "make": "Suzuki",      "model": "Baleno",   "year": 2020, "reg": "KL 63 F 3227"},
        {"plan": "Standard Coverage", "make": "Maruti",      "model": "Swift",    "year": 2021, "reg": "KL-10-AA-1111"},
        {"plan": "Basic Coverage",    "make": "Hyundai",     "model": "i20",      "year": 2019, "reg": "KL-05-BB-2222"},
        {"plan": "Premium Coverage",  "make": "Tata",        "model": "Nexon",    "year": 2023, "reg": "KL-14-CC-3333"},
    ]

    for p in policies:
        existing = db.query(Policy).filter(Policy.vehicle_registration == p["reg"]).first()
        if existing:
            print(f"  ✔ Policy for {p['reg']} already exists (id={existing.id})")
        else:
            policy = Policy(
                user_id=unassigned_user_id,
                plan_id=plan_map[p["plan"]],
                vehicle_make=p["make"],
                vehicle_model=p["model"],
                vehicle_year=p["year"],
                vehicle_registration=p["reg"],
                start_date=now,
                end_date=now + one_year,
                status="active",
            )
            db.add(policy)
            db.flush()
            print(f"  ✚ Created policy for {p['reg']} (id={policy.id})")


def display_summary(db, unassigned_user_id):
    """Print a summary of the seeded data."""
    total_plans = db.query(PolicyPlan).count()
    total_policies = db.query(Policy).count()
    available = db.query(Policy).filter(Policy.user_id == unassigned_user_id).count()

    print(f"\n   Plans: {total_plans}  |  Policies: {total_policies}  |  Available for registration: {available}")

    print("\n   Available policies (users can register with these IDs):")
    free = db.query(Policy).filter(Policy.user_id == unassigned_user_id).all()
    for p in free:
        print(f"     ID {p.id}  →  {p.vehicle_year} {p.vehicle_make} {p.vehicle_model}  ({p.vehicle_registration})")


def main():
    """Main function to seed policy data."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("\n══════════════════════════════════════════════════════")
        print("  🌱 Seeding Policy Data")
        print("══════════════════════════════════════════════════════\n")

        print("Creating policy plans...")
        plan_map = create_policy_plans(db)
        print(f"\n✅ Policy plans ready ({len(plan_map)} total)\n")

        print("Creating proxy 'Unassigned' user for available policies...")
        unassigned_user_id = get_or_create_unassigned_user(db)

        print("Creating policies (unlinked, available for registration)...")
        create_policies(db, plan_map, unassigned_user_id)

        db.commit()

        display_summary(db, unassigned_user_id)

        print("\n══════════════════════════════════════════════════════")
        print("  ✅ Seed complete!")
        print("══════════════════════════════════════════════════════\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
