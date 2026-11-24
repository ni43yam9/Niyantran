import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password, create_access_token
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.sync import SyncOperation, SyncEntityVersion, SyncConflict

@pytest.fixture
def sync_reliability_fixture(db_session: Session):
    user_id = f"usr_rel_{uuid.uuid4().hex[:8]}"
    user = User(
        id=user_id,
        uuid=str(uuid.uuid4()),
        name="Reliability User",
        email=f"rel_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Pass123!Reliable"),
        is_active=True,
        status="active"
    )
    db_session.add(user)
    db_session.commit()

    dev_1_uuid = f"dev-1-{uuid.uuid4().hex[:8]}"
    dev_2_uuid = f"dev-2-{uuid.uuid4().hex[:8]}"
    
    dev_1 = Device(
        user_id=user_id,
        device_uuid=dev_1_uuid,
        device_name="Device Laptop",
        device_type="laptop",
        status="active"
    )
    dev_2 = Device(
        user_id=user_id,
        device_uuid=dev_2_uuid,
        device_name="Device Mobile",
        device_type="mobile",
        status="active"
    )
    db_session.add(dev_1)
    db_session.add(dev_2)
    db_session.commit()

    token = create_access_token(subject=user_id, email=user.email)
    
    return {
        "user": user,
        "dev_1_uuid": dev_1_uuid,
        "dev_2_uuid": dev_2_uuid,
        "token": token,
        "headers_dev1": {"Authorization": f"Bearer {token}", "X-Device-UUID": dev_1_uuid},
        "headers_dev2": {"Authorization": f"Bearer {token}", "X-Device-UUID": dev_2_uuid},
    }

def test_offline_create_update_delete_lifecycle(client, sync_reliability_fixture, db_session):
    """Verifies that CREATE, UPDATE, and DELETE (tombstone) survive and propagate with correct versions."""
    headers1 = sync_reliability_fixture["headers_dev1"]
    headers2 = sync_reliability_fixture["headers_dev2"]
    dev1 = sync_reliability_fixture["dev_1_uuid"]
    dev2 = sync_reliability_fixture["dev_2_uuid"]
    entity_id = f"task-rel-{uuid.uuid4().hex[:8]}"

    # 1. CREATE Operation
    create_op = {
        "operation_uuid": str(uuid.uuid4()),
        "device_uuid": dev1,
        "entity_type": "task",
        "entity_id": entity_id,
        "operation_type": "CREATE",
        "entity_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "title": "Reliability Audit Task",
            "priority": "High",
            "category": "Coding",
            "status": "Pending"
        }
    }
    push_create = client.post("/api/sync/push", json={"device_uuid": dev1, "operations": [create_op]}, headers=headers1)
    assert push_create.status_code == 200
    assert push_create.json()["applied"] == 1

    # 2. UPDATE Operation
    update_op = {
        "operation_uuid": str(uuid.uuid4()),
        "device_uuid": dev1,
        "entity_type": "task",
        "entity_id": entity_id,
        "operation_type": "UPDATE",
        "entity_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "title": "Reliability Audit Task - In Progress",
            "status": "In Progress"
        }
    }
    push_update = client.post("/api/sync/push", json={"device_uuid": dev1, "operations": [update_op]}, headers=headers1)
    assert push_update.status_code == 200
    assert push_update.json()["applied"] == 1

    # 3. DELETE Operation (Tombstone)
    delete_op = {
        "operation_uuid": str(uuid.uuid4()),
        "device_uuid": dev1,
        "entity_type": "task",
        "entity_id": entity_id,
        "operation_type": "DELETE",
        "entity_version": 3,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {}
    }
    push_delete = client.post("/api/sync/push", json={"device_uuid": dev1, "operations": [delete_op]}, headers=headers1)
    assert push_delete.status_code == 200
    assert push_delete.json()["applied"] == 1

    # Verify underlying database entity tombstone status
    task = db_session.query(Task).filter(Task.id == entity_id).first()
    assert task is not None, "Tombstone record should be preserved"
    assert task.is_deleted is True, "Entity must be marked is_deleted=True"
    assert task.deleted_at is not None, "deleted_at timestamp must be recorded"

    # Device 2 pulls from cursor 0: should receive all 3 changes including the final DELETE
    pull_res = client.get("/api/sync/pull?cursor=0", headers=headers2)
    assert pull_res.status_code == 200
    changes = pull_res.json()["changes"]
    entity_changes = [c for c in changes if c["entity_id"] == entity_id]
    assert len(entity_changes) == 3
    assert entity_changes[-1]["operation_type"] == "DELETE"

def test_idempotency_and_duplicate_suppression(client, sync_reliability_fixture, db_session):
    """Pushing identical operation payload multiple times is idempotent."""
    headers1 = sync_reliability_fixture["headers_dev1"]
    dev1 = sync_reliability_fixture["dev_1_uuid"]
    op_uuid = str(uuid.uuid4())
    entity_id = f"task-idem-{uuid.uuid4().hex[:8]}"

    op = {
        "operation_uuid": op_uuid,
        "device_uuid": dev1,
        "entity_type": "task",
        "entity_id": entity_id,
        "operation_type": "CREATE",
        "entity_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "title": "Idempotency Test Task",
            "category": "Coding",
            "priority": "Medium",
            "status": "Pending"
        }
    }

    # First push
    res1 = client.post("/api/sync/push", json={"device_uuid": dev1, "operations": [op]}, headers=headers1)
    assert res1.status_code == 200
    assert res1.json()["applied"] == 1

    # Second push (identical operation)
    res2 = client.post("/api/sync/push", json={"device_uuid": dev1, "operations": [op]}, headers=headers1)
    assert res2.status_code == 200
    results = res2.json()["results"]
    assert len(results) == 1
    assert "already processed" in results[0]["message"].lower()

    # Verify no duplicate rows in SyncOperation
    op_count = db_session.query(SyncOperation).filter(SyncOperation.operation_uuid == op_uuid).count()
    assert op_count == 1, "Duplicate operation should not create duplicate rows"

    # Verify entity version remained 1
    ev = db_session.query(SyncEntityVersion).filter(SyncEntityVersion.entity_id == entity_id).first()
    assert ev.current_version == 1

def test_conflict_resolution_consistency(client, sync_reliability_fixture, db_session):
    """Verifies that conflict resolution adheres to Phase 10H strategies (KEEP_LOCAL, KEEP_REMOTE, MANUAL_MERGE)."""
    headers1 = sync_reliability_fixture["headers_dev1"]
    dev1 = sync_reliability_fixture["dev_1_uuid"]
    dev2 = sync_reliability_fixture["dev_2_uuid"]
    user_id = sync_reliability_fixture["user"].id
    entity_id = f"task-conf-{uuid.uuid4().hex[:8]}"

    # Seed a conflict record
    conflict = SyncConflict(
        id=f"conf-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        entity_type="task",
        entity_id=entity_id,
        base_version=1,
        local_version=2,
        remote_version=2,
        detecting_device_uuid=dev1,
        conflicting_device_uuid=dev2,
        local_data={"title": "Local Version of Task", "category": "Coding"},
        remote_data={"title": "Remote Version of Task", "category": "Coding"},
        status="DETECTED"
    )
    db_session.add(conflict)
    db_session.commit()

    # 1. Resolve with MANUAL_MERGE
    resolve_payload = {
        "strategy": "MANUAL_MERGE",
        "resolved_data": {
            "title": "Merged Title: Local + Remote Unified",
            "priority": "High",
            "category": "Coding",
            "status": "In Progress"
        }
    }
    resolve_res = client.post(f"/api/sync/conflicts/{conflict.id}/resolve", json=resolve_payload, headers=headers1)
    assert resolve_res.status_code == 200, resolve_res.text
    res_data = resolve_res.json()
    assert res_data["status"] == "RESOLVED_MERGED"
    assert res_data["resolution_strategy"] == "MANUAL_MERGE"

    # Verify that a winning SyncOperation was broadcast with bumped version
    ev = db_session.query(SyncEntityVersion).filter(SyncEntityVersion.entity_id == entity_id).first()
    assert ev is not None
    assert ev.current_version >= 3

    # Verify task was updated to the merged state
    task = db_session.query(Task).filter(Task.id == entity_id).first()
    assert task is not None
    assert task.title == "Merged Title: Local + Remote Unified"
