import sys
sys.path.insert(0, '.')
from database import get_db_connection
from services.couple_split_engine import get_couple_split_analytics

conn = get_db_connection()
workspaces = conn.execute("SELECT * FROM workspaces").fetchall()
print("Workspaces:", [dict(w) for w in workspaces])

users = conn.execute("SELECT * FROM users").fetchall()
print("Users:", [dict(u) for u in users])

for w in workspaces:
    wid = w["id"]
    print(f"\n--- Workspace {wid}: {w['name']} ---")
    tx_list = conn.execute("SELECT id, date, description, amount, category, is_shared, tags, profile_id FROM transactions WHERE workspace_id = ? ORDER BY date DESC LIMIT 25", (wid,)).fetchall()
    for t in tx_list:
        print(f"ID {t['id']}: {t['date']} | {t['description']} | €{t['amount']} | Cat: {t['category']} | is_shared={t['is_shared']}")

    split_res = get_couple_split_analytics(wid, preset='THIS_MONTH')
    print("\nSplit analytics result:")
    print("Total shared:", split_res.get("total_shared"))
    print("P1 spent:", split_res.get("p1_total"))
    print("P2 spent:", split_res.get("p2_total"))
    print("Settlement:", split_res.get("settlement"))
    print("Categories:", split_res.get("category_matrix"))
