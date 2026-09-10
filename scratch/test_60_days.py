import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, get_db_connection

client = app.test_client()
test_email = f"tester60_{int(datetime.now().timestamp())}@test.it"
res = client.post('/register', data={
    'full_name': 'Tester Sessanta Giorni',
    'email': test_email,
    'password': 'password123',
    'privacy_consent': '1'
}, follow_redirects=True)

conn = get_db_connection()
user = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
conn.execute("DELETE FROM users WHERE email = ?", (test_email,))
conn.commit()
conn.close()

assert user is not None
assert user['subscription_plan'] == 'PRO_ANNUAL'
expected = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
assert user['subscription_expires_at'] == expected
print(f"[SUCCESS] User created with 60-day trial: plan={user['subscription_plan']}, expires={user['subscription_expires_at']}")
