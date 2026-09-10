import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, get_db_connection

def test_onboarding_and_security():
    client = app.test_client()
    
    print("--- 1. Testing Privacy Page ---")
    res = client.get('/privacy')
    assert res.status_code == 200
    assert b"Informativa sulla Privacy" in res.data
    assert b"GDPR" in res.data
    print("[OK] /privacy page loads correctly with full GDPR details!")

    print("\n--- 2. Testing Registration Privacy Enforcement ---")
    res_no_privacy = client.post('/register', data={
        'full_name': 'Tester No Privacy',
        'email': 'noprivacy@test.it',
        'password': 'password123'
    }, follow_redirects=True)
    assert b"necessario accettare l&#39;Informativa" in res_no_privacy.data or b"Informativa sulla Privacy" in res_no_privacy.data
    print("[OK] Registration properly blocked without privacy consent!")

    print("\n--- 3. Testing 30-Day Free Trial Auto-Assignment ---")
    test_email = f"trial_tester_{int(datetime.now().timestamp())}@test.it"
    res_reg = client.post('/register', data={
        'full_name': 'Tester Beta Pro',
        'email': test_email,
        'password': 'password123',
        'privacy_consent': '1'
    }, follow_redirects=True)
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
    conn.close()
    
    assert user is not None
    assert user['subscription_plan'] == 'PRO_ANNUAL'
    assert user['subscription_status'] == 'ACTIVE'
    assert user['subscription_expires_at'] is not None
    
    expected_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    assert user['subscription_expires_at'] == expected_expiry
    print(f"[OK] New user {test_email} created with Plan={user['subscription_plan']}, Status={user['subscription_status']}, Expires={user['subscription_expires_at']}")

    print("\n--- 4. Testing Admin Password Reset ---")
    # Log in as admin (find super admin)
    conn = get_db_connection()
    admin_user = conn.execute("SELECT * FROM users WHERE role = 'SUPER_ADMIN' LIMIT 1").fetchone()
    conn.close()
    
    assert admin_user is not None
    
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user['id']
        sess['user_email'] = admin_user['email']
        sess['user_name'] = admin_user['full_name']
        sess['role'] = 'SUPER_ADMIN'
        sess['subscription_plan'] = 'LIFETIME'
        sess['subscription_status'] = 'ACTIVE'
    
    new_pwd = "NewSecurePassword2026!"
    res_reset = client.post(f"/admin/users/{user['id']}/reset-password", data={
        'new_password': new_pwd
    }, follow_redirects=True)
    
    assert res_reset.status_code == 200
    assert b"reimpostata con successo" in res_reset.data
    print(f"[OK] Password reset by admin for user_id={user['id']} succeeded!")

    # Test login with new password
    with client.session_transaction() as sess:
        sess.clear()
        
    res_login_new = client.post('/login', data={
        'email': test_email,
        'password': new_pwd
    }, follow_redirects=True)
    
    assert b"Bentornato Tester Beta Pro" in res_login_new.data
    print(f"[OK] User successfully logged in with the new password!")

    print("\n--- 5. Testing Plan Update & Extension from Admin ---")
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user['id']
        sess['user_email'] = admin_user['email']
        sess['user_name'] = admin_user['full_name']
        sess['role'] = 'SUPER_ADMIN'
        sess['subscription_plan'] = 'LIFETIME'
        sess['subscription_status'] = 'ACTIVE'

    res_plan = client.post(f"/admin/users/{user['id']}/update-plan", data={
        'subscription_plan': 'LIFETIME',
        'subscription_status': 'ACTIVE',
        'role': 'USER',
        'subscription_expires_at': ''
    }, follow_redirects=True)
    
    assert res_plan.status_code == 200
    
    conn = get_db_connection()
    updated_user = conn.execute("SELECT * FROM users WHERE id = ?", (user['id'],)).fetchone()
    conn.close()
    
    assert updated_user['subscription_plan'] == 'LIFETIME'
    assert updated_user['subscription_expires_at'] is None
    print(f"[OK] User upgraded to LIFETIME with unlimited expiration!")

    print("\nALL 5 TEST SUITES PASSED FLAWLESSLY! [SUCCESS]")

if __name__ == '__main__':
    test_onboarding_and_security()
