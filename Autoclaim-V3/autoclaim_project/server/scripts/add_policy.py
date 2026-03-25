"""
Script to add policy for Hyundai Vento with license plate KL63C599.
Run from: autoclaim_project/server/
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import SessionLocal
from app.db import models

db = SessionLocal()

try:
    # ── 1. Find "Standard Coverage" PolicyPlan ───────────────────────────────
    plan = db.query(models.PolicyPlan).filter(
        models.PolicyPlan.name == "Standard Coverage"
    ).first()

    if not plan:
        print("❌ Error: 'Standard Coverage' plan not found in database.")
        print("Please run seed_policies.py first to create policy plans.")
        sys.exit(1)
    else:
        print(f"ℹ️  Using PolicyPlan: {plan.name} (id={plan.id})")
        print(f"   Coverage: ₹{plan.coverage_amount:,}")
        print(f"   Premium: ₹{plan.premium_monthly}/month")

    # ── 2. Check if policy already exists (avoid duplicates) ──────────────────
    existing = db.query(models.Policy).filter(
        models.Policy.vehicle_registration == "KL63C599"
    ).first()

    if existing:
        print(f"⚠️  Policy for KL63C599 already exists (id={existing.id}). Skipping.")
        sys.exit(0)

    # ── 3. Create policy ────────────────────────────────────────────────────────
    start_date = datetime(2024, 12, 12)
    # End date: 12/12/2025 (December 12, 2025)
    end_date = datetime(2025, 12, 12)

    policy = models.Policy(
        user_id=None,  # No user assigned yet (will be assigned during registration)
        plan_id=plan.id,
        vehicle_make="Volkswagen",
        vehicle_model="Vento",
        vehicle_year=2014,
        vehicle_registration="KL63C599",
        start_date=start_date,
        end_date=end_date,
        status="inactive",  # requested as inactive
    )
    db.add(policy)
    db.flush()

    db.commit()
    
    print(f"\n✅ Policy created successfully!")
    print(f"   Policy DB id       : {policy.id}")
    print(f"   Vehicle Make       : {policy.vehicle_make}")
    print(f"   Vehicle Model      : {policy.vehicle_model}")
    print(f"   Vehicle Year       : {policy.vehicle_year}")
    print(f"   License Plate      : {policy.vehicle_registration}")
    print(f"   Vehicle Color      : Silver")
    print(f"   Coverage Amount    : ₹{plan.coverage_amount:,}")
    print(f"   Premium Monthly    : ₹{plan.premium_monthly}")
    print(f"   Start Date         : {start_date.strftime('%d/%m/%Y')}")
    print(f"   End Date           : {end_date.strftime('%d/%m/%Y')}")
    print(f"   Status             : {policy.status}")
    print(f"   Assigned User      : (None - to be assigned at registration)")

except Exception as e:
    db.rollback()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()