import sys
sys.path.insert(0, '.')
from app import get_db_connection
conn = get_db_connection()
tables = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    if 'profile' in t['sql'].lower():
        print(f"Table: {t['name']}")
        print(f"  Schema: {t['sql']}\n")
