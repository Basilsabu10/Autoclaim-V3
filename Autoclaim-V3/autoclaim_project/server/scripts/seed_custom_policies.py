"""
Seed Custom Policy Data

Creates the specific dummy policies as requested:
- POL-2024-00001: Kia Seltos 2020 (KL-07-CU-7475) - Comprehensive Plan
- POL-2024-00007: Kia Seltos 2020 (KL-07-CU-7475) - Comprehensive - 5 Lakh
"""

from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import User, PolicyPlan, Policy


def create_or_get_comprehensive_plan(db):
    """Create or retrieve the Comprehensive - 5 Lakh plan."""
    
    plan_name = "Comprehensive - 5 Lakh"
    
    # Check if plan already exists
    existing = db.query(PolicyPlan).filter(PolicyPlan.name == plan_name).first()
    if existing:
        print(f"  ✓ Policy plan '{plan_name}' already exists")
        return existing
    
    # Create new plan
    plan = PolicyPlan(
        name=plan_name,
        description="Comprehensive coverage with ₹5 Lakh maximum claim limit. Complete protection for your vehicle.",
        coverage_amount=500000,  # ₹500,000 = ₹5 Lakh
        premium_monthly=400
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    print(f"  ✓ Created policy plan: {plan.name}")
    return plan


def create_or_get_comprehensive_basic_plan(db):
    """Create or retrieve the basic Comprehensive Plan."""
    
    plan_name = "Comprehensive Plan"
    
    # Check if plan already exists
    existing = db.query(PolicyPlan).filter(PolicyPlan.name == plan_name).first()
    if existing:
        print(f"  ✓ Policy plan '{plan_name}' already exists")
        return existing
    
    # Create new plan
    plan = PolicyPlan(
        name=plan_name,
        description="Comprehensive insurance coverage for everyday protection.",
        coverage_amount=500000,  # ₹500,000 = ₹5 Lakh
        premium_monthly=400
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    print(f"  ✓ Created policy plan: {plan.name}")
    return plan


def create_custom_policies(db):
    """Create the two specific custom policies."""
    
    # Get or create the admin user (or use any existing user)
    admin = db.query(User).filter(User.email == "admin@autoclaim.com").first()
    if not admin:
        print("  ⚠️  Admin user not found. Creating a test user...")
        # You might want to create a test user or use an existing one
        # For now, let's just return if no admin exists
        print("  ❌ Please ensure admin user exists before running this script.")
        return []
    
    # Get or create the policy plans
    comprehensive_plan = create_or_get_comprehensive_basic_plan(db)
    comprehensive_5l_plan = create_or_get_comprehensive_plan(db)
    
    # Define the custom policies
    custom_policies = [
        {
            "policy_number": "POL-2024-00001",
            "user_id": admin.id,
            "plan_id": comprehensive_plan.id,
            "vehicle_make": "Kia",
            "vehicle_model": "Seltos",
            "vehicle_year": 2020,
            "vehicle_registration": "KL-07-CU-7475",
            "start_date": datetime(2026, 2, 10),
            "end_date": datetime(2027, 2, 10),
            "status": "active"
        },
        {
            "policy_number": "POL-2024-00007",
            "user_id": admin.id,
            "plan_id": comprehensive_5l_plan.id,
            "vehicle_make": "Kia",
            "vehicle_model": "Seltos",
            "vehicle_year": 2020,
            "vehicle_registration": "KL-07-CU-7475",
            "start_date": datetime(2026, 2, 12),
            "end_date": datetime(2027, 2, 12),
            "status": "active"
        }
    ]
    
    created_policies = []
    for policy_data in custom_policies:
        policy_num = policy_data.pop("policy_number")
        
        # Check if similar policy exists (by registration and start date)
        existing = db.query(Policy).filter(
            Policy.vehicle_registration == policy_data["vehicle_registration"],
            Policy.start_date == policy_data["start_date"]
        ).first()
        
        if existing:
            print(f"  ✓ Policy {policy_num} already exists (ID: {existing.id})")
            created_policies.append(existing)
        else:
            policy = Policy(**policy_data)
            db.add(policy)
            db.commit()
            db.refresh(policy)
            created_policies.append(policy)
            print(f"  ✓ Created policy {policy_num}: {policy.vehicle_make} {policy.vehicle_model} ({policy.vehicle_registration})")
    
    return created_policies


def display_custom_policies(db):
    """Display the custom policies in a formatted way."""
    
    print("\n" + "=" * 80)
    print("  🚗 CUSTOM POLICIES")
    print("=" * 80 + "\n")
    
    # Get the Kia Seltos policies
    policies = db.query(Policy).filter(
        Policy.vehicle_registration == "KL-07-CU-7475"
    ).all()
    
    for idx, policy in enumerate(policies, 1):
        policy_number = f"POL-2024-{str(idx).zfill(5)}"
        if policy.start_date == datetime(2026, 2, 10):
            policy_number = "POL-2024-00001"
        elif policy.start_date == datetime(2026, 2, 12):
            policy_number = "POL-2024-00007"
        
        print(f"  Policy Number: {policy_number}")
        print(f"  Vehicle: {policy.vehicle_make} {policy.vehicle_model} {policy.vehicle_year}")
        print(f"  Registration: {policy.vehicle_registration}")
        print(f"  Plan: {policy.plan.name}")
        print(f"  Max Claim: ₹{policy.plan.coverage_amount:,}")
        print(f"  Status: {policy.status}")
        print(f"  Valid: {policy.start_date.strftime('%Y-%m-%d')} to {policy.end_date.strftime('%Y-%m-%d')}")
        print(f"  {'-' * 76}\n")


def main():
    """Main function to seed custom policy data."""
    db = SessionLocal()
    
    try:
        print("\n" + "=" * 80)
        print("  🌱 Seeding Custom Policy Data")
        print("=" * 80 + "\n")
        
        # Create the custom policies
        print("Creating custom policies...")
        policies = create_custom_policies(db)
        print(f"\n✅ Total policies created/verified: {len(policies)}\n")
        
        # Display the policies
        display_custom_policies(db)
        
        print("=" * 80)
        print("  ✅ Custom policy data seeding complete!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
