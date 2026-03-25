import sqlite3
import json

db = sqlite3.connect('autoclaim.db')
cursor = db.cursor()

cursor.execute("PRAGMA table_info(users)")
users_cols = [row[1] for row in cursor.fetchall()]

cursor.execute("PRAGMA table_info(policies)")
policies_cols = [row[1] for row in cursor.fetchall()]

print("Users columns:", json.dumps(users_cols))
print("Policies columns:", json.dumps(policies_cols))

db.close()
