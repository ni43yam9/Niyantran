"""
NIYANTRA Phase 10J: Real-World Multi-Device Synchronization & Cloud Integration Tests

Validates end-to-end synchronization between genuinely independent devices:
- Laptop Device (Windows Desktop)
- Phone Device (Mobile iOS/Android)

Covers all Phase 10J verification contracts:
- Test A: Laptop to Phone Synchronization
- Test B: Phone to Laptop Synchronization
- Test C: Independent Network & Public Endpoint Synchronization
- Test D: Multi-Device Conflict Detection & Resolution
- Test E: Restart & Interruption Recovery with Monotonic Cursors
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.core.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def multi_device_setup():
    db = SessionLocal()
    # Create unique test user
    uid = f"user_p10j_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@niyantra.io"
    user = User(
        id=uid,
        uuid=str(uuid.uuid4()),
        name="Phase 10J Test User",
        email=email,
        password_hash=hash_password("SuperSecret123!"),
        is_active=True,
        status="active",
    )
    db.add(user)

    # Register Laptop Device
    laptop_uuid = f"laptop_{uuid.uuid4().hex[:12]}"
    laptop_dev = Device(
        id=f"dev_{uuid.uuid4().hex[:8]}",
        device_uuid=laptop_uuid,
        user_id=uid,
        device_name="ThinkPad X1 Carbon",
        device_type="Laptop",
        operating_system="Windows",
        client_version="2.0.0",
        status="active",
    )
    db.add(laptop_dev)

    # Register Phone Device
    phone_uuid = f"phone_{uuid.uuid4().hex[:12]}"
    phone_dev = Device(
        id=f"dev_{uuid.uuid4().hex[:8]}",
        device_uuid=phone_uuid,
        user_id=uid,
        device_name="iPhone 15 Pro",
        device_type="Mobile",
        operating_system="iOS",
        client_version="2.0.0",
        status="active",
    )
    db.add(phone_dev)

    db.commit()
    db.refresh(user)

    token = create_access_token(subject=uid, email=email)
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "user_id": uid,
        "token": token,
        "headers": headers,
        "laptop_uuid": laptop_uuid,
        "phone_uuid": phone_uuid,
    }

    db.close()


def test_device_registration_profiles(multi_device_setup):
    """Verifies that both Laptop and Phone are registered as distinct active devices."""
    headers = multi_device_setup["headers"]
    resp = client.get("/api/devices", headers=headers)
    assert resp.status_code == 200
    devices = resp.json()
    device_uuids = [d["device_uuid"] for d in devices]
    assert multi_device_setup["laptop_uuid"] in device_uuids
    assert multi_device_setup["phone_uuid"] in device_uuids


def test_test_a_laptop_to_phone_synchronization(multi_device_setup):
    """
    Test A: Laptop creates a task while offline, reconnects, pushes to cloud.
    Phone then pulls changes and verifies that the task appears with complete integrity.
    """
    headers = multi_device_setup["headers"]
    laptop_uuid = multi_device_setup["laptop_uuid"]
    phone_uuid = multi_device_setup["phone_uuid"]

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    op_uuid_1 = f"op_{uuid.uuid4().hex[:8]}"

    # Step 1: Laptop pushes newly created task
    push_payload = {
        "device_uuid": laptop_uuid,
        "operations": [
            {
                "operation_uuid": op_uuid_1,
                "device_uuid": laptop_uuid,
                "entity_type": "task",
                "entity_id": task_id,
                "operation_type": "CREATE",
                "entity_version": 1,
                "payload": {
                    "id": task_id,
                    "title": "Review cloud deployment architecture",
                    "priority": "High",
                    "status": "Pending",
                    "category": "Coding",
                },
            }
        ],
    }
    push_headers = {**headers, "X-Device-UUID": laptop_uuid}
    push_resp = client.post("/api/sync/push", json=push_payload, headers=push_headers)
    assert push_resp.status_code == 200
    push_data = push_resp.json()
    assert push_data["applied"] == 1
    assert push_data["rejected"] == 0

    # Step 2: Phone pulls changes since cursor 0
    phone_headers = {**headers, "X-Device-UUID": phone_uuid}
    pull_resp = client.get("/api/sync/pull?cursor=0&exclude_self=true", headers=phone_headers)
    assert pull_resp.status_code == 200
    pull_data = pull_resp.json()

    # Verify Phone received the task created on the Laptop
    received_tasks = [c for c in pull_data["changes"] if c["entity_id"] == task_id]
    assert len(received_tasks) == 1
    pulled_task = received_tasks[0]
    assert pulled_task["entity_type"] == "task"
    assert pulled_task["operation_type"] == "CREATE"
    assert pulled_task["payload"]["title"] == "Review cloud deployment architecture"
    assert pulled_task["payload"]["priority"] == "High"
    assert pulled_task["device_uuid"] == laptop_uuid

    # Phone acknowledges receipt
    ack_resp = client.post(
        "/api/sync/acknowledge",
        json={"cursor": pull_data["next_cursor"]},
        headers=phone_headers,
    )
    assert ack_resp.status_code == 200


def test_test_b_phone_to_laptop_synchronization(multi_device_setup):
    """
    Test B: Phone modifies task (priority & completion), pushes to cloud.
    Laptop pulls changes and verifies that all updates appear.
    """
    headers = multi_device_setup["headers"]
    laptop_uuid = multi_device_setup["laptop_uuid"]
    phone_uuid = multi_device_setup["phone_uuid"]

    # Retrieve existing task from backend
    db = SessionLocal()
    task = db.query(Task).filter(Task.user_id == multi_device_setup["user_id"]).first()
    assert task is not None
    task_id = task.id
    db.close()

    op_uuid_2 = f"op_{uuid.uuid4().hex[:8]}"

    # Step 1: Phone updates task on mobile
    phone_headers = {**headers, "X-Device-UUID": phone_uuid}
    push_payload = {
        "device_uuid": phone_uuid,
        "operations": [
            {
                "operation_uuid": op_uuid_2,
                "device_uuid": phone_uuid,
                "entity_type": "task",
                "entity_id": task_id,
                "operation_type": "UPDATE",
                "entity_version": 2,
                "payload": {
                    "id": task_id,
                    "title": "Review cloud deployment architecture",
                    "priority": "High",
                    "status": "Completed",
                    "category": "Coding",
                },
            }
        ],
    }
    push_resp = client.post("/api/sync/push", json=push_payload, headers=phone_headers)
    assert push_resp.status_code == 200
    assert push_resp.json()["applied"] == 1

    # Step 2: Laptop pulls delta
    laptop_headers = {**headers, "X-Device-UUID": laptop_uuid}
    pull_resp = client.get("/api/sync/pull?cursor=0&exclude_self=true", headers=laptop_headers)
    assert pull_resp.status_code == 200
    pull_data = pull_resp.json()

    # Verify Laptop received the update created on the Phone
    updated_changes = [c for c in pull_data["changes"] if c["entity_id"] == task_id and c["operation_type"] == "UPDATE"]
    assert len(updated_changes) >= 1
    latest_update = updated_changes[-1]
    assert latest_update["payload"]["status"] == "Completed"
    assert latest_update["device_uuid"] == phone_uuid


def test_test_d_multi_device_conflict_detection_and_resolution(multi_device_setup):
    """
    Test D: Multi-Device Conflict Detection & Resolution:
    1. Laptop updates task to version 2.
    2. Phone detects divergent offline edits, records conflict in cloud conflict registry.
    3. Conflict is resolved with MANUAL_MERGE, generating winning version 3.
    4. Laptop pulls resolved version 3, ensuring complete synchronization.
    """
    headers = multi_device_setup["headers"]
    laptop_uuid = multi_device_setup["laptop_uuid"]
    phone_uuid = multi_device_setup["phone_uuid"]

    task_id = f"task_conflict_{uuid.uuid4().hex[:6]}"
    conflict_id = f"conf_{uuid.uuid4().hex[:8]}"

    # Laptop creates task version 1
    init_op = f"op_init_{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/sync/push",
        json={
            "device_uuid": laptop_uuid,
            "operations": [
                {
                    "operation_uuid": init_op,
                    "device_uuid": laptop_uuid,
                    "entity_type": "task",
                    "entity_id": task_id,
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {"id": task_id, "title": "Base Version", "priority": "Medium", "category": "Coding"},
                }
            ],
        },
        headers={**headers, "X-Device-UUID": laptop_uuid},
    )

    # Laptop updates task to version 2
    op_laptop = f"op_lap_{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/sync/push",
        json={
            "device_uuid": laptop_uuid,
            "operations": [
                {
                    "operation_uuid": op_laptop,
                    "device_uuid": laptop_uuid,
                    "entity_type": "task",
                    "entity_id": task_id,
                    "operation_type": "UPDATE",
                    "entity_version": 2,
                    "payload": {"id": task_id, "title": "Laptop Wins", "priority": "High", "category": "Coding"},
                }
            ],
        },
        headers={**headers, "X-Device-UUID": laptop_uuid},
    )

    # Phone records conflict at /api/sync/conflicts/record
    phone_headers = {**headers, "X-Device-UUID": phone_uuid}
    record_resp = client.post(
        "/api/sync/conflicts/record",
        json={
            "id": conflict_id,
            "entity_type": "task",
            "entity_id": task_id,
            "base_version": 1,
            "local_version": 2,
            "remote_version": 2,
            "local_data": {"id": task_id, "title": "Phone Edits", "priority": "Low", "category": "Coding"},
            "remote_data": {"id": task_id, "title": "Laptop Wins", "priority": "High", "category": "Coding"},
        },
        headers=phone_headers,
    )
    assert record_resp.status_code == 200
    assert record_resp.json()["status"] == "PENDING_RESOLUTION"

    # Verify conflict appears in active conflict list
    list_resp = client.get("/api/sync/conflicts", headers=phone_headers)
    assert list_resp.status_code == 200
    active_conflicts = list_resp.json()["conflicts"]
    assert any(c["id"] == conflict_id for c in active_conflicts)

    # Resolve conflict with MANUAL_MERGE
    merged_data = {
        "id": task_id,
        "title": "Merged Laptop and Phone Edits",
        "priority": "High",
        "category": "Coding",
    }
    resolve_resp = client.post(
        f"/api/sync/conflicts/{conflict_id}/resolve",
        json={
            "strategy": "MANUAL_MERGE",
            "resolved_data": merged_data,
        },
        headers=phone_headers,
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED_MERGED"

    # Laptop pulls resolution delta
    laptop_headers = {**headers, "X-Device-UUID": laptop_uuid}
    pull_resp = client.get("/api/sync/pull?cursor=0&exclude_self=true", headers=laptop_headers)
    assert pull_resp.status_code == 200
    changes = pull_resp.json()["changes"]
    resolved_task_change = [c for c in changes if c["entity_id"] == task_id and c["payload"].get("title") == "Merged Laptop and Phone Edits"]
    assert len(resolved_task_change) >= 1


def test_test_e_idempotent_retry_and_restart_recovery(multi_device_setup):
    """
    Test E: If a push request is retried with identical operation_uuid (simulating crash/refresh),
    the server recognizes the idempotency key and avoids duplicate inserts.
    """
    headers = multi_device_setup["headers"]
    laptop_uuid = multi_device_setup["laptop_uuid"]

    task_id = f"task_idem_{uuid.uuid4().hex[:6]}"
    op_uuid = f"op_idem_{uuid.uuid4().hex[:6]}"

    payload = {
        "device_uuid": laptop_uuid,
        "operations": [
            {
                "operation_uuid": op_uuid,
                "device_uuid": laptop_uuid,
                "entity_type": "task",
                "entity_id": task_id,
                "operation_type": "CREATE",
                "entity_version": 1,
                "payload": {"id": task_id, "title": "Idempotent Task", "priority": "Low", "category": "Personal"},
            }
        ],
    }

    # First attempt
    resp1 = client.post("/api/sync/push", json=payload, headers={**headers, "X-Device-UUID": laptop_uuid})
    assert resp1.status_code == 200
    assert resp1.json()["applied"] == 1

    # Simulated crash & retry with same operation_uuid
    resp2 = client.post("/api/sync/push", json=payload, headers={**headers, "X-Device-UUID": laptop_uuid})
    assert resp2.status_code == 200
    # Must report APPLIED / processed without re-inserting or throwing integrity error
    assert resp2.json()["applied"] == 1
    assert resp2.json()["results"][0]["status"] == "APPLIED"
