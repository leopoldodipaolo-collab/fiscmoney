import sys
sys.path.insert(0, '.')
from app import app, get_db_connection

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['workspace_id'] = 1
    
    conn = get_db_connection()
    # Create test member in ws 1
    cursor = conn.cursor()
    cursor.execute("INSERT INTO profiles (workspace_id, name, is_primary, role_title) VALUES (1, 'Test Member', 0, 'Partner')")
    test_p_id = cursor.lastrowid
    # Create test account
    cursor.execute("INSERT INTO accounts (workspace_id, profile_id, name, balance) VALUES (1, ?, 'Conto Test', 500)", (test_p_id,))
    test_acc_id = cursor.lastrowid
    # Create test transaction
    cursor.execute("INSERT INTO transactions (workspace_id, profile_id, account_id, date, amount, category, description) VALUES (1, ?, ?, '2026-08-01', -50, 'Spesa', 'Test Tx')", (test_p_id, test_acc_id))
    # Create test paystub
    cursor.execute("INSERT INTO paystubs (workspace_id, profile_id, month, year, gross_amount, net_amount) VALUES (1, ?, 8, 2026, 2000, 1500)", (test_p_id,))
    # Create test 730
    cursor.execute("INSERT INTO tax_declarations_730 (workspace_id, profile_id, tax_year, declaration_year) VALUES (1, ?, 2025, 2026)", (test_p_id,))
    conn.commit()
    conn.close()

    # Now call delete endpoint
    res = client.post(f'/workspace/profile/delete/{test_p_id}', follow_redirects=True)
    assert res.status_code == 200
    
    # Verify everything is gone
    conn = get_db_connection()
    assert conn.execute("SELECT count(*) FROM profiles WHERE id = ?", (test_p_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM accounts WHERE profile_id = ?", (test_p_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM transactions WHERE profile_id = ?", (test_p_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM paystubs WHERE profile_id = ?", (test_p_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM tax_declarations_730 WHERE profile_id = ?", (test_p_id,)).fetchone()[0] == 0
    conn.close()
    print("CASCADE DELETE TEST PASSED 100%!")
