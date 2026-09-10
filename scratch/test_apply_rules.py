import sqlite3
from services.bank_importer import apply_all_workspace_rules

count = apply_all_workspace_rules(1)
print(f"Total transactions updated by workspace rules: {count}")

conn = sqlite3.connect('fiscmoney.db')
conn.row_factory = sqlite3.Row

print("\n=== GEDIMPIANTI TRANSACTIONS AFTER SYNC ===")
txs = conn.execute("SELECT id, date, amount, description, category, sub_category, tags FROM transactions WHERE description LIKE '%GEDIMPIANTI%'").fetchall()
for t in txs:
    print(f"ID {t['id']} | Date: {t['date']} | Desc: {t['description']} | Cat: {t['category']} | Sub: {t['sub_category']} | Tags: {t['tags']}")

conn.close()
