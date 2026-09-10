import sys
sys.path.insert(0, '.')
from app import app, get_db_connection

conn = get_db_connection()
# Check profiles
profiles = conn.execute("SELECT id, workspace_id, name, is_primary FROM profiles").fetchall()
print("Current profiles in DB:")
for p in profiles:
    print(" ", dict(p))

conn.close()
