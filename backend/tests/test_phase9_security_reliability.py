import os
import time
import uuid
import threading
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from backend.app.main import app
from backend.app.database import SessionLocal, get_db, engine
from backend.app.core.config import settings
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.services import backup_service, recommendation_service

client = TestClient(app)

def test_system_info_endpoint():
    """Verify system info endpoint reports runtime configuration and WAL journal mode."""
    response = client.get("/api/system/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert "journal_mode" in data
    assert "table_counts" in data
    assert "tasks" in data["table_counts"]

def test_system_integrity_check_endpoint():
    """Verify SQLite database integrity check reports healthy with 0 FK violations."""
    response = client.get("/api/system/integrity")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["integrity_check"] == "ok"
    assert data["foreign_key_violations"] == 0

def test_backup_and_restore_cycle(tmp_path):
    """
    Test online backup creation, verification, listing, and restoration with safety snapshots.
    """
    # 1. Trigger online backup
    resp = client.post("/api/system/backup?label=test_suite")
    assert resp.status_code == 200
    backup_meta = resp.json()
    assert backup_meta["status"] == "success"
    assert len(backup_meta["sha256"]) == 64
    assert backup_meta["size_bytes"] > 0
    assert backup_meta["integrity"] == "ok"
    assert backup_meta["foreign_key_violations"] == 0
    backup_filename = backup_meta["filename"]

    # 2. List backups and confirm presence
    list_resp = client.get("/api/system/backups")
    assert list_resp.status_code == 200
    backups = list_resp.json()
    assert any(b["filename"] == backup_filename for b in backups)

    # 3. Restore from backup
    restore_resp = client.post("/api/system/restore", json={"backup_filename": backup_filename})
    assert restore_resp.status_code == 200
    restore_data = restore_resp.json()
    assert restore_data["status"] == "success"
    assert restore_data["restored_from"] == backup_filename
    assert restore_data["integrity"] == "ok"
    assert restore_data["foreign_key_violations"] == 0
    assert restore_data["safety_snapshot"] is not None

def test_sql_injection_resistance():
    """
    Ensure SQL injection payloads in user input are parameterized and treated as literal text.
    """
    db = SessionLocal()
    unique_title = f"Test SQL Injection ' OR '1'='1' -- {uuid.uuid4().hex[:6]}"
    malicious_desc = "'; DROP TABLE tasks; -- Robert'); DROP TABLE students;--"
    
    try:
        new_task = Task(
            id=f"sqli_{uuid.uuid4().hex[:12]}",
            title=unique_title,
            description=malicious_desc,
            task_type="One-Time",
            category="Coding",
            priority="High",
            status="Pending",
            start_date=date.today(),
            due_date=date.today() + timedelta(days=2),
        )
        db.add(new_task)
        db.commit()

        # Query back using normal ORM
        fetched = db.query(Task).filter(Task.title == unique_title).first()
        assert fetched is not None
        assert fetched.description == malicious_desc

        # Verify tables still exist
        table_check = db.execute(text("SELECT count(*) FROM tasks")).scalar()
        assert table_check > 0
    finally:
        # Cleanup
        db.query(Task).filter(Task.title == unique_title).delete()
        db.commit()
        db.close()

def test_xss_input_sanitization():
    """
    Ensure XSS script tags and event handlers are stored harmlessly as literal strings.
    """
    db = SessionLocal()
    xss_payload = "<script>alert('XSS Attack');</script><img src=x onerror=alert(1)>"
    t_id = f"xss_{uuid.uuid4().hex[:12]}"
    
    try:
        task = Task(
            id=t_id,
            title=f"XSS Test {xss_payload}",
            description=xss_payload,
            task_type="Daily",
            category="Personal",
            priority="Medium",
            status="Pending",
            start_date=date.today(),
            due_date=date.today(),
        )
        db.add(task)
        db.commit()

        stored = db.query(Task).filter(Task.id == t_id).first()
        assert stored is not None
        assert stored.description == xss_payload
    finally:
        db.query(Task).filter(Task.id == t_id).delete()
        db.commit()
        db.close()

def test_foreign_key_constraint_enforcement():
    """
    Verify foreign keys are enforced by SQLite engine (raising IntegrityError on invalid FK).
    """
    db = SessionLocal()
    invalid_task = Task(
        id=f"fk_test_{uuid.uuid4().hex[:12]}",
        title="Invalid FK Task",
        task_type="Daily",
        category="Personal",
        priority="Low",
        status="Pending",
        start_date=date.today(),
        due_date=date.today(),
        goal_id="completely-invalid-nonexistent-goal-id-9999",
    )
    db.add(invalid_task)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()

def test_optional_api_key_authentication(monkeypatch):
    """
    Verify dual-mode authentication:
    - Default (API_KEY unset): Transparent local desktop access.
    - Protected (API_KEY set): 401 on missing/wrong key, 200 with X-API-Key or Bearer token.
    """
    # 1. Single-user desktop mode (default)
    monkeypatch.setattr(settings, "API_KEY", None)
    resp = client.get("/api/system/info")
    assert resp.status_code == 200

    # 2. Configured protected mode
    test_key = "secure-ny-prod-token-2026"
    monkeypatch.setattr(settings, "API_KEY", test_key)

    # Missing auth -> 401
    resp_unauth = client.get("/api/system/info")
    assert resp_unauth.status_code == 401

    # Invalid auth -> 401
    resp_wrong = client.get("/api/system/info", headers={"X-API-Key": "wrong-key"})
    assert resp_wrong.status_code == 401

    # Valid X-API-Key -> 200
    resp_valid_header = client.get("/api/system/info", headers={"X-API-Key": test_key})
    assert resp_valid_header.status_code == 200

    # Valid Bearer token -> 200
    resp_valid_bearer = client.get("/api/system/info", headers={"Authorization": f"Bearer {test_key}"})
    assert resp_valid_bearer.status_code == 200

def test_concurrent_writes_wal_mode():
    """
    Verify SQLite WAL mode prevents 'database is locked' errors under concurrent writes.
    """
    errors = []
    created_ids = []

    def worker(worker_num: int):
        db = SessionLocal()
        try:
            for i in range(5):
                tid = f"cw_{worker_num}_{i}_{uuid.uuid4().hex[:8]}"
                task = Task(
                    id=tid,
                    title=f"Concurrent Worker {worker_num} Item {i}",
                    task_type="Daily",
                    category="Coding",
                    priority="Medium",
                    status="Pending",
                    start_date=date.today(),
                    due_date=date.today(),
                )
                db.add(task)
                db.commit()
                created_ids.append(tid)
                time.sleep(0.01)
        except Exception as exc:
            errors.append(f"Worker {worker_num} failed: {exc}")
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Cleanup created tasks
    cleanup_db = SessionLocal()
    try:
        cleanup_db.query(Task).filter(Task.id.in_(created_ids)).delete(synchronize_session=False)
        cleanup_db.commit()
    finally:
        cleanup_db.close()

    assert len(errors) == 0, f"Concurrent write errors encountered: {errors}"
    assert len(created_ids) == 20

def test_request_auditing_middleware_header():
    """Verify all HTTP responses contain X-Response-Time-Ms header."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "x-response-time-ms" in resp.headers
    duration = float(resp.headers["x-response-time-ms"])
    assert duration >= 0.0

def test_cors_security_configuration():
    """
    Verify CORS configuration properly responds with configured origin and disallows wildcard with credentials.
    """
    resp = client.options(
        "/api/tasks",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-credentials") == "true"
