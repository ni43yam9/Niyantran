import uuid
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.database import get_db, SessionLocal
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.device import Device
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.recommendation import Recommendation

client = TestClient(app)


def unique_email(prefix: str = "test") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@niyantra.app"


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 1. USER AUTHENTICATION TESTS
# ---------------------------------------------------------------------------

def test_user_registration_success():
    email = unique_email("user_register")
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Alex Mercer",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email
    assert data["user"]["name"] == "Alex Mercer"
    assert data["user"]["status"] == "active"
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_duplicate_email_rejection():
    email = unique_email("duplicate_test")
    # First registration
    client.post(
        "/api/auth/register",
        json={"name": "First User", "email": email, "password": "Password123"},
    )
    # Duplicate registration
    response = client.post(
        "/api/auth/register",
        json={"name": "Second User", "email": email, "password": "Password123"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_user_login_success_and_password_verification():
    email = unique_email("login_success")
    password = "CorrectPassword123!"
    client.post(
        "/api/auth/register",
        json={"name": "Login User", "email": email, "password": password},
    )

    # Valid login
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == email

    # Verify password hash directly
    session = SessionLocal()
    user_db = session.query(User).filter(User.email == email).first()
    assert user_db is not None
    assert user_db.password_hash != password
    assert verify_password(password, user_db.password_hash) is True
    assert verify_password("WrongPassword!", user_db.password_hash) is False
    session.close()


def test_incorrect_password_rejection():
    email = unique_email("login_fail")
    client.post(
        "/api/auth/register",
        json={"name": "Fail User", "email": email, "password": "OriginalPassword1"},
    )

    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPasswordX"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


def test_protected_endpoint_me_and_invalid_token():
    # 1. Unauthenticated request to strictly protected /api/auth/me
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401

    # 2. Invalid bearer token
    resp_bad = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not_a_valid_jwt_token_string"},
    )
    assert resp_bad.status_code == 401
    assert "Invalid" in resp_bad.json()["detail"]

    # 3. Valid bearer token
    email = unique_email("protected")
    reg = client.post(
        "/api/auth/register",
        json={"name": "Protected Test", "email": email, "password": "Password123"},
    ).json()
    token = reg["access_token"]

    resp_me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_me.status_code == 200
    assert resp_me.json()["email"] == email


def test_expired_token_rejection():
    # Manually issue an already expired token (negative delta)
    expired_token = create_access_token(
        subject="test_user_expired",
        email=unique_email("expired"),
        expires_delta=timedelta(seconds=-10),
    )
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_user_logout_endpoint():
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


# ---------------------------------------------------------------------------
# 2. DEVICE MANAGEMENT TESTS
# ---------------------------------------------------------------------------

def test_device_registration_and_listing():
    email = unique_email("devices_test")
    reg = client.post(
        "/api/auth/register",
        json={"name": "Device Tester", "email": email, "password": "Password123"},
    ).json()
    token = reg["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # Register Device 1 (Laptop)
    dev1_resp = client.post(
        "/api/devices/register",
        headers=auth_header,
        json={
            "device_name": "Work Laptop",
            "device_type": "Laptop",
            "operating_system": "Windows 11",
            "client_version": "2.0.0",
        },
    )
    assert dev1_resp.status_code == 201
    dev1 = dev1_resp.json()
    assert dev1["device_name"] == "Work Laptop"
    assert dev1["status"] == "active"
    assert dev1["last_synced_at"] is None

    # Register Device 2 (Mobile)
    dev2_resp = client.post(
        "/api/devices/register",
        headers=auth_header,
        json={
            "device_name": "Pixel 9 Pro",
            "device_type": "Mobile",
            "operating_system": "Android 15",
            "client_version": "2.0.0",
        },
    )
    assert dev2_resp.status_code == 201

    # List devices
    list_resp = client.get("/api/devices", headers=auth_header)
    assert list_resp.status_code == 200
    devices = list_resp.json()
    assert len(devices) >= 2
    device_names = [d["device_name"] for d in devices]
    assert "Work Laptop" in device_names
    assert "Pixel 9 Pro" in device_names


def test_device_update_and_revocation():
    email = unique_email("dev_update")
    reg = client.post(
        "/api/auth/register",
        json={"name": "Dev Update User", "email": email, "password": "Password123"},
    ).json()
    auth_header = {"Authorization": f"Bearer {reg['access_token']}"}

    dev = client.post(
        "/api/devices/register",
        headers=auth_header,
        json={"device_name": "Old Device Name", "device_type": "Desktop", "operating_system": "macOS"},
    ).json()
    dev_id = dev["id"]

    # Patch device
    patch_resp = client.patch(
        f"/api/devices/{dev_id}",
        headers=auth_header,
        json={"device_name": "New Renamed Desktop", "device_type": "Desktop"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["device_name"] == "New Renamed Desktop"

    # Revoke device
    revoke_resp = client.post(
        f"/api/devices/{dev_id}/revoke",
        headers=auth_header,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    # Verify status in DB
    session = SessionLocal()
    dev_db = session.query(Device).filter(Device.id == dev_id).first()
    assert dev_db.status == "revoked"
    session.close()


def test_unauthorized_device_access_between_users():
    # User A
    user_a = client.post(
        "/api/auth/register",
        json={"name": "User Alpha", "email": unique_email("alpha_dev"), "password": "Password123"},
    ).json()
    auth_a = {"Authorization": f"Bearer {user_a['access_token']}"}

    dev_a = client.post(
        "/api/devices/register",
        headers=auth_a,
        json={"device_name": "Alpha Phone", "device_type": "Mobile", "operating_system": "iOS"},
    ).json()

    # User B
    user_b = client.post(
        "/api/auth/register",
        json={"name": "User Beta", "email": unique_email("beta_dev"), "password": "Password123"},
    ).json()
    auth_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    # User B attempts to access User A's device
    resp_get = client.get(f"/api/devices/{dev_a['id']}", headers=auth_b)
    assert resp_get.status_code == 404

    # User B attempts to revoke User A's device
    resp_revoke = client.post(f"/api/devices/{dev_a['id']}/revoke", headers=auth_b)
    assert resp_revoke.status_code == 404


# ---------------------------------------------------------------------------
# 3. DATA OWNERSHIP & ISOLATION TESTS
# ---------------------------------------------------------------------------

def test_user_data_isolation_tasks_goals_habits():
    # 1. Create User A and User B
    user_a = client.post(
        "/api/auth/register",
        json={"name": "User A", "email": unique_email("user_a"), "password": "Password123"},
    ).json()
    auth_a = {"Authorization": f"Bearer {user_a['access_token']}"}

    user_b = client.post(
        "/api/auth/register",
        json={"name": "User B", "email": unique_email("user_b"), "password": "Password123"},
    ).json()
    auth_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    # 2. User A creates a task
    task_a = client.post(
        "/api/tasks",
        headers=auth_a,
        json={"title": "Private Task for User A", "category": "Coding", "priority": "High"},
    ).json()
    task_a_id = task_a["id"]

    # User B cannot get User A's task
    get_task_b = client.get(f"/api/tasks/{task_a_id}", headers=auth_b)
    assert get_task_b.status_code == 404

    # User B cannot update User A's task
    update_task_b = client.put(f"/api/tasks/{task_a_id}", headers=auth_b, json={"title": "Hacked Title"})
    assert update_task_b.status_code == 404

    # User B's task list does not include User A's task
    tasks_b = client.get("/api/tasks", headers=auth_b).json()
    assert all(t["id"] != task_a_id for t in tasks_b)

    # 3. User A creates a goal
    goal_a = client.post(
        "/api/goals",
        headers=auth_a,
        json={
            "title": "Private Goal for User A",
            "category": "Coding",
            "goalType": "Short-Term",
            "targetDate": "2026-12-31",
        },
    ).json()
    goal_a_id = goal_a["id"]

    # User B cannot get User A's goal
    get_goal_b = client.get(f"/api/goals/{goal_a_id}", headers=auth_b)
    assert get_goal_b.status_code == 404

    # 4. User A creates a habit
    habit_a = client.post(
        "/api/habits",
        headers=auth_a,
        json={"name": "Private Habit for User A", "target": "Daily target"},
    ).json()
    habit_a_id = habit_a["id"]

    # User B cannot get User A's habit
    get_habit_b = client.get(f"/api/habits/{habit_a_id}", headers=auth_b)
    assert get_habit_b.status_code == 404


def test_backward_compatibility_default_unauthenticated_user():
    # Requests without Authorization Bearer header operate seamlessly using 'default_user'
    resp_tasks = client.get("/api/tasks")
    assert resp_tasks.status_code == 200
    assert isinstance(resp_tasks.json(), list)

    resp_goals = client.get("/api/goals")
    assert resp_goals.status_code == 200
    assert isinstance(resp_goals.json(), list)

    resp_habits = client.get("/api/habits")
    assert resp_habits.status_code == 200
    assert isinstance(resp_habits.json(), list)

    resp_rec = client.get("/api/recommendations")
    assert resp_rec.status_code == 200
    assert "total_active" in resp_rec.json()
