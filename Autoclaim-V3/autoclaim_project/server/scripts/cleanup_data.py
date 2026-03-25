"""
Cleanup script to:
1. Delete claim #5 (and its forensic analysis)
2. Unlink user@example.com from policy POL-2024-00007
3. Delete user@example.com (and all their remaining claims/forensics)
"""

from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import User, Policy, Claim, ForensicAnalysis


def main():
    db = SessionLocal()
    try:
        # Find user
        user = db.query(User).filter(User.email == "user@example.com").first()
        if not user:
            print("User user@example.com not found.")
            return
        print(f"Found user: {user.email} (ID: {user.id})")

        # Step 1: Delete ALL claims by this user (including claim #5) and their forensic analyses
        all_claims = db.query(Claim).filter(Claim.user_id == user.id).all()
        print(f"Found {len(all_claims)} claims by this user")
        for claim in all_claims:
            # Delete forensic analysis first (child)
            forensic = db.query(ForensicAnalysis).filter(ForensicAnalysis.claim_id == claim.id).first()
            if forensic:
                db.delete(forensic)
                print(f"  Deleted forensic analysis for claim #{claim.id}")
            db.delete(claim)
            print(f"  Deleted claim #{claim.id}")
        db.flush()

        # Step 2: Unlink user from policy POL-2024-00007
        # Find the policy by registration and start_date
        policy = db.query(Policy).filter(
            Policy.vehicle_registration == "KL-07-CU-7475",
            Policy.start_date == datetime(2026, 2, 12)
        ).first()

        if not policy:
            # Fallback: find any policy linked to this user
            policy = db.query(Policy).filter(Policy.user_id == user.id).first()

        if policy:
            admin = db.query(User).filter(User.email == "admin@autoclaim.com").first()
            if admin:
                policy.user_id = admin.id
                print(f"  Unlinked user from policy (ID: {policy.id}), reassigned to admin")
            else:
                print("  Admin user not found, cannot reassign policy")
        else:
            print("  Policy POL-2024-00007 not found")

        # Also reassign any other policies owned by this user
        other_policies = db.query(Policy).filter(Policy.user_id == user.id).all()
        for p in other_policies:
            admin = db.query(User).filter(User.email == "admin@autoclaim.com").first()
            if admin:
                p.user_id = admin.id
                print(f"  Reassigned policy ID {p.id} to admin")
        db.flush()

        # Clear the user's policy_id field
        if user.policy_id:
            print(f"  Cleared user.policy_id = '{user.policy_id}'")
            user.policy_id = None

        # Step 3: Delete the user
        db.delete(user)
        print(f"  Deleted user {user.email}")

        db.commit()
        print("\nAll cleanup operations completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
