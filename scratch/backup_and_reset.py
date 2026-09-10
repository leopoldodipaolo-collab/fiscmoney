import sqlite3
import os
import shutil
from datetime import datetime

# 1. Create backups folder if not exists
os.makedirs('backups', exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = os.path.join('backups', f'fiscmoney_backup_{timestamp}.db')

# Copy database
shutil.copy2('fiscmoney.db', backup_path)
print(f"[OK] Backup created successfully: {backup_path} ({os.path.getsize(backup_path)} bytes)")

# 2. Reset transactions, custom rules and balances in Workspace 2 (Leopoldo)
conn = sqlite3.connect('fiscmoney.db')
cursor = conn.cursor()

# Get stats before reset
tx_count = cursor.execute("SELECT count(*) FROM transactions WHERE workspace_id = 2").fetchone()[0]
rules_count = cursor.execute("SELECT count(*) FROM category_rules WHERE workspace_id = 2").fetchone()[0]
accounts_count = cursor.execute("SELECT count(*) FROM accounts WHERE workspace_id = 2").fetchone()[0]

print(f"\n[STATS] Pre-reset stats for Workspace 2 (Leopoldo):")
print(f"  - Transactions: {tx_count}")
print(f"  - Custom Category Rules: {rules_count}")
print(f"  - Accounts: {accounts_count}")

# Reset Transactions
cursor.execute("DELETE FROM transactions WHERE workspace_id = 2")

# Reset Custom User Category Rules (so new Global Rules are tested cleanly)
cursor.execute("DELETE FROM category_rules WHERE workspace_id = 2")

# Reset Accounts (or reset balance to 0)
cursor.execute("DELETE FROM accounts WHERE workspace_id = 2")

# Reset Paystubs if any in workspace 2
cursor.execute("DELETE FROM paystubs WHERE workspace_id = 2")

# Keep global category rules intact
global_rules_count = cursor.execute("SELECT count(*) FROM global_category_rules").fetchone()[0]
print(f"\n[RULES] Global Master Rules intact: {global_rules_count} rules ready for testing")

conn.commit()
conn.close()

print(f"\n[DONE] Workspace 2 (Leopoldo) successfully reset and ready for clean re-import & testing!")
