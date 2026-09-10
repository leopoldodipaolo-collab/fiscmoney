import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import get_db_connection
conn = get_db_connection()
conn.execute("DELETE FROM users WHERE email LIKE '%@test.it'")
conn.commit()
conn.close()
print("Cleaned up test users successfully")
