import pytest

def test_create_habit_and_toggle_log(client):
    payload = {
        "id": "h-test-1",
        "name": "DSA Problem Solving",
        "target": "2 problems",
        "category": "Coding",
        "frequency": "Daily",
        "baseStreak": 5,
        "completedDates": {
            "2026-11-16": True,
            "2026-11-17": True,
        }
    }
    # Create
    resp = client.post("/api/habits", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "h-test-1"
    assert data["name"] == "DSA Problem Solving"
    assert data["baseStreak"] == 5
    assert data["completedDates"]["2026-11-16"] is True
    assert data["completedDates"]["2026-11-17"] is True

    # List
    list_resp = client.get("/api/habits")
    assert list_resp.status_code == 200
    habits = list_resp.json()
    assert len(habits) == 1

    # Toggle a new date (2026-11-18)
    toggle_resp = client.post("/api/habits/h-test-1/toggle?date=2026-11-18")
    assert toggle_resp.status_code == 200
    toggle_data = toggle_resp.json()
    assert toggle_data["completedDates"]["2026-11-18"] is True

    # Toggle off (untick)
    untoggle_resp = client.post("/api/habits/h-test-1/toggle?date=2026-11-18")
    assert untoggle_resp.status_code == 200
    assert "2026-11-18" not in untoggle_resp.json()["completedDates"]

def test_habit_historical_logs_retention_across_weeks(client):
    """
    Ensure habit logs are preserved across weekly boundaries and never deleted.
    """
    payload = {
        "id": "h-history",
        "name": "Deep Work / Focus",
        "baseStreak": 12,
        "completedDates": {
            "2026-10-01": True,
            "2026-10-02": True,
            "2026-11-01": True,
        }
    }
    client.post("/api/habits", json=payload)
    
    # Add another past log explicitly
    resp = client.post("/api/habits/h-history/toggle?date=2026-09-15&completed=true")
    assert resp.status_code == 200
    dates = resp.json()["completedDates"]
    assert "2026-09-15" in dates
    assert "2026-10-01" in dates
    assert "2026-10-02" in dates
    assert "2026-11-01" in dates
    assert len(resp.json()["logs"]) == 4

def test_delete_habit_cascades_logs(client, db_session):
    from backend.app.models.habit_log import HabitLog
    
    payload = {
        "id": "h-delete",
        "name": "Temporary Habit",
        "completedDates": {"2026-11-18": True}
    }
    client.post("/api/habits", json=payload)
    assert db_session.query(HabitLog).filter(HabitLog.habit_id == "h-delete").count() == 1

    del_resp = client.delete("/api/habits/h-delete")
    assert del_resp.status_code == 200
    assert db_session.query(HabitLog).filter(HabitLog.habit_id == "h-delete").count() == 0
