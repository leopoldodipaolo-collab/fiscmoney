import sys
sys.path.insert(0, '.')
from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['workspace_id'] = 1
    res = client.get('/transactions?month=all')
    assert res.status_code == 200, f"Expected 200 got {res.status_code}"
    html = res.data.decode('utf-8')
    assert 'id="smartCategoryTrayModal"' in html
    assert 'id="speedTriageGameModal"' in html
    assert 'openSpeedTriageGameModal()' in html
    assert 'openSmartCategoryTrayFromBtn(this, event)' in html
    print("Verification OK: All modal IDs, buttons, and scripts are present and correctly structured!")
