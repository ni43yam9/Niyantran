"""
NIYANTRA Phase 10J: Empirical Performance Verification Benchmark
Measures live API response latencies, authentication throughput,
push batch processing, pull pagination, and multi-device roundtrip latency.
"""
import time
import uuid
import json
import urllib.request

base_url = 'http://127.0.0.1:8000'

def measure_request(name, req_fn, iterations=5):
    latencies = []
    result = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        result = req_fn()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)
    avg = sum(latencies) / len(latencies)
    p95 = sorted(latencies)[int(0.95 * len(latencies))]
    print(f"[{name}] Avg: {avg:.2f}ms | Min: {min(latencies):.2f}ms | P95: {p95:.2f}ms")
    return avg, result

print("=== NIYANTRA PHASE 10J PERFORMANCE BENCHMARKS ===\n")

# 1. Health Probe Latency
def probe_health():
    req = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

measure_request("Health Probe (GET /health)", probe_health, iterations=10)

# 2. Authentication Response Time (bcrypt hash verification + JWT issue)
uid = f"perf_user_{uuid.uuid4().hex[:6]}"
email = f"{uid}@example.com"
password = "PerformanceSecret123!"

reg_data = json.dumps({"name": "Perf User", "email": email, "password": password}).encode()
req = urllib.request.Request(f"{base_url}/api/auth/register", data=reg_data, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    auth_data = json.loads(resp.read().decode())
    token = auth_data["access_token"]

def auth_login():
    login_data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(f"{base_url}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

measure_request("Auth Verification (POST /api/auth/login)", auth_login, iterations=5)

# 3. Device Registration
laptop_uuid = f"laptop_{uuid.uuid4().hex[:8]}"
phone_uuid = f"phone_{uuid.uuid4().hex[:8]}"
auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

dev_data = json.dumps({"device_uuid": laptop_uuid, "device_name": "Benchmark Laptop", "device_type": "Laptop", "operating_system": "Windows"}).encode()
req = urllib.request.Request(f"{base_url}/api/devices/register", data=dev_data, headers=auth_headers)
with urllib.request.urlopen(req) as resp:
    pass

dev_data_p = json.dumps({"device_uuid": phone_uuid, "device_name": "Benchmark Phone", "device_type": "Mobile", "operating_system": "iOS"}).encode()
req = urllib.request.Request(f"{base_url}/api/devices/register", data=dev_data_p, headers=auth_headers)
with urllib.request.urlopen(req) as resp:
    pass

# 4. Push Batch Performance (10 operations per batch)
def push_batch_10():
    ops = []
    for i in range(10):
        t_id = f"task_perf_{uuid.uuid4().hex[:6]}"
        ops.append({
            "operation_uuid": f"op_{uuid.uuid4().hex[:8]}",
            "device_uuid": laptop_uuid,
            "entity_type": "task",
            "entity_id": t_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {"id": t_id, "title": f"Benchmark Task {i}", "priority": "Medium", "category": "Coding", "status": "Pending"},
        })
    batch_data = json.dumps({"device_uuid": laptop_uuid, "operations": ops}).encode()
    req = urllib.request.Request(f"{base_url}/api/sync/push", data=batch_data, headers={**auth_headers, "X-Device-UUID": laptop_uuid})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

measure_request("Push Batch (10 items / batch)", push_batch_10, iterations=5)

# 5. Pull Pagination Performance
def pull_changes():
    req = urllib.request.Request(f"{base_url}/api/sync/pull?cursor=0&limit=50&exclude_self=false", headers={**auth_headers, "X-Device-UUID": phone_uuid})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

measure_request("Pull Delta Query (limit=50)", pull_changes, iterations=5)

# 6. End-to-End Laptop-to-Phone Sync Cycle
def sync_roundtrip():
    t_id = f"task_rt_{uuid.uuid4().hex[:6]}"
    # 1. Laptop push
    push_data = json.dumps({
        "device_uuid": laptop_uuid,
        "operations": [{
            "operation_uuid": f"op_{uuid.uuid4().hex[:8]}",
            "device_uuid": laptop_uuid,
            "entity_type": "task",
            "entity_id": t_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {"id": t_id, "title": "Roundtrip Sync Task", "priority": "High", "category": "Coding"},
        }]
    }).encode()
    req1 = urllib.request.Request(f"{base_url}/api/sync/push", data=push_data, headers={**auth_headers, "X-Device-UUID": laptop_uuid})
    with urllib.request.urlopen(req1) as r1:
        p_res = json.loads(r1.read().decode())
    # 2. Phone pull
    req2 = urllib.request.Request(f"{base_url}/api/sync/pull?cursor=0&exclude_self=true", headers={**auth_headers, "X-Device-UUID": phone_uuid})
    with urllib.request.urlopen(req2) as r2:
        pull_res = json.loads(r2.read().decode())
    # 3. Phone acknowledge
    req3 = urllib.request.Request(f"{base_url}/api/sync/acknowledge", data=json.dumps({"cursor": pull_res["next_cursor"]}).encode(), headers={**auth_headers, "X-Device-UUID": phone_uuid})
    with urllib.request.urlopen(req3) as r3:
        pass
    return pull_res

measure_request("End-to-End Multi-Device Sync Cycle", sync_roundtrip, iterations=5)

print("\n=== PERFORMANCE BENCHMARKS COMPLETE ===")
