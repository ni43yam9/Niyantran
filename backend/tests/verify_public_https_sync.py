import urllib.request
import json
import uuid

base_url = 'https://06d355e21c47db.app.lhr.life'

print(f"Connecting to live public HTTPS backend at: {base_url}\n")

# 1. Health check over public HTTPS
req = urllib.request.Request(f'{base_url}/health', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())
    print('1. Public HTTPS Health Check:', data)
    assert data['status'] == 'healthy'

# 2. Register test account over public HTTPS
uid = f'user_https_{uuid.uuid4().hex[:6]}'
email = f'{uid}@public-test.io'
reg_payload = json.dumps({'name': 'Public HTTPS User', 'email': email, 'password': 'SecurePassword123!'}).encode()
req = urllib.request.Request(f'{base_url}/api/auth/register', data=reg_payload, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as r:
    auth_data = json.loads(r.read().decode())
    token = auth_data['access_token']
    user_id = auth_data['user']['id']
    print(f'2. Public HTTPS User Registered: {user_id} (Token bytes: {len(token)})')

# 3. Register Laptop and Phone devices over public HTTPS
laptop_uuid = f'laptop_{uuid.uuid4().hex[:8]}'
phone_uuid = f'phone_{uuid.uuid4().hex[:8]}'
auth_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}

for dev_uuid, dev_name, dev_type, os_name in [
    (laptop_uuid, 'ThinkPad Laptop', 'Laptop', 'Windows'),
    (phone_uuid, 'iPhone Mobile', 'Mobile', 'iOS')
]:
    dev_payload = json.dumps({
        'device_uuid': dev_uuid,
        'device_name': dev_name,
        'device_type': dev_type,
        'operating_system': os_name,
        'client_version': '2.0.0'
    }).encode()
    req = urllib.request.Request(f'{base_url}/api/devices/register', data=dev_payload, headers=auth_headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        dev_res = json.loads(r.read().decode())
        print(f"   Registered {dev_type} ({dev_uuid}): {dev_res['status']}")

# 4. Laptop pushes task over public HTTPS
task_id = f'task_{uuid.uuid4().hex[:6]}'
laptop_headers = {**auth_headers, 'X-Device-UUID': laptop_uuid}
push_payload = json.dumps({
    'device_uuid': laptop_uuid,
    'operations': [{
        'operation_uuid': f'op_{uuid.uuid4().hex[:6]}',
        'device_uuid': laptop_uuid,
        'entity_type': 'task',
        'entity_id': task_id,
        'operation_type': 'CREATE',
        'entity_version': 1,
        'payload': {'id': task_id, 'title': 'Public HTTPS Synced Task', 'priority': 'High', 'category': 'Coding', 'status': 'Pending'}
    }]
}).encode()
req = urllib.request.Request(f'{base_url}/api/sync/push', data=push_payload, headers=laptop_headers)
with urllib.request.urlopen(req, timeout=10) as r:
    push_res = json.loads(r.read().decode())
    print(f"3. Laptop Pushed Task over Public HTTPS: applied={push_res['applied']}")

# 5. Phone pulls task over public HTTPS
phone_headers = {**auth_headers, 'X-Device-UUID': phone_uuid}
req = urllib.request.Request(f'{base_url}/api/sync/pull?cursor=0&exclude_self=true', headers=phone_headers)
with urllib.request.urlopen(req, timeout=10) as r:
    pull_res = json.loads(r.read().decode())
    changes = [c for c in pull_res['changes'] if c['entity_id'] == task_id]
    print(f"4. Phone Pulled Task over Public HTTPS: {len(changes)} change(s) received, next_cursor={pull_res['next_cursor']}")
    assert len(changes) == 1
    assert changes[0]['payload']['title'] == 'Public HTTPS Synced Task'

print('\n✓ ALL REAL PUBLIC HTTPS MULTI-DEVICE TRANSACTIONS VERIFIED WITH ZERO ERRORS!')
