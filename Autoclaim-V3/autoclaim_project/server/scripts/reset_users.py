from database import SessionLocal, engine
from models import User
from sqlalchemy import text

def reset_users():
    db = SessionLocal()
    try:
        # Delete all users
        num_deleted = db.query(User).delete()
        db.commit()
        print(f"Successfully deleted {num_deleted} users.")
        print("You can now register a new user.")
    except Exception as e:
        print(f"Error resetting users: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Forcing reset of all users...")
    reset_users()
