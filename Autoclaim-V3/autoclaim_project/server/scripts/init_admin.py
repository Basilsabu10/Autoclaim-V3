"""
Admin Account Initialization Script

This script creates the default admin account for the AutoClaim system.
Run this script once to initialize the admin account with developer-specified credentials.

Usage:
    python init_admin.py

The script is idempotent - it can be run multiple times safely.
If the admin already exists, it will skip creation.
"""

from app.db.database import SessionLocal
from app.db.models import User
from app.core.security import get_password_hash


# Developer-specified admin credentials
ADMIN_EMAIL = "admin@autoclaim.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "System Administrator"


def init_admin():
    """
    Initialize the admin account.
    
    Creates an admin user with predefined credentials if one doesn't exist.
    """
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(
            User.email == ADMIN_EMAIL
        ).first()
        
        if existing_admin:
            print(f"✓ Admin account already exists: {ADMIN_EMAIL}")
            print(f"  Role: {existing_admin.role}")
            print(f"  Created: {existing_admin.created_at}")
            return
        
        # Create admin account
        hashed_password = get_password_hash(ADMIN_PASSWORD)
        admin_user = User(
            email=ADMIN_EMAIL,
            hashed_password=hashed_password,
            role="admin",
            name=ADMIN_NAME
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("=" * 60)
        print("✅ Admin account created successfully!")
        print("=" * 60)
        print(f"Email:    {ADMIN_EMAIL}")
        print(f"Password: {ADMIN_PASSWORD}")
        print(f"Role:     {admin_user.role}")
        print(f"ID:       {admin_user.id}")
        print("=" * 60)
        print("\n⚠️  IMPORTANT: Change the default password after first login!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin account: {e}")
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing admin account...\n")
    init_admin()
