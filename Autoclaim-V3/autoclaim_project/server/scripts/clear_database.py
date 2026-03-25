"""
Script to clear all data from the AutoClaim database tables.

WARNING: This will permanently delete ALL data from all tables.
Use with caution!

Usage:
    python clear_database.py

The script will prompt for confirmation before proceeding.
"""

from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.db.models import User, PolicyPlan, Policy, ForensicAnalysis, Claim


def clear_all_tables():
    """
    Clear all data from all database tables.
    
    Tables are cleared in the correct order to respect foreign key constraints:
    1. ForensicAnalysis (depends on Claim)
    2. Claim (depends on User and Policy)
    3. Policy (depends on User and PolicyPlan)
    4. PolicyPlan
    5. User
    """
    db: Session = SessionLocal()
    
    try:
        print("Starting database cleanup...")
        
        # Delete in order to respect foreign key constraints
        
        # 1. Delete ForensicAnalysis (depends on Claim)
        forensic_count = db.query(ForensicAnalysis).count()
        db.query(ForensicAnalysis).delete()
        print(f"✓ Deleted {forensic_count} forensic analysis records")
        
        # 2. Delete Claims (depends on User and Policy)
        claim_count = db.query(Claim).count()
        db.query(Claim).delete()
        print(f"✓ Deleted {claim_count} claims")
        
        # 3. Delete Policies (depends on User and PolicyPlan)
        policy_count = db.query(Policy).count()
        db.query(Policy).delete()
        print(f"✓ Deleted {policy_count} policies")
        
        # 4. Delete PolicyPlans
        plan_count = db.query(PolicyPlan).count()
        db.query(PolicyPlan).delete()
        print(f"✓ Deleted {plan_count} policy plans")
        
        # 5. Delete Users
        user_count = db.query(User).count()
        db.query(User).delete()
        print(f"✓ Deleted {user_count} users")
        
        # Commit all deletions
        db.commit()
        print("\n✅ All tables have been cleared successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error occurred while clearing tables: {e}")
        raise
    
    finally:
        db.close()


def main():
    """Main function with confirmation prompt."""
    print("=" * 60)
    print("WARNING: DATABASE CLEANUP")
    print("=" * 60)
    print("\nThis script will permanently delete ALL data from:")
    print("  • Users")
    print("  • Policy Plans")
    print("  • Policies")
    print("  • Claims")
    print("  • Forensic Analyses")
    print("\nThis action CANNOT be undone!")
    print("=" * 60)
    
    confirmation = input("\nType 'DELETE ALL' to proceed: ")
    
    if confirmation == "DELETE ALL":
        print("\nProceeding with database cleanup...\n")
        clear_all_tables()
    else:
        print("\n❌ Operation cancelled. No data was deleted.")


if __name__ == "__main__":
    main()
