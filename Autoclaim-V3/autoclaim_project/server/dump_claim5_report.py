import sqlite3
import json

conn = sqlite3.connect(r'c:\Autoclaim-main\Autoclaim-V3\autoclaim_project\server\autoclaim.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

def dump_table(table_name, col_name, val):
    try:
        c.execute(f"SELECT * FROM {table_name} WHERE {col_name} = ?", (val,))
        rows = [dict(r) for r in c.fetchall()]
        print(f"\n=== {table_name.upper()} ===")
        print(json.dumps(rows, indent=2, default=str))
        return rows
    except Exception as e:
        print(f"Error querying {table_name}: {e}")
        return []

print("=== START ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]

claim_rows = dump_table("claims", "id", 5)
if claim_rows:
    claim = claim_rows[0]
    if claim.get("user_id"):
        dump_table("users", "id", claim["user_id"])
    if claim.get("policy_id"):
        dump_table("policies", "id", claim["policy_id"])
        
    dump_table("forensic_analyses", "claim_id", 5)
    
    # Check verification rules, etc
    for tbl in tables:
        if "verif" in tbl.lower() or "rule" in tbl.lower() or "result" in tbl.lower():
            if tbl != "forensic_analyses":
                dump_table(tbl, "claim_id", 5)

conn.close()
