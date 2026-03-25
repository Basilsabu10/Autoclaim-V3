import sys
import os

# Add the server root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.db import models

def delete_user_claims(email: str):
    db = SessionLocal()
    try:
        # Find user
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"User with email {email} not found.")
            return

        print(f"Found user ID {user.id} for email {email}")

        # Find claims
        claims = db.query(models.Claim).filter(models.Claim.user_id == user.id).all()
        
        if not claims:
            print(f"No claims found for user {email}.")
            return

        print(f"Found {len(claims)} claims for user {email}. Deleting...")

        # Delete related forensic analyses first due to foreign keys
        for claim in claims:
            db.query(models.ForensicAnalysis).filter(models.ForensicAnalysis.claim_id == claim.id).delete()
            print(f" - Deleted forensic analysis for claim {claim.id}")

            # Optionally, you could delete images here from the file system, 
            # but usually, just abandoning them is safer than raw file deletes in an untracked script.
            # We will just delete the DB records.

        # Delete claims
        db.query(models.Claim).filter(models.Claim.user_id == user.id).delete()
        db.commit()
        
        print(f"Successfully deleted all {len(claims)} claims for user {email}.")
    except Exception as e:
        db.rollback()
        print(f"Error during deletion: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    delete_user_claims("user@example.com")
