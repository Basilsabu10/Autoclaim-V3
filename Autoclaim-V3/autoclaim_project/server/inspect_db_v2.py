import sqlite3
import json

db_path = 'autoclaim.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def get_table_info(table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

tables = ['users', 'policies', 'policy_plans', 'claims']
schema = {}
for t in tables:
    try:
        schema[t] = get_table_info(t)
    except:
        schema[t] = "Table not found"

cursor.execute("SELECT id, name FROM policy_plans")
plans = [dict(zip(['id', 'name'], row)) for row in cursor.fetchall()]

cursor.execute("SELECT * FROM users ORDER BY id DESC LIMIT 1")
latest_user = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

result = {
    "schema": schema,
    "plans": plans,
    "latest_user": latest_user
}

print(json.dumps(result, indent=2))
conn.close()
