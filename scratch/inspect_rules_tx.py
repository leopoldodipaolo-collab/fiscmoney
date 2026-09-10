import sqlite3

conn = sqlite3.connect('fiscmoney.db')
conn.row_factory = sqlite3.Row

print("=== CATEGORY RULES ===")
rules = conn.execute("SELECT id, pattern, category, sub_category, tags, match_type FROM category_rules WHERE pattern LIKE '%GEDIMPIANTI%' OR pattern LIKE '%PAYPAL%'").fetchall()
for r in rules:
    print(f"Rule ID: {r['id']} | Pattern: {repr(r['pattern'])} | Cat: {r['category']} | Sub: {r['sub_category']} | Tags: {r['tags']}")

print("\n=== MATCHING TRANSACTIONS ===")
txs = conn.execute("SELECT id, date, amount, description, raw_description, category, sub_category, tags FROM transactions WHERE description LIKE '%GEDIMPIANTI%' OR raw_description LIKE '%GEDIMPIANTI%'").fetchall()
for t in txs:
    print(f"Tx ID: {t['id']} | Date: {t['date']} | Desc: {repr(t['description'])} | Raw: {repr(t['raw_description'])} | Cat: {t['category']} | Sub: {t['sub_category']} | Tags: {t['tags']}")

conn.close()
