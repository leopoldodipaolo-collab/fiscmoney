import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, get_db_connection

def test_password_complexity():
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE email LIKE '%@test.it'")
    conn.commit()
    conn.close()

    client = app.test_client()
    
    print("--- 1. Testing Registration with Weak Passwords ---")
    
    # Too short (< 8)
    res1 = client.post('/register', data={
        'full_name': 'Test Short',
        'email': 'short@test.it',
        'password': 'Pass1!',
        'privacy_consent': '1'
    }, follow_redirects=True)
    assert b"almeno 8 caratteri" in res1.data
    print("[OK] Blocked password with < 8 chars")

    # No number
    res2 = client.post('/register', data={
        'full_name': 'Test No Num',
        'email': 'nonum@test.it',
        'password': 'PasswordSecret!',
        'privacy_consent': '1'
    }, follow_redirects=True)
    assert b"almeno un numero" in res2.data
    print("[OK] Blocked password without number")

    # No special character
    res3 = client.post('/register', data={
        'full_name': 'Test No Special',
        'email': 'nospecial@test.it',
        'password': 'Password12345',
        'privacy_consent': '1'
    }, follow_redirects=True)
    assert b"almeno un carattere speciale" in res3.data
    print("[OK] Blocked password without special character")

    print("\n--- 2. Testing Registration with Strong Password ---")
    strong_pwd = "FiscMoney2026#Secure"
    res4 = client.post('/register', data={
        'full_name': 'Test Strong',
        'email': 'strong@test.it',
        'password': strong_pwd,
        'privacy_consent': '1'
    }, follow_redirects=True)
    assert b"Registrazione completata" in res4.data
    print("[OK] Strong password accepted and user registered successfully!")

    # Test login with the strong password
    res_login = client.post('/login', data={
        'email': 'strong@test.it',
        'password': strong_pwd
    }, follow_redirects=True)
    assert b"Bentornato Test Strong" in res_login.data
    print("[OK] Logged in successfully with the strong password!")

    # Cleanup test user
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE email LIKE '%@test.it'")
    conn.commit()
    conn.close()

    print("\nALL PASSWORD COMPLEXITY TESTS PASSED! [SUCCESS]")

if __name__ == '__main__':
    test_password_complexity()
