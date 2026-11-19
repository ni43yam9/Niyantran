from datetime import date, timedelta

def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data

def test_dashboard_summary_metrics(client):
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=2)).isoformat()
    future = (date.today() + timedelta(days=10)).isoformat()

    # 1. Overdue task
    client.post("/api/tasks", json={
        "title": "Overdue Task",
        "priority": "High",
        "status": "Pending",
        "startDate": yesterday,
        "dueDate": yesterday,
    })

    # 2. Due today task
    client.post("/api/tasks", json={
        "title": "Due Today Task",
        "priority": "High",
        "status": "In Progress",
        "startDate": today,
        "dueDate": today,
    })

    # 3. Completed task
    client.post("/api/tasks", json={
        "title": "Completed Task",
        "priority": "Medium",
        "status": "Completed",
        "startDate": yesterday,
        "dueDate": today,
    })

    # 4. Active goal
    client.post("/api/goals", json={
        "title": "Active Goal",
        "startDate": today,
        "targetDate": future,
        "status": "In Progress",
        "progress": 50,
    })

    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    metrics = data["metrics"]

    assert metrics["totalTasks"] == 3
    assert metrics["completedTasks"] == 1
    assert metrics["pendingTasks"] == 2
    assert metrics["activeGoals"] == 1
    assert metrics["completionRate"] == 33  # 1/3 * 100
    assert metrics["overdueCount"] == 1
    assert metrics["dueTodayCount"] == 1

    assert len(data["tasksDueToday"]) >= 1
    assert len(data["topPriorities"]) >= 1
    assert len(data["categoryDistribution"]) >= 1
