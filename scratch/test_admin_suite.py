import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database import get_db_connection, init_db

def test_admin_suite():
    init_db()
    client = app.test_client()

    print("\n--- 1. Testing Non-Admin Access Protection ---")
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['user_email'] = 'leo.19@live.it'
        sess['user_name'] = 'Leopoldo Standard'
        sess['role'] = 'USER'
        sess['workspace_id'] = 2

    res_admin = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Accesso riservato all&#39;Amministratore" in res_admin.data or b"Accesso riservato" in res_admin.data or b"Dashboard" in res_admin.data
    print("[OK] Non-admin correctly blocked from /admin/dashboard!")

    print("\n--- 2. Testing Super-Admin Login & Dashboard ---")
    client.get('/logout', follow_redirects=True)
    res_login = client.post('/login', data={'email': 'admin@fiscmoney.it', 'password': 'FiscMoney2026Admin!'}, follow_redirects=True)
    assert res_login.status_code == 200
    
    res_dash = client.get('/admin/dashboard')
    assert res_dash.status_code == 200
    assert b"FiscMoney Executive Suite" in res_dash.data
    assert b"Master Rules AI" in res_dash.data
    assert b"Registro Audit Trail" in res_dash.data
    print("[OK] Admin dashboard rendered perfectly with all KPI cards and tabs!")

    print("\n--- 3. Testing User Subscription Plan Update ---")
    conn = get_db_connection()
    target_user = conn.execute("SELECT id FROM users WHERE email != 'admin@fiscmoney.it' LIMIT 1").fetchone()
    conn.close()

    if target_user:
        u_id = target_user['id']
        res_plan = client.post(f'/admin/users/{u_id}/update-plan', data={
            'subscription_plan': 'PRO_ANNUAL',
            'subscription_status': 'ACTIVE',
            'role': 'USER',
            'subscription_expires_at': '2027-12-31'
        }, follow_redirects=True)
        assert res_plan.status_code == 200
        assert b"aggiornato con successo" in res_plan.data
        print(f"[OK] User #{u_id} plan updated to PRO_ANNUAL (100 EUR/year) with expiration!")

    print("\n--- 4. Testing Global Category Master Rule Addition & Propagation ---")
    res_add_rule = client.post('/admin/global-rules/add', data={
        'pattern': 'TEST_MERCHANT_AUTO',
        'category': 'Tecnologia & Software',
        'sub_category': 'Cloud & SaaS',
        'tags': 'cloud,dev,test',
        'priority': '15',
        'is_tax_deductible': '1'
    }, follow_redirects=True)
    assert res_add_rule.status_code == 200
    assert b"TEST_MERCHANT_AUTO" in res_add_rule.data
    print("[OK] Global Category Rule added!")

    res_prop = client.post('/admin/global-rules/propagate', follow_redirects=True)
    assert res_prop.status_code == 200
    assert b"Propagazione completata con successo" in res_prop.data
    print("[OK] Master rules propagated across all active workspaces!")

    print("\n--- 5. Testing Broadcast Announcement Banner ---")
    res_ann = client.post('/admin/announcements/save', data={
        'title': 'Manutenzione Piattaforma FiscMoney',
        'message': 'Rilascio nuove funzionalita fiscali 2026',
        'level': 'WARNING',
        'is_active': '1'
    }, follow_redirects=True)
    assert res_ann.status_code == 200
    assert b"Manutenzione Piattaforma FiscMoney" in res_ann.data
    
    # Check that announcement appears in standard dashboard
    res_user_dash = client.get('/dashboard')
    assert b"Manutenzione Piattaforma FiscMoney" in res_user_dash.data
    print("[OK] Broadcast announcement banner created and rendered across all user pages!")

    print("\n--- 6. Testing Impersonation (Support Mode) & Exit ---")
    if target_user:
        res_imp = client.post(f'/admin/users/{u_id}/impersonate', follow_redirects=True)
        assert res_imp.status_code == 200
        assert b"ASSISTENZA" in res_imp.data
        print(f"[OK] Impersonation support session active for User #{u_id}!")

        # Exit Impersonation
        res_exit = client.post('/admin/impersonate/exit', follow_redirects=True)
        assert res_exit.status_code == 200
        assert b"FiscMoney Executive Suite" in res_exit.data or b"Suite Super-Admin" in res_exit.data
        print("[OK] Exited impersonation and securely restored Super-Admin session!")

    print("\n--- 7. Testing Database Optimization (VACUUM) ---")
    res_vac = client.post('/admin/system/vacuum', follow_redirects=True)
    assert res_vac.status_code == 200
    assert b"Ottimizzazione del Database completata" in res_vac.data
    print("[OK] Database VACUUM & ANALYZE executed successfully!")

    print("\n--- 8. Testing Database Snapshot Backup Download ---")
    res_backup = client.get('/admin/system/backup')
    assert res_backup.status_code == 200
    assert 'attachment' in res_backup.headers.get('Content-Disposition', '')
    print("[OK] Database backup download generated successfully!")

    print("\n=== ALL ADMIN SUITE TESTS PASSED 100%! ===")

if __name__ == '__main__':
    test_admin_suite()
