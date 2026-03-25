import sqlite3
import sys

db_path = r'c:\Autoclaim-main\Autoclaim-V3\autoclaim_project\server\autoclaim.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get a plan
    cursor.execute("SELECT id FROM policy_plans WHERE name='Standard Coverage'")
    plan = cursor.fetchone()
    if not plan:
        print("Plan 'Standard Coverage' not found.")
        sys.exit(1)
    plan_id = plan[0]
    
    # Get a user id just in case user_id cannot be null
    cursor.execute("SELECT id FROM users LIMIT 1")
    user = cursor.fetchone()
    user_id = user[0] if user else 1

    # Check if policy exists
    cursor.execute("SELECT id FROM policies WHERE vehicle_registration='KL63C599'")
    if cursor.fetchone():
        print("Policy for KL63C599 already exists.")
        sys.exit(0)

    # Insert policy
    from datetime import datetime
    start_date = "2024-12-12 00:00:00.000000"
    end_date = "2025-12-12 00:00:00.000000"
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    
    cursor.execute("""
    INSERT INTO policies 
    (user_id, plan_id, vehicle_make, vehicle_model, vehicle_year, vehicle_registration, start_date, end_date, status, created_at)
    VALUES (?, ?, 'Volkswagen', 'Vento', 2014, 'KL63C599', ?, ?, 'inactive', ?)
    """, (user_id, plan_id, start_date, end_date, created_at))
    
    conn.commit()
    print("Policy inserted successfully! ID:", cursor.lastrowid)

except Exception as e:
    print("Error:", e)
finally:
    if 'conn' in locals():
        conn.close()
