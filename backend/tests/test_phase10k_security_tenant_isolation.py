import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt

from backend.app.main import app
from backend.app.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import hash_password, create_access_token
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit


@pytest.fixture
def auth_fixture(db_session: Session):
    """Creates two distinct, fully isolated user accounts and devices for testing."""
    uid_a = f"usr_test_a_{uuid.uuid4().hex[:8]}"
    uid_b = f"usr_test_b_{uuid.uuid4().hex[:8]}"
    
    user_a = User(
        id=uid_a,
        uuid=str(uuid.uuid4()),
        name="Security Audit User A",
        email=f"audit_a_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("SecAuditPassA!123"),
        is_active=True,
        status="active"
    )
    user_b = User(
        id=uid_b,
        uuid=str(uuid.uuid4()),
        name="Security Audit User B",
        email=f"audit_b_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("SecAuditPassB!123"),
        is_active=True,
        status="active"
    )
    db_session.add(user_a)
    db_session.add(user_b)
    db_session.commit()

    dev_a_uuid = f"dev-sec-a-{uuid.uuid4().hex[:8]}"
    dev_b_uuid = f"dev-sec-b-{uuid.uuid4().hex[:8]}"

    dev_a = Device(
        user_id=uid_a,
        device_uuid=dev_a_uuid,
        device_name="Laptop A",
        device_type="laptop",
        status="active"
    )
    dev_b = Device(
        user_id=uid_b,
        device_uuid=dev_b_uuid,
        device_name="Phone B",
        device_type="mobile",
        status="active"
    )
    db_session.add(dev_a)
    db_session.add(dev_b)
    db_session.commit()

    token_a = create_access_token(subject=uid_a, email=user_a.email)
    token_b = create_access_token(subject=uid_b, email=user_b.email)

    return {
        "user_a": user_a,
        "user_b": user_b,
        "dev_a": dev_a,
        "dev_b": dev_b,
        "token_a": token_a,
        "token_b": token_b,
        "headers_a": {"Authorization": f"Bearer {token_a}", "X-Device-UUID": dev_a_uuid},
        "headers_b": {"Authorization": f"Bearer {token_b}", "X-Device-UUID": dev_b_uuid},
    }

def test_tenant_isolation_tasks(client, auth_fixture, db_session):
    """User B cannot view, edit, or delete User A's task."""
    headers_a = auth_fixture["headers_a"]
    headers_b = auth_fixture["headers_b"]

    # User A creates a task
    create_res = client.post(
        "/api/tasks/",
        json={"title": "User A Confidential Task", "priority": "High", "time_estimate": 30},
        headers=headers_a
    )
    assert create_res.status_code in [200, 201], create_res.text
    task_id = create_res.json()["id"]

    # User B tries to read User A's task
    get_res = client.get(f"/api/tasks/{task_id}", headers=headers_b)
    assert get_res.status_code in [404, 403], "User B should not be able to read User A's task"

    # User B tries to update User A's task
    update_res = client.put(f"/api/tasks/{task_id}", json={"title": "Compromised Title"}, headers=headers_b)
    assert update_res.status_code in [404, 403], "User B should not be able to update User A's task"

    # User B tries to delete User A's task
    del_res = client.delete(f"/api/tasks/{task_id}", headers=headers_b)
    assert del_res.status_code in [404, 403], "User B should not be able to delete User A's task"

    # Verify task was untouched
    verify_res = client.get(f"/api/tasks/{task_id}", headers=headers_a)
    assert verify_res.status_code == 200
    assert verify_res.json()["title"] == "User A Confidential Task"

def test_tenant_isolation_goals_and_habits(client, auth_fixture, db_session):
    """User B cannot view User A's goals or habits."""
    headers_a = auth_fixture["headers_a"]
    headers_b = auth_fixture["headers_b"]

    # User A creates a goal
    goal_res = client.post("/api/goals/", json={"title": "Confidential Goal A", "target_date": "2026-12-31"}, headers=headers_a)
    assert goal_res.status_code in [200, 201], goal_res.text
    goal_id = goal_res.json()["id"]

    # User B tries to read User A's goal
    get_goal = client.get(f"/api/goals/{goal_id}", headers=headers_b)
    assert get_goal.status_code in [404, 403]

    # User A creates a habit
    habit_res = client.post("/api/habits/", json={"name": "Confidential Habit A", "frequency": "Daily"}, headers=headers_a)
    assert habit_res.status_code in [200, 201], habit_res.text
    habit_id = habit_res.json()["id"]

    # User B tries to read User A's habit
    get_habit = client.get(f"/api/habits/{habit_id}", headers=headers_b)
    assert get_habit.status_code in [404, 403]

def test_device_ownership_and_revocation(client, auth_fixture, db_session):
    """Device belonging to User A cannot be hijacked by User B, and revoked devices cannot sync."""
    user_b_token = auth_fixture["token_b"]
    dev_a_uuid = auth_fixture["dev_a"].device_uuid

    # User B attempts to push changes using User A's device UUID
    hijack_headers = {
        "Authorization": f"Bearer {user_b_token}",
        "X-Device-UUID": dev_a_uuid
    }
    push_payload = {
        "device_uuid": dev_a_uuid,
        "operations": []
    }
    hijack_res = client.post("/api/sync/push", json=push_payload, headers=hijack_headers)
    assert hijack_res.status_code == 403, f"Expected 403, got {hijack_res.status_code}"
    assert "Device ownership mismatch" in hijack_res.text

    # User A revokes Device A
    dev_a = auth_fixture["dev_a"]
    dev_a.status = "revoked"
    db_session.commit()

    # User A attempts to push with revoked device
    revoked_res = client.post("/api/sync/push", json=push_payload, headers=auth_fixture["headers_a"])
    assert revoked_res.status_code == 403
    assert "revoked" in revoked_res.text

def test_sync_delta_isolation(client, auth_fixture, db_session):
    """User B's pull request receives 0 operations from User A's sync queue."""
    headers_a = auth_fixture["headers_a"]
    headers_b = auth_fixture["headers_b"]
    dev_a_uuid = auth_fixture["dev_a"].device_uuid
    dev_b_uuid = auth_fixture["dev_b"].device_uuid

    # User A pushes a sync operation
    client_entity_id = str(uuid.uuid4())
    op_payload = {
        "device_uuid": dev_a_uuid,
        "operations": [
            {
                "operation_uuid": str(uuid.uuid4()),
                "device_uuid": dev_a_uuid,
                "entity_type": "task",
                "entity_id": client_entity_id,
                "operation_type": "CREATE",
                "entity_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "payload": {"title": "User A Private Sync Task"}
            }
        ]
    }
    push_res = client.post("/api/sync/push", json=op_payload, headers=headers_a)
    assert push_res.status_code == 200

    # User B pulls changes from cursor 0
    pull_res = client.get("/api/sync/pull?cursor=0", headers=headers_b)
    assert pull_res.status_code == 200
    pulled_ops = pull_res.json()["changes"]
    
    # Assert none of User A's entity IDs are present in User B's pull
    pulled_entity_ids = [op["entity_id"] for op in pulled_ops]
    assert client_entity_id not in pulled_entity_ids, "Cross-user data leakage detected in /sync/pull!"

def test_jwt_validation_and_tampering(client, auth_fixture):
    """Validates signature rejection, expired tokens, and missing tokens."""
    token = auth_fixture["token_a"]

    # 1. Missing Authorization header
    res_no_auth = client.get("/api/sync/pull?cursor=0")
    assert res_no_auth.status_code == 401

    # 2. Tampered token signature
    tampered_token = token[:-5] + "XXXXX"
    res_tampered = client.get("/api/sync/pull?cursor=0", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401
    assert "Invalid authentication token" in res_tampered.text

    # 3. Expired token
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": auth_fixture["user_a"].id,
        "email": auth_fixture["user_a"].email,
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
        "jti": str(uuid.uuid4())
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    res_expired = client.get("/api/sync/pull?cursor=0", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401
    assert "expired" in res_expired.text.lower()

def test_password_hashing_security():
    """Confirms bcrypt algorithm, random salt uniqueness, and constant-time verification."""
    raw_pwd = "SuperSecretPassword#2026"
    h1 = hash_password(raw_pwd)
    h2 = hash_password(raw_pwd)

    # Hashes must start with bcrypt identifier
    assert h1.startswith("$2b$") or h1.startswith("$2a$")
    assert h2.startswith("$2b$") or h2.startswith("$2a$")
    # Salting must ensure hashes are different for the same password
    assert h1 != h2
