import uuid
from datetime import date, timedelta
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.timeblock import DailyTimeblock

def test_endpoints_inventory_coverage(client, db_session):
    today = date.today()

    # 1. Root & Health
    r1 = client.get("/")
    assert r1.status_code == 200
    assert r1.json()["status"] == "online"

    r2 = client.get("/api/health")
    assert r2.status_code == 200
    assert r2.json()["database"] == "connected"

    r3 = client.get("/api/dashboard/summary")
    assert r3.status_code == 200
    assert "metrics" in r3.json()

    # 2. Migration Status
    r_mig_status = client.get("/api/migration/status")
    assert r_mig_status.status_code == 200

    # 3. Tasks Endpoints (GET, POST, GET {id}, PUT {id}, PATCH complete, PATCH pending, DELETE)
    t_create = client.post("/api/tasks", json={
        "title": "Matrix Task Verification",
        "taskType": "Daily",
        "category": "Academic",
        "priority": "High",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": today.isoformat(),
    })
    assert t_create.status_code == 201
    tid = t_create.json()["id"]

    t_get = client.get(f"/api/tasks/{tid}")
    assert t_get.status_code == 200
    assert t_get.json()["title"] == "Matrix Task Verification"

    t_put = client.put(f"/api/tasks/{tid}", json={"priority": "Low"})
    assert t_put.status_code == 200
    assert t_put.json()["priority"] == "Low"

    t_comp = client.patch(f"/api/tasks/{tid}/complete")
    assert t_comp.status_code == 200
    assert t_comp.json()["status"] == "Completed"

    t_pend = client.patch(f"/api/tasks/{tid}/pending")
    assert t_pend.status_code == 200
    assert t_pend.json()["status"] == "Pending"

    # 404 on nonexistent task
    assert client.get("/api/tasks/nonexistent-task-id").status_code == 404
    assert client.put("/api/tasks/nonexistent-task-id", json={"title": "foo"}).status_code == 404

    # 4. Goals Endpoints (GET, POST, GET {id}, PUT {id}, PATCH progress, DELETE)
    g_create = client.post("/api/goals", json={
        "title": "Matrix Goal Verification",
        "goalType": "Long-Term",
        "category": "Career",
        "priority": "High",
        "status": "In Progress",
        "startDate": today.isoformat(),
        "targetDate": (today + timedelta(days=90)).isoformat(),
        "progress": 25,
    })
    assert g_create.status_code == 201
    gid = g_create.json()["id"]

    g_get = client.get(f"/api/goals/{gid}")
    assert g_get.status_code == 200
    assert g_get.json()["progress"] == 25

    g_put = client.put(f"/api/goals/{gid}", json={"priority": "Low"})
    assert g_put.status_code == 200

    g_patch = client.patch(f"/api/goals/{gid}/progress", json={"progress": 40})
    assert g_patch.status_code == 200
    assert g_patch.json()["progress"] == 40

    assert client.get("/api/goals/nonexistent-goal-id").status_code == 404

    # 5. Habits Endpoints (GET, POST, GET {id}, PUT {id}, POST toggle, DELETE)
    h_create = client.post("/api/habits", json={
        "name": "Matrix Habit Verification",
        "target": "20m",
        "category": "Health",
        "frequency": "Daily",
        "baseStreak": 2,
    })
    assert h_create.status_code == 201
    hid = h_create.json()["id"]

    h_get = client.get(f"/api/habits/{hid}")
    assert h_get.status_code == 200

    h_put = client.put(f"/api/habits/{hid}", json={"target": "25m"})
    assert h_put.status_code == 200

    h_tog = client.post(f"/api/habits/{hid}/toggle?date={today.isoformat()}&completed=true")
    assert h_tog.status_code == 200

    assert client.get("/api/habits/nonexistent-habit-id").status_code == 404

    # 6. Timeblocks Endpoints (GET, POST, GET {id}, PUT {id}, DELETE, analytics)
    tb_create = client.post("/api/timeblocks", json={
        "block_date": today.isoformat(),
        "title": "Matrix Timeblock",
        "time": "11:00 AM",
        "durationMinutes": 45,
        "category": "Reading",
        "status": "Pending",
        "isBreak": False,
        "taskId": tid,
    })
    assert tb_create.status_code == 201
    tbid = tb_create.json()["id"]

    tb_get = client.get(f"/api/timeblocks/{tbid}")
    assert tb_get.status_code == 200

    tb_put = client.put(f"/api/timeblocks/{tbid}", json={"status": "Completed"})
    assert tb_put.status_code == 200

    tb_pva = client.get("/api/timeblocks/analytics/planned-vs-actual")
    assert tb_pva.status_code == 200

    assert client.get("/api/timeblocks/nonexistent-tb-id").status_code == 404

    # 7. Behaviour Endpoints (all 9 endpoints)
    act_rec = client.post("/api/behaviour/activity", json={
        "event_type": "TASK_CREATED",
        "entity_type": "task",
        "entity_id": tid,
        "details": {"source": "test_matrix"},
    })
    assert act_rec.status_code in (200, 201)

    assert client.get("/api/behaviour/activities").status_code == 200
    assert client.get("/api/behaviour/summary").status_code == 200
    assert client.get("/api/behaviour/task-completion").status_code == 200
    assert client.get("/api/behaviour/postponements").status_code == 200
    assert client.get("/api/behaviour/time-estimation").status_code == 200
    assert client.get("/api/behaviour/productivity-hours").status_code == 200
    assert client.get("/api/behaviour/habit-consistency").status_code == 200
    assert client.get("/api/behaviour/daily-planning").status_code == 200

    # 8. Analytics Endpoints (all 7 endpoints)
    assert client.get("/api/analytics/overview").status_code == 200
    assert client.get("/api/analytics/daily").status_code == 200
    assert client.get("/api/analytics/weekly").status_code == 200
    assert client.get("/api/analytics/monthly").status_code == 200
    assert client.get("/api/analytics/time").status_code == 200
    assert client.get("/api/analytics/goals").status_code == 200
    assert client.get("/api/analytics/insights").status_code == 200

    # 9. Recommendations Endpoints (all 5 endpoints)
    rec_list = client.get("/api/recommendations")
    assert rec_list.status_code == 200

    rec_gen = client.post("/api/recommendations/generate")
    assert rec_gen.status_code == 200

    if rec_list.json()["items"]:
        rec_id = rec_list.json()["items"][0]["id"]
        assert client.post(f"/api/recommendations/{rec_id}/accept").status_code == 200
        assert client.post(f"/api/recommendations/{rec_id}/dismiss").status_code == 200
        assert client.post(f"/api/recommendations/{rec_id}/complete").status_code == 200

    assert client.post("/api/recommendations/nonexistent-rec-id/accept").status_code == 404

    # 10. Clean Deletions (testing DELETE on all entities)
    assert client.delete(f"/api/tasks/{tid}").status_code == 200
    assert client.delete(f"/api/tasks/{tid}").status_code == 404  # already deleted

    assert client.delete(f"/api/goals/{gid}").status_code == 200
    assert client.delete(f"/api/goals/{gid}").status_code == 404

    assert client.delete(f"/api/habits/{hid}").status_code == 200
    assert client.delete(f"/api/habits/{hid}").status_code == 404

    assert client.delete(f"/api/timeblocks/{tbid}").status_code == 200
    assert client.delete(f"/api/timeblocks/{tbid}").status_code == 404
