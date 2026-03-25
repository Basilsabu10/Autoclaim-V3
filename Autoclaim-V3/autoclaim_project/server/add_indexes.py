import sqlite3

db_path = r"c:\Autoclaim-main\Autoclaim-V3\autoclaim_project\server\autoclaim.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

indexes = [
    "CREATE INDEX IF NOT EXISTS ix_policies_plan_id ON policies (plan_id);",
    "CREATE INDEX IF NOT EXISTS ix_policies_user_id ON policies (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_policies_vehicle_registration ON policies (vehicle_registration);",
    "CREATE INDEX IF NOT EXISTS ix_claims_user_id ON claims (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_claims_policy_id ON claims (policy_id);",
    "CREATE INDEX IF NOT EXISTS ix_claims_assigned_agent_id ON claims (assigned_agent_id);",
    "CREATE INDEX IF NOT EXISTS ix_claims_status ON claims (status);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_notifications_claim_id ON notifications (claim_id);",
    "CREATE INDEX IF NOT EXISTS ix_wallets_user_id ON wallets (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_wallet_transactions_wallet_id ON wallet_transactions (wallet_id);",
    "CREATE INDEX IF NOT EXISTS ix_wallet_transactions_claim_id ON wallet_transactions (claim_id);"
]

for idx in indexes:
    try:
        c.execute(idx)
        print(f"Executed: {idx}")
    except Exception as e:
        print(f"Error on {idx}: {e}")

conn.commit()
conn.close()
print("Indexes added successfully.")
