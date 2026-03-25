"""
Seed Dummy Policy Data

Creates sample policy plans and policies for testing the AutoClaim system.
"""

from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.db.models import User, PolicyPlan, Policy


def create_policy_plans(db):
    """Create sample policy plan templates."""
    
    plans = [
        {
            "name": "Basic Coverage",
            "description": "Essential coverage for everyday drivers. Covers basic collision and liability.",
            "coverage_amount": 50000,
            "premium_monthly": 120
        },
        {
            "name": "Standard Coverage",
            "description": "Comprehensive protection with enhanced benefits. Includes collision, comprehensive, and roadside assistance.",
            "coverage_amount": 100000,
            "premium_monthly": 200
        },
        {
            "name": "Premium Coverage",
            "description": "Maximum protection for high-value vehicles. Full coverage with zero deductible option.",
            "coverage_amount": 250000,
            "premium_monthly": 350
        },
        {
            "name": "Platinum Elite",
            "description": "Ultimate insurance package with concierge service. Luxury vehicle specialist coverage.",
            "coverage_amount": 500000,
            "premium_monthly": 600
        }
    ]
    
    created_plans = []
    for plan_data in plans:
        # Check if plan already exists
        existing = db.query(PolicyPlan).filter(PolicyPlan.name == plan_data["name"]).first()
        if existing:
            print(f"  ✓ Policy plan '{plan_data['name']}' already exists")
            created_plans.append(existing)
        else:
            plan = PolicyPlan(**plan_data)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            created_plans.append(plan)
            print(f"  ✓ Created policy plan: {plan.name}")
    
    return created_plans


def create_sample_policies(db, plans):
    """Create sample policies for the admin user."""
    
    # Get admin user
    admin = db.query(User).filter(User.email == "admin@autoclaim.com").first()
    if not admin:
        print("  ⚠️  Admin user not found. Please run the server first to create admin user.")
        return []
    
    # Sample policies data
    sample_policies = [
        {
            "user_id": admin.id,
            "plan_id": plans[2].id,  # Premium Coverage
            "vehicle_make": "Tesla",
            "vehicle_model": "Model 3",
            "vehicle_year": 2023,
            "vehicle_registration": "TES3LA",
            "start_date": datetime.now() - timedelta(days=180),
            "end_date": datetime.now() + timedelta(days=185),
            "status": "active"
        },
        {
            "user_id": admin.id,
            "plan_id": plans[1].id,  # Standard Coverage
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
            "vehicle_year": 2022,
            "vehicle_registration": "CAM22RY",
            "start_date": datetime.now() - timedelta(days=90),
            "end_date": datetime.now() + timedelta(days=275),
            "status": "active"
        },
        {
            "user_id": admin.id,
            "plan_id": plans[0].id,  # Basic Coverage
            "vehicle_make": "Honda",
            "vehicle_model": "Civic",
            "vehicle_year": 2020,
            "vehicle_registration": "CIV20IC",
            "start_date": datetime.now() - timedelta(days=365),
            "end_date": datetime.now() - timedelta(days=30),
            "status": "expired"
        }
    ]
    
    created_policies = []
    for policy_data in sample_policies:
        # Check if similar policy exists
        existing = db.query(Policy).filter(
            Policy.vehicle_registration == policy_data["vehicle_registration"]
        ).first()
        
        if existing:
            print(f"  ✓ Policy for {policy_data['vehicle_registration']} already exists")
            created_policies.append(existing)
        else:
            policy = Policy(**policy_data)
            db.add(policy)
            db.commit()
            db.refresh(policy)
            created_policies.append(policy)
            print(f"  ✓ Created policy: {policy.vehicle_make} {policy.vehicle_model} ({policy.vehicle_registration})")
    
    return created_policies


def display_policy_data(db):
    """Display all policy plans and policies."""
    
    print("\n" + "=" * 80)
    print("  📋 POLICY PLANS")
    print("=" * 80 + "\n")
    
    plans = db.query(PolicyPlan).all()
    for plan in plans:
        print(f"  Plan ID: {plan.id}")
        print(f"  Name: {plan.name}")
        print(f"  Description: {plan.description}")
        print(f"  Coverage Amount: ${plan.coverage_amount:,}")
        print(f"  Monthly Premium: ${plan.premium_monthly}")
        print(f"  Active Policies: {len(plan.policies)}")
        print(f"  {'-' * 76}")
    
    print("\n" + "=" * 80)
    print("  🚗 ACTIVE POLICIES")
    print("=" * 80 + "\n")
    
    policies = db.query(Policy).all()
    for policy in policies:
        print(f"  Policy ID: {policy.id}")
        print(f"  User: {policy.user.email}")
        print(f"  Plan: {policy.plan.name}")
        print(f"  Vehicle: {policy.vehicle_year} {policy.vehicle_make} {policy.vehicle_model}")
        print(f"  Registration: {policy.vehicle_registration}")
        print(f"  Status: {policy.status.upper()}")
        print(f"  Coverage: ${policy.plan.coverage_amount:,}")
        print(f"  Monthly Premium: ${policy.plan.premium_monthly}")
        print(f"  Start Date: {policy.start_date.strftime('%Y-%m-%d')}")
        print(f"  End Date: {policy.end_date.strftime('%Y-%m-%d')}")
        print(f"  Claims: {len(policy.claims)}")
        print(f"  {'-' * 76}")


def main():
    """Main function to seed and display policy data."""
    db = SessionLocal()
    
    try:
        print("\n" + "=" * 80)
        print("  🌱 Seeding Policy Data")
        print("=" * 80 + "\n")
        
        # Create policy plans
        print("Creating policy plans...")
        plans = create_policy_plans(db)
        print(f"\n✅ Total policy plans: {len(plans)}\n")
        
        # Create sample policies
        print("Creating sample policies...")
        policies = create_sample_policies(db, plans)
        print(f"\n✅ Total policies created: {len(policies)}\n")
        
        # Display all data
        display_policy_data(db)
        
        print("\n" + "=" * 80)
        print("  ✅ Policy data seeding complete!")
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
