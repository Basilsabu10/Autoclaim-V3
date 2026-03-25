"""Create policy POL-2024-00010 for Kia Seltos KL-07-CU-7476."""
from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.db.models import User, PolicyPlan, Policy

db = SessionLocal()

user = db.query(User).filter(User.email == "user@example.com").first()
if not user:
    print("user@example.com not found!")
    for u in db.query(User).all():
        print(f"  {u.id}: {u.email} ({u.role})")
    db.close()
    exit(1)

plan = db.query(PolicyPlan).filter(PolicyPlan.name == "Comprehensive Plan").first()
if not plan:
    plan = PolicyPlan(
        name="Comprehensive Plan",
        description="Full coverage including theft, accidents, natural disasters",
        coverage_amount=500000,
        premium_monthly=2500
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    print(f"Created plan: {plan.name}")

today = datetime.now()
one_year = today + timedelta(days=365)

policy = Policy(
    user_id=user.id,
    plan_id=plan.id,
    vehicle_make="Kia",
    vehicle_model="Seltos",
    vehicle_year=2020,
    vehicle_registration="KL-07-CU-7476",
    start_date=today,
    end_date=one_year,
    status="active"
)
db.add(policy)
db.commit()
db.refresh(policy)

print("=" * 60)
print("Policy created successfully!")
print("=" * 60)
print(f"  Policy ID:    {policy.id}")
print(f"  Policy No:    POL-2024-00010")
print(f"  Vehicle:      {policy.vehicle_year} {policy.vehicle_make} {policy.vehicle_model}")
print(f"  Registration: {policy.vehicle_registration}")
print(f"  Chase Number: WVWF14601ET093171")
print(f"  Coverage:     Rs.{plan.coverage_amount:,}")
print(f"  Type:         {plan.name}")
print(f"  Status:       {policy.status.upper()}")
sd = policy.start_date.strftime("%Y-%m-%d")
ed = policy.end_date.strftime("%Y-%m-%d")
print(f"  Valid:        {sd} to {ed}")
print(f"  User:         {user.email}")
db.close()
