import sys, os
sys.path.insert(0, os.path.abspath('.'))
import app, database

client = app.app.test_client()

with client.session_transaction() as sess:
    sess['user_id'] = 9
    sess['user_name'] = 'Macera Mascitelli Nunzia'
    sess['role'] = 'USER'
    sess['workspace_id'] = 2

r = client.get('/dashboard')
print('Nunzia status:', r.status_code)
print('Includes filter/all (Tutta la Famiglia):', '/workspace/filter/all' in r.text)
print('Includes filter/2 (Leopoldo Di Paolo):', '/workspace/filter/2' in r.text)
print('Includes filter/21 (Nunzia):', '/workspace/filter/21' in r.text)
print('Includes edit privacy modal trigger:', 'openPrivacyModal' in r.text and 'onclick="openPrivacyModal()"' in r.text)
