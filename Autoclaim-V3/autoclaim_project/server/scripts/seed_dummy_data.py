"""
Seed Comprehensive Dummy Data for AutoClaim System

Creates all the dummy data for:
- Policy Plans
- Users
- Policies
- Claims
- Forensic Analyses
"""

from datetime import datetime, timedelta
from app.db.database import SessionLocal
from app.db.models import User, PolicyPlan, Policy, Claim, ForensicAnalysis
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    # Trim password to avoid bcrypt's 72-byte limit
    return pwd_context.hash(password[:50])


def create_policy_plans(db):
    """Create policy plans based on the provided dummy data."""
    
    print("\n🏷️  Creating Policy Plans...")
    
    plans_data = [
        {
            "name": "Basic Third Party",
            "description": "Covers third-party damages only. Minimum required coverage.",
            "coverage_amount": 100000,
            "premium_monthly": 500
        },
        {
            "name": "Comprehensive",
            "description": "Full coverage including own damage, theft, and third-party liability.",
            "coverage_amount": 500000,
            "premium_monthly": 2000
        },
        {
            "name": "Premium Comprehensive",
            "description": "Maximum coverage with zero depreciation and roadside assistance.",
            "coverage_amount": 1000000,
            "premium_monthly": 4000
        },
        {
            "name": "Comprehensive Plan",
            "description": "Full coverage insurance",
            "coverage_amount": 500000,
            "premium_monthly": 5000
        },
        {
            "name": "Comprehensive - 5 Lakh",
            "description": "Comprehensive insurance coverage with ₹5,00,000 maximum claim amount",
            "coverage_amount": 500000,
            "premium_monthly": 2500
        }
    ]
    
    created_plans = []
    for plan_data in plans_data:
        # Check if plan already exists by name
        existing = db.query(PolicyPlan).filter(PolicyPlan.name == plan_data["name"]).first()
        if existing:
            print(f"   ✓ Plan '{plan_data['name']}' already exists (ID: {existing.id})")
            created_plans.append(existing)
        else:
            plan = PolicyPlan(**plan_data)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            created_plans.append(plan)
            print(f"   ✓ Created: {plan.name} (ID: {plan.id})")
    
    return created_plans


def create_users(db):
    """Create users based on the provided dummy data."""
    
    print("\n👥 Creating Users...")
    
    users_data = [
        {
            "email": "userm@gmail.com",
            "hashed_password": hash_password("password123"),
            "role": "user",
            "name": None,
            "policy_id": "POL-2024-00001"
        },
        {
            "name": "System Administrator",
            "email": "admin@autoclaim.com",
            "hashed_password": hash_password("admin123"),
            "role": "admin",
            "policy_id": None
        },
        {
            "name": "agent1",
            "email": "agent1@autoclaim.com",
            "hashed_password": hash_password("agent123"),
            "role": "agent",
            "policy_id": None
        },
        {
            "email": "user@mail.com",
            "hashed_password": hash_password("password123"),
            "role": "user",
            "name": None,
            "policy_id": "POL-2024-00007"
        }
    ]
    
    created_users = []
    for user_data in users_data:
        # Check if user already exists
        existing = db.query(User).filter(User.email == user_data["email"]).first()
        if existing:
            print(f"   ✓ User '{user_data['email']}' already exists (ID: {existing.id})")
            created_users.append(existing)
        else:
            user = User(**user_data)
            db.add(user)
            db.commit()
            db.refresh(user)
            created_users.append(user)
            print(f"   ✓ Created: {user.email} (Role: {user.role})")
    
    return created_users


def create_policies(db, users, plans):
    """Create policies based on the provided dummy data."""
    
    print("\n🚗 Creating Policies...")
    
    # Find the users and plans we need
    user_1 = next((u for u in users if u.email == "userm@gmail.com"), None)
    user_4 = next((u for u in users if u.email == "user@mail.com"), None)
    plan_4 = next((p for p in plans if p.name == "Comprehensive Plan"), None)
    plan_5 = next((p for p in plans if p.name == "Comprehensive - 5 Lakh"), None)
    
    if not all([user_1, user_4, plan_4, plan_5]):
        print("   ⚠️  Required users or plans not found!")
        print(f"   user_1: {user_1}, user_4: {user_4}, plan_4: {plan_4}, plan_5: {plan_5}")
        return []
    
    policies_data = [
        {
            "user_id": user_1.id,
            "plan_id": plan_4.id,
            "vehicle_make": "Kia",
            "vehicle_model": "Seltos",
            "vehicle_year": 2020,
            "vehicle_registration": "KL-07-CU-7475",
            "start_date": datetime(2026, 2, 10),
            "end_date": datetime(2027, 2, 10),
            "status": "active"
        },
        {
            "user_id": user_4.id,
            "plan_id": plan_5.id,
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
    for idx, policy_data in enumerate(policies_data):
        # Generate policy number
        policy_number = f"POL-2024-{str(idx*6 + 1).zfill(5)}"
        
        # Check if policy already exists by vehicle registration and user
        existing = db.query(Policy).filter(
            Policy.vehicle_registration == policy_data["vehicle_registration"],
            Policy.user_id == policy_data["user_id"]
        ).first()
        
        if existing:
            print(f"   ✓ Policy '{policy_number}' already exists (ID: {existing.id})")
            created_policies.append(existing)
        else:
            policy = Policy(**policy_data)
            db.add(policy)
            db.commit()
            db.refresh(policy)
            created_policies.append(policy)
            print(f"   ✓ Created: {policy_number} - {policy.vehicle_make} {policy.vehicle_model} ({policy.vehicle_registration})")
    
    return created_policies


def create_claims(db, users, policies):
    """Create claims based on the provided dummy data."""
    
    print("\n📄 Creating Claims...")
    
    # Find the user and policy we need
    user_1 = next((u for u in users if u.email == "userm@gmail.com"), None)
    policy_1 = next((p for p in policies if p.user_id == user_1.id), None) if user_1 else None
    
    if not all([user_1, policy_1]):
        print("   ⚠️  Required user or policy not found!")
        print(f"   user_1: {user_1}, policy_1: {policy_1}")
        return []
    
    claims_data = [
        {
            "user_id": user_1.id,
            "policy_id": policy_1.id,
            "description": "Vehicle: 2020 kia seltos\n\nLicense Plate: KL-07-CU-...",
            "status": "error",
            "created_at": datetime(2026, 1, 31)
        }
    ]
    
    created_claims = []
    for claim_data in claims_data:
        # Check if claim already exists with the same description and user
        existing = db.query(Claim).filter(
            Claim.user_id == claim_data["user_id"],
            Claim.description == claim_data["description"]
        ).first()
        
        if existing:
            print(f"   ✓ Claim ID {existing.id} already exists")
            created_claims.append(existing)
        else:
            claim = Claim(**claim_data)
            db.add(claim)
            db.commit()
            db.refresh(claim)
            created_claims.append(claim)
            print(f"   ✓ Created: Claim ID {claim.id} - Status: {claim.status}")
    
    return created_claims


def create_forensic_analyses(db, claims):
    """Create forensic analyses based on the provided dummy data."""
    
    print("\n🔍 Creating Forensic Analyses...")
    
    if not claims:
        print("   ⚠️  No claims found!")
        return []
    
    created_forensics = []
    for claim in claims:
        # Check if forensic analysis already exists
        existing = db.query(ForensicAnalysis).filter(
            ForensicAnalysis.claim_id == claim.id
        ).first()
        
        if existing:
            print(f"   ✓ Forensic Analysis for Claim ID {claim.id} already exists")
            created_forensics.append(existing)
        else:
            forensic = ForensicAnalysis(
                claim_id=claim.id,
                vehicle_make=None,
                vehicle_model=None,
                ai_severity=None
            )
            db.add(forensic)
            db.commit()
            db.refresh(forensic)
            created_forensics.append(forensic)
            print(f"   ✓ Created: Analysis ID {forensic.id} for Claim ID {forensic.claim_id}")
    
    return created_forensics


def display_summary(db):
    """Display a summary of all seeded data."""
    
    print("\n" + "=" * 70)
    print("📋 CURRENT DATABASE DUMMY DATA")
    print("=" * 70)
    
    # Policy Plans
    print("\n🏷️  POLICY PLANS:\n")
    plans = db.query(PolicyPlan).all()
    for plan in plans:
        print(f"   ID: {plan.id}")
        print(f"   Name: {plan.name}")
        print(f"   Description: {plan.description}")
        print(f"   Coverage: ₹{plan.coverage_amount:,}")
        print(f"   Premium (Monthly): ₹{plan.premium_monthly}")
        print()
    
    # Policies
    print("🚗 POLICIES:\n")
    policies = db.query(Policy).all()
    for idx, policy in enumerate(policies):
        policy_num = f"POL-2024-{str(idx*6 + 1).zfill(5)}"
        print(f"   Policy Number: {policy_num}")
        print(f"   Vehicle: {policy.vehicle_make} {policy.vehicle_model} {policy.vehicle_year}")
        print(f"   Registration: {policy.vehicle_registration}")
        print(f"   Plan: {policy.plan.name}")
        print(f"   Max Claim: ₹{policy.plan.coverage_amount:,}")
        print(f"   Status: {policy.status}")
        print(f"   Valid: {policy.start_date.strftime('%Y-%m-%d')} to {policy.end_date.strftime('%Y-%m-%d')}")
        print()
    
    # Users
    print("\n👥 USERS:\n")
    users = db.query(User).all()
    for user in users:
        print(f"   ID: {user.id}")
        print(f"   Name: {user.name}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role}")
        print(f"   Policy: {user.policy_id if user.policy_id else 'None assigned'}")
        print()
    
    # Claims
    print("\n📄 CLAIMS:\n")
    claims = db.query(Claim).all()
    for claim in claims:
        print(f"   Claim ID: {claim.id}")
        print(f"   User: {claim.user.email}")
        print(f"   Status: {claim.status}")
        print(f"   Accident Date: {claim.created_at.strftime('%Y-%m-%d')}")
        print(f"   Description: {claim.description[:80]}...")
        print()
    
    # Forensic Analyses
    print("\n🔍 FORENSIC ANALYSES:\n")
    forensics = db.query(ForensicAnalysis).all()
    for forensic in forensics:
        print(f"   Analysis ID: {forensic.id}")
        print(f"   Claim ID: {forensic.claim_id}")
        print(f"   Vehicle: {forensic.vehicle_make} {forensic.vehicle_model}")
        print(f"   AI Severity: {forensic.ai_severity if forensic.ai_severity else 'N/A'}")
        print()
    
    print("=" * 70)


def main():
    """Main function to seed all dummy data."""
    db = SessionLocal()
    
    try:
        print("\n" + "=" * 70)
        print("🌱 SEEDING AUTOCLAIM DUMMY DATA")
        print("=" * 70)
        
        # Create all data in order
        plans = create_policy_plans(db)
        users = create_users(db)
        policies = create_policies(db, users, plans)
        claims = create_claims(db, users, policies)
        forensics = create_forensic_analyses(db, claims)
        
        # Display summary
        display_summary(db)
        
        print("\n" + "=" * 70)
        print("✅ DUMMY DATA SEEDING COMPLETE!")
        print("=" * 70)
        print(f"\nCreated:")
        print(f"  • {len(plans)} Policy Plans")
        print(f"  • {len(users)} Users")
        print(f"  • {len(policies)} Policies")
        print(f"  • {len(claims)} Claims")
        print(f"  • {len(forensics)} Forensic Analyses")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
