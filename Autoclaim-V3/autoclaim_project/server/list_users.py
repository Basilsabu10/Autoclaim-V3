import sqlite3

conn = sqlite3.connect("autoclaim.db")
cur = conn.cursor()
cur.execute("SELECT id, email, role, name, is_active FROM users ORDER BY id")
rows = cur.fetchall()

print(f"{'ID':<4} {'Email':<35} {'Role':<10} {'Name':<20} {'Active'}")
print("-" * 80)
for r in rows:
    print(f"{r[0]:<4} {r[1]:<35} {r[2]:<10} {str(r[3] or ''):<20} {'Yes' if r[4] else 'No'}")

conn.close()
