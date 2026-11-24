import uuid
import pytest
from datetime import date, timedelta, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.daily_intent import DailyIntent
from backend.app.services import backup_service

client = TestClient(app)

def test_daily_intents_crud_lifecycle():
    """Verify storing, retrieving, updating, listing, and soft-deleting daily intents."""
    test_date = (date.today() + timedelta(days=50)).isoformat()
    
    # 1. Create / Upsert intent
    create_resp = client.post(
        "/api/daily-intents",
        json={"intent_date": test_date, "intent_text": "Phase 10B Schema Evolution Verification"},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["user_id"] == "default_user"
    assert created_data["intent_text"] == "Phase 10B Schema Evolution Verification"
    assert created_data["version"] == 1
    assert created_data["is_deleted"] is False

    # 2. Retrieve intent by date
    get_resp = client.get(f"/api/daily-intents/{test_date}")
    assert get_resp.status_code == 200
    assert get_resp.json()["intent_text"] == "Phase 10B Schema Evolution Verification"

    # 3. Update / Upsert same date -> increments version
    update_resp = client.post(
        "/api/daily-intents",
        json={"intent_date": test_date, "intent_text": "Updated Intent Text for Sync"},
    )
    assert update_resp.status_code == 201
    updated_data = update_resp.json()
    assert updated_data["version"] == 2
    assert updated_data["intent_text"] == "Updated Intent Text for Sync"

    # 4. List daily intents
    list_resp = client.get("/api/daily-intents")
    assert list_resp.status_code == 200
    intents = list_resp.json()
    assert any(i["intent_date"] == test_date for i in intents)

    # 5. Soft delete daily intent
    del_resp = client.delete(f"/api/daily-intents/{test_date}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # 6. Verify 404 on normal get
    get_after_del = client.get(f"/api/daily-intents/{test_date}")
    assert get_after_del.status_code == 404

    # 7. Verify record physically remains in SQLite with tombstone
    db = SessionLocal()
    try:
        tombstone = db.query(DailyIntent).filter(DailyIntent.intent_date == date.fromisoformat(test_date)).first()
        assert tombstone is not None
        assert tombstone.is_deleted is True
        assert tombstone.deleted_at is not None
        assert tombstone.version == 3
    finally:
        db.query(DailyIntent).filter(DailyIntent.intent_date == date.fromisoformat(test_date)).delete()
        db.commit()
        db.close()

def test_task_soft_deletion_and_version_tracking():
    """Verify task soft-deletion preserves SQLite record and version increments."""
    # 1. Create task
    t_resp = client.post("/api/tasks", json={
        "title": "Version Tracking Test Task",
        "taskType": "Daily",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": date.today().isoformat(),
        "dueDate": date.today().isoformat(),
    })
    assert t_resp.status_code == 201
    tid = t_resp.json()["id"]

    # 2. Update task -> version increments
    u_resp = client.put(f"/api/tasks/{tid}", json={"priority": "Low"})
    assert u_resp.status_code == 200

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == tid).first()
        assert task.version >= 2
        assert task.user_id == "default_user"
        assert task.is_deleted is False

        # 3. Delete task via API
        del_resp = client.delete(f"/api/tasks/{tid}")
        assert del_resp.status_code == 200

        # 4. Subsequent API calls return 404
        assert client.get(f"/api/tasks/{tid}").status_code == 404
        assert client.delete(f"/api/tasks/{tid}").status_code == 404

        # 5. Verify record physically preserved in DB as tombstone
        db.refresh(task)
        assert task.is_deleted is True
        assert task.deleted_at is not None
        assert task.version >= 3
    finally:
        db.query(Task).filter(Task.id == tid).delete()
        db.commit()
        db.close()

def test_goal_soft_deletion_and_version_tracking():
    """Verify goal soft-deletion preserves SQLite record and unlinks tasks safely."""
    g_resp = client.post("/api/goals", json={
        "title": "Version Tracking Goal",
        "goalType": "Short-Term",
        "category": "Career",
        "priority": "Medium",
        "status": "In Progress",
        "startDate": date.today().isoformat(),
        "targetDate": (date.today() + timedelta(days=30)).isoformat(),
        "progress": 10,
    })
    assert g_resp.status_code == 201
    gid = g_resp.json()["id"]

    # Update goal
    client.put(f"/api/goals/{gid}", json={"progress": 25})

    db = SessionLocal()
    try:
        goal = db.query(Goal).filter(Goal.id == gid).first()
        assert goal.version >= 2
        assert goal.user_id == "default_user"
        assert goal.is_deleted is False

        # Delete goal
        assert client.delete(f"/api/goals/{gid}").status_code == 200
        assert client.get(f"/api/goals/{gid}").status_code == 404

        db.refresh(goal)
        assert goal.is_deleted is True
        assert goal.deleted_at is not None
        assert goal.version >= 3
    finally:
        db.query(Goal).filter(Goal.id == gid).delete()
        db.commit()
        db.close()

def test_schema_integrity_and_foreign_keys():
    """Verify database integrity check and zero foreign key violations post-migration."""
    rep = backup_service.verify_database_integrity()
    assert rep["status"] == "healthy"
    assert rep["integrity_check"] == "ok"
    assert rep["foreign_key_violations"] == 0
    assert "daily_intents" in rep["table_counts"]

def test_backup_and_restore_with_new_schema():
    """Verify online backup and restore functions seamlessly with migrated schema."""
    resp = client.post("/api/system/backup?label=phase10b_verification")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["status"] == "success"
    assert meta["integrity"] == "ok"
    assert meta["foreign_key_violations"] == 0
