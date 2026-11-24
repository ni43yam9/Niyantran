import time
import uuid
import json
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.security import hash_password, create_access_token
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.sync import SyncOperation

def run_performance_benchmarks():
    client = TestClient(app)
    results = {}
    
    # 1. Health Probe Response Time (50 iterations)
    health_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = client.get("/health")
        t1 = time.perf_counter()
        assert res.status_code == 200
        health_times.append((t1 - t0) * 1000)
    
    health_times.sort()
    results["health_probe_ms"] = {
        "p50": round(health_times[25], 2),
        "p95": round(health_times[47], 2),
        "p99": round(health_times[49], 2),
        "min": round(min(health_times), 2),
        "max": round(max(health_times), 2),
    }

    # 2. Setup user and device in real DB
    db = SessionLocal()
    uid = f"usr_bench_{uuid.uuid4().hex[:8]}"
    email = f"bench_{uuid.uuid4().hex[:6]}@example.com"
    
    t0 = time.perf_counter()
    pwd_hash = hash_password("BenchmarkPass123!")
    t1 = time.perf_counter()
    results["bcrypt_hashing_ms"] = round((t1 - t0) * 1000, 2)

    user = User(
        id=uid,
        uuid=str(uuid.uuid4()),
        name="Benchmark User",
        email=email,
        password_hash=pwd_hash,
        is_active=True,
        status="active"
    )
    db.add(user)
    db.commit()

    dev_uuid = f"dev-bench-{uuid.uuid4().hex[:8]}"
    dev = Device(
        user_id=uid,
        device_uuid=dev_uuid,
        device_name="Benchmark Device",
        device_type="laptop",
        status="active"
    )
    db.add(dev)
    db.commit()

    token = create_access_token(subject=uid, email=email)
    headers = {"Authorization": f"Bearer {token}", "X-Device-UUID": dev_uuid}

    # 3. Tasks List Query Latency (20 iterations)
    task_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        res = client.get("/api/tasks/", headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        task_times.append((t1 - t0) * 1000)
    task_times.sort()
    results["tasks_list_query_ms"] = {
        "p50": round(task_times[10], 2),
        "p95": round(task_times[18], 2),
        "min": round(min(task_times), 2),
    }

    # 4. Large Sync Batches (10, 50, 100 operations)
    for batch_size in [10, 50, 100]:
        ops = []
        for i in range(batch_size):
            ops.append({
                "operation_uuid": str(uuid.uuid4()),
                "device_uuid": dev_uuid,
                "entity_type": "task",
                "entity_id": f"task-bench-{uuid.uuid4().hex[:8]}",
                "operation_type": "CREATE",
                "entity_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "title": f"Bench Task #{i}",
                    "category": "Coding",
                    "priority": "Medium",
                    "status": "Pending"
                }
            })
        
        t0 = time.perf_counter()
        res = client.post("/api/sync/push", json={"device_uuid": dev_uuid, "operations": ops}, headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        assert res.json()["applied"] == batch_size
        duration_ms = (t1 - t0) * 1000
        results[f"push_batch_{batch_size}_ops"] = {
            "total_ms": round(duration_ms, 2),
            "per_op_ms": round(duration_ms / batch_size, 2)
        }

    # 5. Pull Delta Query with 100+ operations
    t0 = time.perf_counter()
    pull_res = client.get("/api/sync/pull?cursor=0", headers=headers)
    t1 = time.perf_counter()
    assert pull_res.status_code == 200
    changes_count = len(pull_res.json()["changes"])
    results["pull_160_ops_delta_ms"] = {
        "total_ms": round((t1 - t0) * 1000, 2),
        "retrieved_count": changes_count
    }

    # 6. Database Storage & Memory
    db_size_bytes = os.path.getsize("backend/niyantra.db")
    wal_size_bytes = os.path.getsize("backend/niyantra.db-wal") if os.path.exists("backend/niyantra.db-wal") else 0
    results["storage_footprint"] = {
        "db_size_kb": round(db_size_bytes / 1024, 2),
        "wal_size_kb": round(wal_size_bytes / 1024, 2)
    }

    # Clean up test rows
    db.query(SyncOperation).filter(SyncOperation.user_id == uid).delete()
    db.query(Task).filter(Task.user_id == uid).delete()
    db.query(Device).filter(Device.user_id == uid).delete()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_performance_benchmarks()
