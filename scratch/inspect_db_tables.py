import sqlite3
import os

conn = sqlite3.connect('fiscmoney.db')
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables in fiscmoney.db:")
for t in tables:
    tname = t['name']
    cnt = conn.execute(f"SELECT count(*) FROM {tname}").fetchone()[0]
    print(f"  - {tname}: {cnt} rows")

print("\nUsers:")
for u in conn.execute("SELECT * FROM users").fetchall():
    print(" ", dict(u))

print("\nWorkspaces:")
for w in conn.execute("SELECT * FROM workspaces").fetchall():
    print(" ", dict(w))

print("\nProfiles:")
for p in conn.execute("SELECT * FROM profiles").fetchall():
    print(" ", dict(p))

print("\nAccounts:")
for a in conn.execute("SELECT * FROM accounts").fetchall():
    print(" ", dict(a))
