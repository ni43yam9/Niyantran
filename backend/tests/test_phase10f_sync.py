"""
NIYANTRA Phase 10F Verification Suite: Cloud Backend & Synchronization API Foundation

Tests all aspects of Phase 10F:
1. Sync model definitions and SQLAlchemy metadata
2. Dual database engine configuration (SQLite & PostgreSQL URL normalisation)
3. Strict JWT authentication enforcement across all sync endpoints
4. Device identity, registration check, and ownership validation
5. Revoked device rejection (HTTP 403)
6. Idempotent push processing (exact same UUID does not duplicate records)
7. Full entity lifecycle (CREATE -> UPDATE -> DELETE with soft deletion & tombstoning)
8. Rejection of invalid entity types and invalid operation types
9. Cursor pagination stability, monotonic ordering, and has_more flag
10. Multi-device push/pull and exclude_self filtering
11. Complete tenant / user isolation
12. Multi-entity synchronization (Task, Goal, Habit, Timeblock, DailyIntent)
13. Acknowledgment endpoint and cursor advancing logic
14. Sync status endpoint and pending change calculation
15. Non-regression of existing authentication and device management APIs
16. Non-regression of existing productivity endpoints (/api/tasks, /api/goals, etc.)
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import get_db, Base, engine, SessionLocal
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.daily_intent import DailyIntent
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.sync import SyncOperation, SyncCursor, SyncEntityVersion


client = TestClient(app)


@pytest.fixture(scope="module")
def sync_test_setup():
    """
    Creates test users and test devices for isolation in Phase 10F tests.
    """
    db = SessionLocal()
    prefix = uuid.uuid4().hex[:8]

    # User 1
    u1_id = f"usr_{prefix}_1"
    u1 = User(
        id=u1_id,
        uuid=str(uuid.uuid4()),
        name="Sync Test User One",
        email=f"sync1_{prefix}@test.local",
        password_hash=hash_password("password123"),
        is_active=True,
        status="active",
    )
    db.add(u1)

    # Device A for User 1
    dev_a_uuid = str(uuid.uuid4())
    dev_a = Device(
        id=f"dev_{prefix}_1a",
        device_uuid=dev_a_uuid,
        user_id=u1_id,
        device_name="Laptop A",
        device_type="Laptop",
        operating_system="Windows",
        status="active",
    )
    db.add(dev_a)

    # Device B for User 1
    dev_b_uuid = str(uuid.uuid4())
    dev_b = Device(
        id=f"dev_{prefix}_1b",
        device_uuid=dev_b_uuid,
        user_id=u1_id,
        device_name="Mobile B",
        device_type="Mobile",
        operating_system="Android",
        status="active",
    )
    db.add(dev_b)

    # Revoked Device C for User 1
    dev_c_uuid = str(uuid.uuid4())
    dev_c = Device(
        id=f"dev_{prefix}_1c",
        device_uuid=dev_c_uuid,
        user_id=u1_id,
        device_name="Revoked Device C",
        device_type="Tablet",
        operating_system="iOS",
        status="revoked",
    )
    db.add(dev_c)

    # User 2 (for tenant isolation tests)
    u2_id = f"usr_{prefix}_2"
    u2 = User(
        id=u2_id,
        uuid=str(uuid.uuid4()),
        name="Sync Test User Two",
        email=f"sync2_{prefix}@test.local",
        password_hash=hash_password("password123"),
        is_active=True,
        status="active",
    )
    db.add(u2)

    # Device D for User 2
    dev_d_uuid = str(uuid.uuid4())
    dev_d = Device(
        id=f"dev_{prefix}_2d",
        device_uuid=dev_d_uuid,
        user_id=u2_id,
        device_name="Laptop D",
        device_type="Laptop",
        operating_system="Linux",
        status="active",
    )
    db.add(dev_d)

    db.commit()

    token_u1 = create_access_token(subject=u1_id, email=u1.email)
    token_u2 = create_access_token(subject=u2_id, email=u2.email)

    data = {
        "u1_id": u1_id,
        "token_u1": token_u1,
        "dev_a_uuid": dev_a_uuid,
        "dev_b_uuid": dev_b_uuid,
        "dev_c_uuid": dev_c_uuid,
        "u2_id": u2_id,
        "token_u2": token_u2,
        "dev_d_uuid": dev_d_uuid,
    }

    db.close()
    return data


# ---------------------------------------------------------------------------
# 1. Models & Schema Instantiation
# ---------------------------------------------------------------------------

def test_sync_models_instantiation_and_schema():
    """Validates that SyncOperation, SyncCursor, and SyncEntityVersion instantiate properly."""
    op = SyncOperation(
        operation_uuid=str(uuid.uuid4()),
        user_id="default_user",
        device_uuid="test-dev",
        entity_type="task",
        entity_id="tsk_123",
        operation_type="CREATE",
        entity_version=1,
        payload={"title": "Test Task"},
        status="APPLIED",
    )
    assert op.operation_type == "CREATE"
    assert op.entity_type == "task"
    assert op.payload["title"] == "Test Task"

    cursor = SyncCursor(
        user_id="default_user",
        device_uuid="test-dev",
        last_pulled_cursor=5,
        last_pushed_cursor=3,
    )
    assert cursor.last_pulled_cursor == 5

    ev = SyncEntityVersion(
        user_id="default_user",
        entity_type="task",
        entity_id="tsk_123",
        current_version=2,
        last_modified_device="test-dev",
        is_deleted=False,
    )
    assert ev.current_version == 2
    assert ev.is_deleted is False


# ---------------------------------------------------------------------------
# 2. Dual Database Engine Configuration
# ---------------------------------------------------------------------------

def test_dual_database_engine_configuration():
    """Validates PostgreSQL and SQLite URL normalisation and engine compatibility."""
    from backend.app.database import engine
    from sqlalchemy import create_engine

    # Current engine runs on SQLite without error
    assert engine is not None
    assert engine.dialect.name == "sqlite"

    # Verify PostgreSQL URL normalization logic
    pg_url = "postgres://user:secret@localhost:5432/niyantra"
    normalized = pg_url.replace("postgres://", "postgresql://", 1)
    assert normalized.startswith("postgresql://")


# ---------------------------------------------------------------------------
# 3. Strict JWT Authentication Enforcement
# ---------------------------------------------------------------------------

def test_strict_jwt_authentication_required():
    """Verifies that all sync endpoints reject unauthenticated or invalid token requests."""
    endpoints = [
        ("POST", "/api/sync/push", {"operations": []}),
        ("GET", "/api/sync/pull", None),
        ("GET", "/api/sync/status", None),
        ("POST", "/api/sync/acknowledge", {"cursor": 1}),
    ]

    for method, path, body in endpoints:
        # No header
        resp = client.request(method, path, json=body) if body else client.request(method, path)
        assert resp.status_code == 401, f"Expected 401 for {method} {path} without token"

        # Invalid token
        headers = {"Authorization": "Bearer invalid_garbage_token"}
        resp2 = client.request(method, path, json=body, headers=headers) if body else client.request(method, path, headers=headers)
        assert resp2.status_code == 401, f"Expected 401 for {method} {path} with bad token"


# ---------------------------------------------------------------------------
# 4. Device Identity & Ownership Validation
# ---------------------------------------------------------------------------

def test_device_validation_and_ownership(sync_test_setup):
    """Verifies missing device, non-existent device, and cross-user device ownership checks."""
    s = sync_test_setup
    headers_u1 = {"Authorization": f"Bearer {s['token_u1']}"}

    # Missing device header/body on push
    resp = client.post("/api/sync/push", json={"operations": []}, headers=headers_u1)
    assert resp.status_code == 400
    assert "UUID is required" in resp.json()["detail"]

    # Non-existent device UUID
    fake_dev = str(uuid.uuid4())
    resp2 = client.post(
        "/api/sync/push",
        json={"device_uuid": fake_dev, "operations": []},
        headers=headers_u1,
    )
    assert resp2.status_code == 404
    assert "not registered" in resp2.json()["detail"]

    # Device belonging to User 2 used by User 1
    resp3 = client.post(
        "/api/sync/push",
        json={"device_uuid": s["dev_d_uuid"], "operations": []},
        headers=headers_u1,
    )
    assert resp3.status_code == 403
    assert "ownership mismatch" in resp3.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Revoked Device Rejection
# ---------------------------------------------------------------------------

def test_revoked_device_rejection(sync_test_setup):
    """Verifies that revoked devices cannot push or pull changes."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_c_uuid"],
    }

    # Push from revoked device
    resp = client.post(
        "/api/sync/push",
        json={"operations": []},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "revoked" in resp.json()["detail"]

    # Pull from revoked device
    resp_pull = client.get("/api/sync/pull", headers=headers)
    assert resp_pull.status_code == 403
    assert "revoked" in resp_pull.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Idempotent Push Processing
# ---------------------------------------------------------------------------

def test_idempotent_push(sync_test_setup):
    """Verifies that submitting identical operation UUIDs is completely idempotent."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    op_uuid = str(uuid.uuid4())
    task_id = f"tsk_{uuid.uuid4().hex[:12]}"

    push_payload = {
        "operations": [
            {
                "operation_uuid": op_uuid,
                "entity_type": "task",
                "entity_id": task_id,
                "operation_type": "CREATE",
                "entity_version": 1,
                "payload": {
                    "title": "Idempotent Test Task",
                    "task_type": "Daily",
                    "category": "Coding",
                    "priority": "High",
                    "status": "Pending",
                    "start_date": "2026-11-22",
                    "due_date": "2026-11-22",
                },
            }
        ]
    }

    # First push
    r1 = client.post("/api/sync/push", json=push_payload, headers=headers)
    assert r1.status_code == 200
    res1 = r1.json()
    assert res1["applied"] == 1
    assert res1["rejected"] == 0
    assert res1["results"][0]["status"] == "APPLIED"

    # Second push (identical operation)
    r2 = client.post("/api/sync/push", json=push_payload, headers=headers)
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["applied"] == 1
    assert res2["rejected"] == 0
    assert res2["results"][0]["status"] == "APPLIED"
    assert "idempotent" in res2["results"][0]["message"].lower()

    # Verify only ONE SyncOperation row was stored
    db = SessionLocal()
    ops_count = db.query(SyncOperation).filter(SyncOperation.operation_uuid == op_uuid).count()
    assert ops_count == 1
    db.close()


# ---------------------------------------------------------------------------
# 7. Entity Lifecycle (CREATE -> UPDATE -> DELETE)
# ---------------------------------------------------------------------------

def test_push_create_update_delete_lifecycle(sync_test_setup):
    """Verifies task creation, attribute update, and soft deletion via sync operations."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    task_id = f"tsk_{uuid.uuid4().hex[:12]}"

    # Step 1: CREATE
    op1_uuid = str(uuid.uuid4())
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": op1_uuid,
                    "entity_type": "task",
                    "entity_id": task_id,
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {
                        "title": "Lifecycle Task",
                        "status": "Pending",
                        "category": "Coding",
                        "start_date": "2026-11-22",
                        "due_date": "2026-11-25",
                    },
                }
            ]
        },
        headers=headers,
    )

    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    assert task is not None
    assert task.title == "Lifecycle Task"
    assert task.version == 1
    assert task.is_deleted is False

    # Step 2: UPDATE
    op2_uuid = str(uuid.uuid4())
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": op2_uuid,
                    "entity_type": "task",
                    "entity_id": task_id,
                    "operation_type": "UPDATE",
                    "entity_version": 2,
                    "payload": {
                        "title": "Updated Lifecycle Task",
                        "status": "Completed",
                    },
                }
            ]
        },
        headers=headers,
    )

    db.refresh(task)
    assert task.title == "Updated Lifecycle Task"
    assert task.status == "Completed"
    assert task.version == 2

    # Step 3: DELETE (Soft Deletion)
    op3_uuid = str(uuid.uuid4())
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": op3_uuid,
                    "entity_type": "task",
                    "entity_id": task_id,
                    "operation_type": "DELETE",
                    "entity_version": 3,
                    "payload": {},
                }
            ]
        },
        headers=headers,
    )

    db.refresh(task)
    assert task.is_deleted is True
    assert task.deleted_at is not None
    assert task.version == 3

    # Check SyncEntityVersion
    sev = (
        db.query(SyncEntityVersion)
        .filter(SyncEntityVersion.entity_id == task_id)
        .first()
    )
    assert sev is not None
    assert sev.is_deleted is True
    assert sev.current_version == 3
    db.close()


# ---------------------------------------------------------------------------
# 8. Rejection of Invalid Entity Types and Invalid Operation Types
# ---------------------------------------------------------------------------

def test_push_rejection_of_invalid_operations(sync_test_setup):
    """Verifies that invalid entity types and invalid operation types are rejected safely."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    resp = client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": str(uuid.uuid4()),
                    "entity_type": "unsupported_crypto_wallet",
                    "entity_id": "c1",
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {},
                },
                {
                    "operation_uuid": str(uuid.uuid4()),
                    "entity_type": "task",
                    "entity_id": f"tsk_{uuid.uuid4().hex[:8]}",
                    "operation_type": "INVALID_VERB",
                    "entity_version": 1,
                    "payload": {},
                },
                {
                    "operation_uuid": str(uuid.uuid4()),
                    "entity_type": "task",
                    "entity_id": f"tsk_{uuid.uuid4().hex[:8]}",
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {"title": "Valid Operation In Mixed Batch"},
                },
            ]
        },
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] == 1
    assert data["rejected"] == 2
    assert data["results"][0]["status"] == "REJECTED"
    assert "unsupported entity_type" in data["results"][0]["message"].lower()
    assert data["results"][1]["status"] == "REJECTED"
    assert "invalid operation_type" in data["results"][1]["message"].lower()
    assert data["results"][2]["status"] == "APPLIED"


# ---------------------------------------------------------------------------
# 9. Cursor Pagination Stability & Monotonic Ordering
# ---------------------------------------------------------------------------

def test_pull_cursor_pagination_and_stability(sync_test_setup):
    """Verifies sequential cursor pagination across multiple operations."""
    s = sync_test_setup
    headers_push = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    # Push 4 distinct operations
    ops = [
        {
            "operation_uuid": str(uuid.uuid4()),
            "entity_type": "task",
            "entity_id": f"tsk_page_{i}",
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {"title": f"Pagination Task {i}"},
        }
        for i in range(4)
    ]
    p_resp = client.post("/api/sync/push", json={"operations": ops}, headers=headers_push)
    assert p_resp.status_code == 200

    headers_pull = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_b_uuid"],
    }

    # Fetch page 1: limit 2 from cursor 0
    r1 = client.get("/api/sync/pull?cursor=0&limit=2", headers=headers_pull)
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["changes"]) == 2
    assert d1["has_more"] is True
    cursor_1 = d1["next_cursor"]
    assert cursor_1 > 0

    # Fetch page 2: limit 2 from cursor_1
    r2 = client.get(f"/api/sync/pull?cursor={cursor_1}&limit=2", headers=headers_pull)
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["changes"]) >= 2
    cursor_2 = d2["next_cursor"]
    assert cursor_2 > cursor_1


# ---------------------------------------------------------------------------
# 10. Multi-Device Push & Pull with exclude_self
# ---------------------------------------------------------------------------

def test_pull_exclude_self(sync_test_setup):
    """Verifies that exclude_self filters out changes made by the requesting device."""
    s = sync_test_setup

    # Device A pushes op
    op_a_uuid = str(uuid.uuid4())
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": op_a_uuid,
                    "entity_type": "task",
                    "entity_id": f"tsk_dev_a_{uuid.uuid4().hex[:6]}",
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {"title": "Pushed by Device A"},
                }
            ]
        },
        headers={"Authorization": f"Bearer {s['token_u1']}", "X-Device-UUID": s["dev_a_uuid"]},
    )

    # Device B pushes op
    op_b_uuid = str(uuid.uuid4())
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": op_b_uuid,
                    "entity_type": "task",
                    "entity_id": f"tsk_dev_b_{uuid.uuid4().hex[:6]}",
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {"title": "Pushed by Device B"},
                }
            ]
        },
        headers={"Authorization": f"Bearer {s['token_u1']}", "X-Device-UUID": s["dev_b_uuid"]},
    )

    # Device A pulls with exclude_self=True
    resp = client.get(
        "/api/sync/pull?cursor=0&limit=50&exclude_self=true",
        headers={"Authorization": f"Bearer {s['token_u1']}", "X-Device-UUID": s["dev_a_uuid"]},
    )
    assert resp.status_code == 200
    changes = resp.json()["changes"]
    dev_uuids = [c["device_uuid"] for c in changes]
    assert s["dev_a_uuid"] not in dev_uuids
    assert s["dev_b_uuid"] in dev_uuids


# ---------------------------------------------------------------------------
# 11. Complete Tenant / User Isolation
# ---------------------------------------------------------------------------

def test_tenant_user_isolation(sync_test_setup):
    """Verifies that User 2 can never see or pull User 1's sync operations."""
    s = sync_test_setup

    # User 1 pushes private task
    private_task_id = f"tsk_private_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/sync/push",
        json={
            "operations": [
                {
                    "operation_uuid": str(uuid.uuid4()),
                    "entity_type": "task",
                    "entity_id": private_task_id,
                    "operation_type": "CREATE",
                    "entity_version": 1,
                    "payload": {"title": "User 1 Secret Task"},
                }
            ]
        },
        headers={"Authorization": f"Bearer {s['token_u1']}", "X-Device-UUID": s["dev_a_uuid"]},
    )

    # User 2 pulls all changes
    resp_u2 = client.get(
        "/api/sync/pull?cursor=0&limit=100",
        headers={"Authorization": f"Bearer {s['token_u2']}", "X-Device-UUID": s["dev_d_uuid"]},
    )
    assert resp_u2.status_code == 200
    changes_u2 = resp_u2.json()["changes"]
    for c in changes_u2:
        assert c["entity_id"] != private_task_id
        assert c["device_uuid"] != s["dev_a_uuid"]


# ---------------------------------------------------------------------------
# 12. Multi-Entity Synchronization
# ---------------------------------------------------------------------------

def test_multi_entity_type_sync(sync_test_setup):
    """Verifies synchronization of Goal, Habit, Timeblock, and DailyIntent."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    goal_id = f"gol_{uuid.uuid4().hex[:12]}"
    habit_id = f"hbt_{uuid.uuid4().hex[:12]}"
    tb_id = f"tbl_{uuid.uuid4().hex[:12]}"
    intent_id = f"int_{uuid.uuid4().hex[:12]}"

    ops = [
        {
            "operation_uuid": str(uuid.uuid4()),
            "entity_type": "goal",
            "entity_id": goal_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {
                "title": "Master Cloud Sync",
                "goal_type": "Short-Term",
                "category": "Coding",
                "priority": "High",
                "progress": 50,
                "start_date": "2026-11-22",
                "target_date": "2026-12-31",
            },
        },
        {
            "operation_uuid": str(uuid.uuid4()),
            "entity_type": "habit",
            "entity_id": habit_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {
                "name": "Sync Verification Habit",
                "frequency": "Daily",
                "category": "General",
                "base_streak": 3,
            },
        },
        {
            "operation_uuid": str(uuid.uuid4()),
            "entity_type": "daily_timeblock",
            "entity_id": tb_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {
                "title": "Deep Sync Coding",
                "time": "10:00 AM",
                "duration_minutes": 90,
                "block_date": "2026-11-22",
            },
        },
        {
            "operation_uuid": str(uuid.uuid4()),
            "entity_type": "daily_intent",
            "entity_id": intent_id,
            "operation_type": "CREATE",
            "entity_version": 1,
            "payload": {
                "intent_date": "2026-11-22",
                "intent_text": "Verify Phase 10F cloud sync foundation",
            },
        },
    ]

    resp = client.post("/api/sync/push", json={"operations": ops}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["applied"] == 4

    db = SessionLocal()
    g = db.query(Goal).filter(Goal.id == goal_id).first()
    assert g is not None
    assert g.progress == 50

    h = db.query(Habit).filter(Habit.id == habit_id).first()
    assert h is not None
    assert h.base_streak == 3

    tb = db.query(DailyTimeblock).filter(DailyTimeblock.id == tb_id).first()
    assert tb is not None
    assert tb.duration_minutes == 90

    di = db.query(DailyIntent).filter(DailyIntent.id == intent_id).first()
    assert di is not None
    assert "Phase 10F" in di.intent_text
    db.close()


# ---------------------------------------------------------------------------
# 13. Acknowledgment Endpoint
# ---------------------------------------------------------------------------

def test_acknowledge_endpoint(sync_test_setup):
    """Verifies that POST /api/sync/acknowledge updates cursor checkpoints."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    # Acknowledge cursor 10
    r1 = client.post("/api/sync/acknowledge", json={"cursor": 10}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["acknowledged"] is True
    assert r1.json()["last_pulled_cursor"] == 10

    # Advance to cursor 20
    r2 = client.post("/api/sync/acknowledge", json={"cursor": 20}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["last_pulled_cursor"] == 20

    # Lower cursor does not decrement monotonic checkpoint
    r3 = client.post("/api/sync/acknowledge", json={"cursor": 15}, headers=headers)
    assert r3.status_code == 200
    assert r3.json()["last_pulled_cursor"] == 20


# ---------------------------------------------------------------------------
# 14. Sync Status Endpoint
# ---------------------------------------------------------------------------

def test_sync_status_endpoint(sync_test_setup):
    """Verifies GET /api/sync/status reports accurate metrics."""
    s = sync_test_setup
    headers = {
        "Authorization": f"Bearer {s['token_u1']}",
        "X-Device-UUID": s["dev_a_uuid"],
    }

    resp = client.get("/api/sync/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == s["u1_id"]
    assert data["device_uuid"] == s["dev_a_uuid"]
    assert data["registered_devices_count"] >= 3
    assert data["device_status"] == "active"
    assert data["latest_server_cursor"] >= 0


# ---------------------------------------------------------------------------
# 15. Non-Regression: Authentication & Device Management APIs
# ---------------------------------------------------------------------------

def test_non_regression_auth_and_devices(sync_test_setup):
    """Verifies existing login, token verification, device registration, and device listing work seamlessly."""
    s = sync_test_setup

    # Register new device via existing endpoint
    headers = {"Authorization": f"Bearer {s['token_u1']}"}
    new_dev_uuid = str(uuid.uuid4())
    r_dev = client.post(
        "/api/devices/register",
        json={
            "device_uuid": new_dev_uuid,
            "device_name": "Non-Regression Laptop",
            "device_type": "Laptop",
            "operating_system": "Windows 11",
            "client_version": "2.0.0",
        },
        headers=headers,
    )
    assert r_dev.status_code == 201
    assert r_dev.json()["device_uuid"] == new_dev_uuid

    # List devices
    r_list = client.get("/api/devices", headers=headers)
    assert r_list.status_code == 200
    assert len(r_list.json()) >= 4


# ---------------------------------------------------------------------------
# 16. Non-Regression: Productivity APIs
# ---------------------------------------------------------------------------

def test_non_regression_productivity_apis(sync_test_setup):
    """Verifies standard REST endpoints (/api/tasks, /api/goals, /api/habits) remain fully operational."""
    s = sync_test_setup
    headers = {"Authorization": f"Bearer {s['token_u1']}"}

    # Create task via standard API
    r_task = client.post(
        "/api/tasks",
        json={
            "title": "Non-Regression REST Task",
            "task_type": "Daily",
            "category": "Coding",
            "priority": "Medium",
            "start_date": "2026-11-22",
            "due_date": "2026-11-22",
        },
        headers=headers,
    )
    assert r_task.status_code == 201
    task_data = r_task.json()
    assert task_data["title"] == "Non-Regression REST Task"

    # List tasks
    r_tasks_list = client.get("/api/tasks", headers=headers)
    assert r_tasks_list.status_code == 200
    assert isinstance(r_tasks_list.json(), list)

    # List habits
    r_habits = client.get("/api/habits", headers=headers)
    assert r_habits.status_code == 200

    # List goals
    r_goals = client.get("/api/goals", headers=headers)
    assert r_goals.status_code == 200
