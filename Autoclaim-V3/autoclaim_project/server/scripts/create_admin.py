import sys
import os

# Add server directory to path
sys.path.append(os.path.join(os.getcwd(), 'app'))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import models
from app.core.security import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        email = "admin@autoclaim.com"
        password = "admin"
        
        # Check if exists
        user = db.query(models.User).filter(models.User.email == email).first()
        hashed_pw = get_password_hash(password)
        
        if user:
            print(f"User {email} already exists.")
            # Always update password to ensure we know it
            user.hashed_password = hashed_pw
            print("Updated password to 'admin'")
            
            if user.role != "admin":
                print(f"Updating role to admin (was {user.role})")
                user.role = "admin"
            
            db.commit()
            return

        print(f"Creating new admin user: {email}")
        hashed_pw = get_password_hash(password)
        new_admin = models.User(
            email=email,
            hashed_password=hashed_pw,
            role="admin",
            name="System Admin"
        )
        db.add(new_admin)
        db.commit()
        print("Admin user created successfully.")
        
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
