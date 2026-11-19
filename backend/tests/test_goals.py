from datetime import date, timedelta

def test_create_goal_and_response_fields(client):
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=60)).isoformat()

    payload = {
        "title": "Master Distributed Systems",
        "description": "Read DDIA and design consensus systems",
        "goalType": "Long-Term",
        "category": "Career",
        "priority": "High",
        "status": "In Progress",
        "startDate": today,
        "targetDate": future,
        "progress": 35,
        "keyMilestone": "Finish Paxos & Raft chapter",
    }

    res = client.post("/api/goals", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["id"].startswith("g-")
    assert data["title"] == "Master Distributed Systems"
    assert data["goalType"] == "Long-Term"
    assert data["type"] == "Long-Term"
    assert data["category"] == "Career"
    assert data["priority"] == "High"
    assert data["status"] == "In Progress"
    assert data["startDate"] == today
    assert data["targetDate"] == future
    assert data["progress"] == 35
    assert data["keyMilestone"] == "Finish Paxos & Raft chapter"
    assert data["daysRemaining"] == 60
    assert data["totalTasks"] == 0
    assert data["completedTasks"] == 0

def test_create_goal_with_custom_id(client):
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "id": "g-custom-100",
        "title": "Custom Goal",
        "targetDate": future,
        "startDate": today,
    }
    res = client.post("/api/goals", json=payload)
    assert res.status_code == 201
    assert res.json()["id"] == "g-custom-100"

def test_goal_progress_patch(client):
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=40)).isoformat()
    res = client.post("/api/goals", json={
        "title": "Progress Goal",
        "startDate": today,
        "targetDate": future,
        "progress": 20,
    })
    goal_id = res.json()["id"]

    patch_res = client.patch(f"/api/goals/{goal_id}/progress", json={"progress": 100})
    assert patch_res.status_code == 200
    assert patch_res.json()["progress"] == 100
    assert patch_res.json()["status"] == "Completed"

def test_goal_task_linking_and_safe_unlink_on_delete(client):
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=30)).isoformat()

    # Create goal
    g_res = client.post("/api/goals", json={
        "title": "Target Goal",
        "startDate": today,
        "targetDate": future,
    })
    goal_id = g_res.json()["id"]

    # Create linked task
    t_res = client.post("/api/tasks", json={
        "title": "Linked Task 1",
        "goalId": goal_id,
        "startDate": today,
        "dueDate": today,
        "status": "Completed",
    })
    task_id = t_res.json()["id"]

    # Goal should report 1 total and 1 completed task
    g_detail = client.get(f"/api/goals/{goal_id}").json()
    assert g_detail["totalTasks"] == 1
    assert g_detail["completedTasks"] == 1

    # Delete goal
    del_res = client.delete(f"/api/goals/{goal_id}")
    assert del_res.status_code == 200

    # Task should still exist, with goalId set to None
    t_detail = client.get(f"/api/tasks/{task_id}").json()
    assert t_detail["goalId"] is None
    assert t_detail["associatedGoalId"] is None
