import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['workspace_id'] = 1

    # Test cashflow default
    res = client.get('/cashflow')
    assert res.status_code in [200, 302], f"Status: {res.status_code}"
    print(f"Default /cashflow status: {res.status_code}")
    if res.status_code == 200:
        html = res.data.decode('utf-8')
        assert 'month-selector-badge-wrap' in html, "Missing header month selector badge"
        assert 'card-month-select-pill' in html, "Missing card month selector pill"
        print("[OK] Successfully verified 'month-selector-badge-wrap' and 'card-month-select-pill' in HTML output!")

    # Test cashflow with specific month parameter
    res2 = client.get('/cashflow?m=2026-08')
    assert res2.status_code == 200, f"Status: {res2.status_code}"
    html2 = res2.data.decode('utf-8')
    assert 'Agosto 2026' in html2, "Agosto 2026 not found in response"
    print("[OK] Successfully verified month switching to 2026-08!")

print("\nALL CASHFLOW MONTH TESTS PASSED PERFECTLY!")
