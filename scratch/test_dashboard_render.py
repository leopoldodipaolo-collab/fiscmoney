import sys
sys.path.insert(0, '.')
from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['workspace_id'] = 2
    res = client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'id="deleteProfileModal"' in html
    assert 'openDeleteProfileModal' in html
    print('Dashboard rendered with professional delete modal 100% OK!')
