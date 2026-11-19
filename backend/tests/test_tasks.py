from datetime import date, timedelta

def test_create_task_and_response_fields(client):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    payload = {
        "title": "Build FastAPI Test Suite",
        "description": "Comprehensive test suite for Phase 2",
        "taskType": "Daily",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": today,
        "dueDate": tomorrow,
    }

    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["id"].startswith("t-")
    assert data["title"] == "Build FastAPI Test Suite"
    assert data["taskType"] == "Daily"
    assert data["category"] == "Coding"
    assert data["priority"] == "High"
    assert data["status"] == "Pending"
    assert data["startDate"] == today
    assert data["dueDate"] == tomorrow
    assert data["isToday"] is True
    assert data["isOverdue"] is False
    assert data["completedAt"] is None

def test_create_task_with_custom_id(client):
    today = date.today().isoformat()
    payload = {
        "id": "t-legacy-999",
        "title": "Legacy Migrated Task",
        "taskType": "Short-Term",
        "category": "Academic",
        "priority": "Medium",
        "status": "In Progress",
        "startDate": today,
        "dueDate": today,
    }
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201
    assert res.json()["id"] == "t-legacy-999"

def test_list_tasks_and_filters(client):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    client.post("/api/tasks", json={
        "title": "Task 1",
        "taskType": "Daily",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": today,
        "dueDate": today,
    })
    client.post("/api/tasks", json={
        "title": "Task 2",
        "taskType": "Long-Term",
        "category": "Reading",
        "priority": "Low",
        "status": "Completed",
        "startDate": yesterday,
        "dueDate": yesterday,
    })

    # List all
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert len(res.json()) == 2

    # Filter by priority
    res = client.get("/api/tasks?priority=High")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["title"] == "Task 1"

    # Filter by status
    res = client.get("/api/tasks?status=Completed")
    assert len(res.json()) == 1
    assert res.json()[0]["title"] == "Task 2"

    # Filter by search
    res = client.get("/api/tasks?search=Task 2")
    assert len(res.json()) == 1

def test_get_and_update_task(client):
    today = date.today().isoformat()
    create_res = client.post("/api/tasks", json={
        "title": "Original Title",
        "taskType": "Daily",
        "category": "Health",
        "priority": "Medium",
        "status": "Pending",
        "startDate": today,
        "dueDate": today,
    })
    task_id = create_res.json()["id"]

    # Fetch
    res = client.get(f"/api/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Original Title"

    # Update
    update_res = client.put(f"/api/tasks/{task_id}", json={
        "title": "Updated Title",
        "priority": "High",
    })
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Title"
    assert update_res.json()["priority"] == "High"

def test_mark_task_complete_and_pending(client):
    today = date.today().isoformat()
    create_res = client.post("/api/tasks", json={
        "title": "Toggle Test Task",
        "taskType": "Daily",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": today,
        "dueDate": today,
    })
    task_id = create_res.json()["id"]

    # Complete
    res = client.patch(f"/api/tasks/{task_id}/complete")
    assert res.status_code == 200
    assert res.json()["status"] == "Completed"
    assert res.json()["completedAt"] is not None

    # Revert to pending
    res = client.patch(f"/api/tasks/{task_id}/pending")
    assert res.status_code == 200
    assert res.json()["status"] == "Pending"
    assert res.json()["completedAt"] is None

def test_delete_task(client):
    today = date.today().isoformat()
    create_res = client.post("/api/tasks", json={
        "title": "To Delete",
        "startDate": today,
        "dueDate": today,
    })
    task_id = create_res.json()["id"]

    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200

    # Verify not found
    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 404

def test_task_validation_errors(client):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Invalid dates: due date before start date
    res = client.post("/api/tasks", json={
        "title": "Invalid Date Task",
        "startDate": today,
        "dueDate": yesterday,
    })
    assert res.status_code == 422

    # Invalid priority
    res = client.post("/api/tasks", json={
        "title": "Invalid Priority",
        "priority": "UltraHigh",
        "startDate": today,
        "dueDate": today,
    })
    assert res.status_code == 422
