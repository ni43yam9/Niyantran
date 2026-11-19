import pytest

def test_create_and_list_timeblocks_by_date(client):
    block_payload = {
        "id": "blk_test_1",
        "date": "2026-11-18",
        "title": "Stanford CS229 SVM Derivations",
        "time": "10:30 AM",
        "durationMinutes": 90,
        "actualDurationMinutes": 85,
        "category": "Academic",
        "status": "Completed",
        "isBreak": False,
    }
    create_resp = client.post("/api/timeblocks", json=block_payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] == "blk_test_1"
    assert data["date"] == "2026-11-18"
    assert data["durationMinutes"] == 90
    assert data["actualDurationMinutes"] == 85

    # Filter by date
    list_resp = client.get("/api/timeblocks?date=2026-11-18")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Filter by different date
    empty_resp = client.get("/api/timeblocks?date=2026-11-19")
    assert empty_resp.status_code == 200
    assert len(empty_resp.json()) == 0

def test_planned_vs_actual_analytics(client):
    # Insert multiple blocks across categories
    client.post("/api/timeblocks", json={
        "id": "blk-a1",
        "date": "2026-11-18",
        "title": "DSA Practice",
        "time": "08:30 AM",
        "durationMinutes": 120, # Planned 2.0 hrs
        "actualDurationMinutes": 90, # Actual 1.5 hrs
        "category": "Coding",
        "status": "Completed",
    })
    client.post("/api/timeblocks", json={
        "id": "blk-a2",
        "date": "2026-11-18",
        "title": "Project Architecture",
        "time": "02:00 PM",
        "durationMinutes": 60, # Planned 1.0 hr
        "actualDurationMinutes": 120, # Actual 2.0 hrs (Underestimated!)
        "category": "Coding",
        "status": "Completed",
    })
    client.post("/api/timeblocks", json={
        "id": "blk-a3",
        "date": "2026-11-18",
        "title": "Lunch Break",
        "time": "01:00 PM",
        "durationMinutes": 45,
        "category": "Personal",
        "isBreak": True, # Should be excluded from focus analytics
    })

    resp = client.get("/api/timeblocks/analytics/planned-vs-actual")
    assert resp.status_code == 200
    analytics = resp.json()
    assert len(analytics) == 1
    coding_stat = analytics[0]
    assert coding_stat["category"] == "Coding"
    assert coding_stat["plannedHours"] == 3.0 # (120 + 60) / 60
    assert coding_stat["actualHours"] == 3.5 # (90 + 120) / 60
    assert coding_stat["varianceHours"] == 0.5
    assert coding_stat["underestimated"] is True

def test_timeblock_task_linking_and_safe_unlink(client):
    # 1. Create task
    t_resp = client.post("/api/tasks", json={
        "id": "t-link-1",
        "title": "Finish Assignment",
        "startDate": "2026-11-18",
        "dueDate": "2026-11-18",
    })
    assert t_resp.status_code == 201

    # 2. Create timeblock linked to task
    b_resp = client.post("/api/timeblocks", json={
        "id": "blk-linked",
        "date": "2026-11-18",
        "title": "Work on Assignment",
        "time": "09:00 AM",
        "durationMinutes": 60,
        "taskId": "t-link-1",
    })
    assert b_resp.status_code == 201
    assert b_resp.json()["taskId"] == "t-link-1"

    # 3. Delete task
    del_t = client.delete("/api/tasks/t-link-1")
    assert del_t.status_code == 200

    # 4. Verify timeblock still exists with taskId set to NULL
    b_check = client.get("/api/timeblocks/blk-linked")
    assert b_check.status_code == 200
    assert b_check.json()["taskId"] is None
