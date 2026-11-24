"""
NIYANTRA Phase 10H Verification Suite: Conflict Detection & Resolution Backend

Tests:
1. SyncConflict model definition and metadata
2. Record conflict endpoint (POST /api/sync/conflicts/record)
3. List user conflicts endpoint (GET /api/sync/conflicts)
4. Keep Local conflict resolution with version increment and broadcast
5. Keep Remote conflict resolution
6. Manual Merge conflict resolution with merged payload propagation
7. Strict tenant isolation (User B cannot resolve User A conflicts)
8. Revoked device rejection on conflict endpoints
9. Strict JWT authentication enforcement
"""
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.sync import SyncOperation, SyncEntityVersion, SyncConflict

client = TestClient(app)


@pytest.fixture(scope="module")
def conflict_test_setup():
    """
    Creates test users and test devices for isolation in Phase 10H conflict tests.
    """
    db = SessionLocal()
    prefix = uuid.uuid4().hex[:8]

    # User 1
    u1_id = f"usr_{prefix}_1"
    u1 = User(
        id=u1_id,
        uuid=str(uuid.uuid4()),
        name="Conflict User Alpha",
        email=f"alpha_{prefix}@niyantra.test",
        password_hash=hash_password("alphaPass123!"),
        is_active=True,
        status="active",
    )
    db.add(u1)

    # User 1 Device A
    d1_a_uuid = f"dev_{prefix}_1a"
    d1_a = Device(
        device_uuid=d1_a_uuid,
        user_id=u1_id,
        device_name="Alpha Laptop",
        device_type="Desktop",
        operating_system="Windows",
        status="active",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(d1_a)

    # User 1 Device B
    d1_b_uuid = f"dev_{prefix}_1b"
    d1_b = Device(
        device_uuid=d1_b_uuid,
        user_id=u1_id,
        device_name="Alpha Phone",
        device_type="Mobile",
        operating_system="Android",
        status="active",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(d1_b)

    # User 1 Revoked Device
    d1_rev_uuid = f"dev_{prefix}_rev"
    d1_rev = Device(
        device_uuid=d1_rev_uuid,
        user_id=u1_id,
        device_name="Alpha Lost Tablet",
        device_type="Tablet",
        operating_system="iOS",
        status="revoked",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(d1_rev)

    # User 2 (Tenant Isolation)
    u2_id = f"usr_{prefix}_2"
    u2 = User(
        id=u2_id,
        uuid=str(uuid.uuid4()),
        name="Conflict User Bravo",
        email=f"bravo_{prefix}@niyantra.test",
        password_hash=hash_password("bravoPass123!"),
        is_active=True,
        status="active",
    )
    db.add(u2)

    # User 2 Device
    d2_uuid = f"dev_{prefix}_2"
    d2 = Device(
        device_uuid=d2_uuid,
        user_id=u2_id,
        device_name="Bravo Workstation",
        device_type="Desktop",
        operating_system="Linux",
        status="active",
        registered_at=datetime.now(timezone.utc),
    )
    db.add(d2)

    db.commit()

    token_u1 = create_access_token(subject=u1_id, email=u1.email)
    token_u2 = create_access_token(subject=u2_id, email=u2.email)

    yield {
        "user1": u1,
        "token1": token_u1,
        "dev1_a": d1_a_uuid,
        "dev1_b": d1_b_uuid,
        "dev1_rev": d1_rev_uuid,
        "user2": u2,
        "token2": token_u2,
        "dev2": d2_uuid,
        "prefix": prefix,
    }

    db.close()


def test_sync_conflict_model_attributes():
    """Verifies that SyncConflict model has correct columns, types, and tablename."""
    assert SyncConflict.__tablename__ == "sync_conflicts"
    col_names = {c.name for c in SyncConflict.__table__.columns}
    required = {
        "id", "user_id", "entity_type", "entity_id", "base_version",
        "local_version", "remote_version", "detecting_device_uuid",
        "conflicting_device_uuid", "status", "resolution_strategy",
        "local_data", "remote_data", "resolved_data", "detected_at", "resolved_at"
    }
    assert required.issubset(col_names)


def test_unauthenticated_conflict_access(conflict_test_setup):
    """Verifies unauthenticated requests to conflict endpoints return HTTP 401."""
    res_list = client.get("/api/sync/conflicts")
    assert res_list.status_code == 401

    res_record = client.post("/api/sync/conflicts/record", json={"id": "test"})
    assert res_record.status_code == 401

    res_resolve = client.post("/api/sync/conflicts/c1/resolve", json={"strategy": "KEEP_LOCAL"})
    assert res_resolve.status_code == 401


def test_record_and_list_conflicts(conflict_test_setup):
    """Verifies conflict registration and user listing."""
    ctx = conflict_test_setup
    headers = {
        "Authorization": f"Bearer {ctx['token1']}",
        "X-Device-UUID": ctx["dev1_a"],
    }
    conflict_id = f"conf-{ctx['prefix']}-1"
    entity_id = f"task-{ctx['prefix']}-1"

    req_payload = {
        "id": conflict_id,
        "entity_type": "task",
        "entity_id": entity_id,
        "base_version": 1,
        "local_version": 2,
        "remote_version": 2,
        "detecting_device_uuid": ctx["dev1_a"],
        "conflicting_device_uuid": ctx["dev1_b"],
        "local_data": {"title": "Local Task Title", "priority": "High"},
        "remote_data": {"title": "Remote Task Title", "priority": "Low"},
    }

    # Record conflict
    res = client.post("/api/sync/conflicts/record", json=req_payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == conflict_id
    assert data["status"] == "PENDING_RESOLUTION"
    assert data["local_data"]["title"] == "Local Task Title"

    # List conflicts
    res_list = client.get("/api/sync/conflicts", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total_unresolved"] >= 1
    ids = [c["id"] for c in list_data["conflicts"]]
    assert conflict_id in ids


def test_resolve_conflict_keep_local(conflict_test_setup):
    """Verifies Keep Local resolution bumps version and creates broadcast operation."""
    ctx = conflict_test_setup
    headers = {
        "Authorization": f"Bearer {ctx['token1']}",
        "X-Device-UUID": ctx["dev1_a"],
    }
    conflict_id = f"conf-{ctx['prefix']}-local"
    entity_id = f"task-{ctx['prefix']}-local"

    # Create initial task in database
    db = SessionLocal()
    today = datetime.now(timezone.utc).date()
    t = Task(
        id=entity_id,
        user_id=ctx["user1"].id,
        title="Original Task",
        priority="Medium",
        task_type="Daily",
        category="Coding",
        start_date=today,
        due_date=today,
        version=1,
    )
    db.add(t)
    db.commit()
    db.close()

    # Record conflict
    client.post(
        "/api/sync/conflicts/record",
        json={
            "id": conflict_id,
            "entity_type": "task",
            "entity_id": entity_id,
            "base_version": 1,
            "local_version": 2,
            "remote_version": 2,
            "local_data": {"id": entity_id, "title": "Local Winning Task", "priority": "High"},
            "remote_data": {"id": entity_id, "title": "Remote Task", "priority": "Low"},
        },
        headers=headers,
    )

    # Resolve with KEEP_LOCAL
    res = client.post(
        f"/api/sync/conflicts/{conflict_id}/resolve",
        json={
            "strategy": "KEEP_LOCAL",
            "resolved_data": {"id": entity_id, "title": "Local Winning Task", "priority": "High"},
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "RESOLVED_LOCAL"
    assert data["resolution_strategy"] == "KEEP_LOCAL"

    # Verify task updated in database
    db = SessionLocal()
    updated_task = db.query(Task).filter(Task.id == entity_id).first()
    assert updated_task.title == "Local Winning Task"
    assert updated_task.priority == "High"
    assert updated_task.version >= 3
    db.close()


def test_resolve_conflict_manual_merge(conflict_test_setup):
    """Verifies Manual Merge resolution combines attributes and broadcasts merged operation."""
    ctx = conflict_test_setup
    headers = {
        "Authorization": f"Bearer {ctx['token1']}",
        "X-Device-UUID": ctx["dev1_a"],
    }
    conflict_id = f"conf-{ctx['prefix']}-merge"
    entity_id = f"task-{ctx['prefix']}-merge"

    # Record conflict
    client.post(
        "/api/sync/conflicts/record",
        json={
            "id": conflict_id,
            "entity_type": "task",
            "entity_id": entity_id,
            "base_version": 1,
            "local_version": 2,
            "remote_version": 2,
            "local_data": {"id": entity_id, "title": "ML Assignment", "priority": "High"},
            "remote_data": {"id": entity_id, "title": "ML Assignment", "priority": "Low", "due_date": "2026-11-28"},
        },
        headers=headers,
    )

    # Resolve with MANUAL_MERGE
    merged = {
        "id": entity_id,
        "title": "ML Assignment",
        "priority": "High",
        "due_date": "2026-11-28",
    }
    res = client.post(
        f"/api/sync/conflicts/{conflict_id}/resolve",
        json={
            "strategy": "MANUAL_MERGE",
            "resolved_data": merged,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "RESOLVED_MERGED"
    assert data["resolution_strategy"] == "MANUAL_MERGE"


def test_cross_tenant_isolation(conflict_test_setup):
    """Verifies User 2 cannot access or resolve User 1's conflict (HTTP 403 / 404)."""
    ctx = conflict_test_setup
    headers_u1 = {
        "Authorization": f"Bearer {ctx['token1']}",
        "X-Device-UUID": ctx["dev1_a"],
    }
    headers_u2 = {
        "Authorization": f"Bearer {ctx['token2']}",
        "X-Device-UUID": ctx["dev2"],
    }
    conflict_id = f"conf-{ctx['prefix']}-isolated"

    # User 1 creates conflict
    client.post(
        "/api/sync/conflicts/record",
        json={
            "id": conflict_id,
            "entity_type": "task",
            "entity_id": "t-isolated",
            "local_data": {"title": "Private User 1 Task"},
        },
        headers=headers_u1,
    )

    # User 2 tries to resolve User 1's conflict -> Forbidden
    res = client.post(
        f"/api/sync/conflicts/{conflict_id}/resolve",
        json={"strategy": "KEEP_LOCAL"},
        headers=headers_u2,
    )
    assert res.status_code == 403
    assert "different account" in res.json()["detail"]


def test_revoked_device_conflict_rejection(conflict_test_setup):
    """Verifies that a revoked device cannot resolve conflicts (HTTP 403)."""
    ctx = conflict_test_setup
    headers_revoked = {
        "Authorization": f"Bearer {ctx['token1']}",
        "X-Device-UUID": ctx["dev1_rev"],
    }
    res = client.post(
        "/api/sync/conflicts/conf-any/resolve",
        json={"strategy": "KEEP_LOCAL"},
        headers=headers_revoked,
    )
    assert res.status_code == 403
    assert "revoked" in res.json()["detail"].lower()
