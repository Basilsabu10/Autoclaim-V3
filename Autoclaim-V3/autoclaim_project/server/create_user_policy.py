import sqlite3
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath('.'))
from app.core.security import get_password_hash


# Database setup
db_path = r'c:\Autoclaim-main\Autoclaim-V3\autoclaim_project\server\autoclaim.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Data to insert
    email = "user2@example.com"
    name = "user2"
    password = "password123"
    hashed_password = get_password_hash(password)
    role = "user"
    vehicle_registration = "KL 63 F 3227"
    vehicle_make = "Suzuki"
    vehicle_model = "Baleno"
    vehicle_year = 2020
    vehicle_number = vehicle_registration
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
        print(f"User {email} already exists with ID: {user_id}. Updating name...")
        cursor.execute("UPDATE users SET name=?, vehicle_number=? WHERE id=?", (name, vehicle_number, user_id))
    else:
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        cursor.execute("""
        INSERT INTO users (email, hashed_password, role, name, vehicle_number, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (email, hashed_password, role, name, vehicle_number, created_at))
        user_id = cursor.lastrowid
        print(f"User {email} created successfully with ID: {user_id}")

    # Get 'Comprehensive' plan id
    cursor.execute("SELECT id FROM policy_plans WHERE name='Comprehensive'")
    plan = cursor.fetchone()
    if not plan:
        print("Plan 'Comprehensive' not found, defaulting to plan ID 1")
        plan_id = 1
    else:
        plan_id = plan[0]

    # Check if policy exists
    cursor.execute("SELECT id FROM policies WHERE vehicle_registration=?", (vehicle_registration,))
    policy = cursor.fetchone()
    if policy:
        print(f"Policy for {vehicle_registration} already exists. Updating plan and dates...")
        start_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        end_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S.%f")
        cursor.execute("""
        UPDATE policies 
        SET user_id=?, plan_id=?, vehicle_make=?, vehicle_model=?, vehicle_year=?, start_date=?, end_date=?, status='active'
        WHERE id=?
        """, (user_id, plan_id, vehicle_make, vehicle_model, vehicle_year, start_date, end_date, policy[0]))
    else:
        start_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        end_date = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S.%f")
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        cursor.execute("""
        INSERT INTO policies 
        (user_id, plan_id, vehicle_make, vehicle_model, vehicle_year, vehicle_registration, start_date, end_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """, (user_id, plan_id, vehicle_make, vehicle_model, vehicle_year, vehicle_registration, start_date, end_date, created_at))
        print("Policy inserted successfully! ID:", cursor.lastrowid)
        
        # Link policy back to user
        policy_id = cursor.lastrowid
        cursor.execute("UPDATE users SET policy_id=? WHERE id=?", (policy_id, user_id))

    conn.commit()
    print("Database transaction committed successfully.")

except Exception as e:
    print("Error:", e)
    conn.rollback()
finally:
    if 'conn' in locals():
        conn.close()
