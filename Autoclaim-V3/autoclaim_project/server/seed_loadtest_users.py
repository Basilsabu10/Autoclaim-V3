"""
Create dedicated load-test seed accounts in autoclaim.db.
Run once before executing k6_load_test.js.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.abspath('.'))
from app.core.security import get_password_hash

DB = r"c:\Autoclaim-main\Autoclaim-V3\autoclaim_project\server\autoclaim.db"
PASSWORD = "loadtest123"
hashed = get_password_hash(PASSWORD)

USERS = [
    # (email, name, role)
    ("loadtest1@autoclaim.com", "Load Test User 1", "user"),
    ("loadtest2@autoclaim.com", "Load Test User 2", "user"),
    ("loadtest3@autoclaim.com", "Load Test User 3", "user"),
    ("loadtest4@autoclaim.com", "Load Test User 4", "user"),
    ("loadtest5@autoclaim.com", "Load Test User 5", "user"),
    ("loadtest_agent@autoclaim.com", "Load Test Agent", "agent"),
]

conn = sqlite3.connect(DB)
c = conn.cursor()

for email, name, role in USERS:
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    if c.fetchone():
        # Update password to ensure it matches
        c.execute("UPDATE users SET hashed_password=?, name=?, role=?, is_active=1 WHERE email=?",
                  (hashed, name, role, email))
        print(f"  Updated: {email}")
    else:
        from datetime import datetime
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        c.execute("""
            INSERT INTO users (email, hashed_password, role, name, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (email, hashed, role, name, now))
        print(f"  Created: {email}")

conn.commit()
conn.close()
print(f"\nDone! All seed accounts use password: '{PASSWORD}'")
