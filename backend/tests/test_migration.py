from datetime import date, timedelta

def test_migration_import_lifecycle(client):
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=45)).isoformat()

    mock_goals = [
        {
            "id": "g-1",
            "title": "Solve 100 DSA Problems on LeetCode",
            "description": "Master core dynamic programming, graphs, and tree patterns",
            "type": "Short-Term",
            "category": "Coding",
            "priority": "High",
            "status": "In Progress",
            "startDate": today,
            "targetDate": future,
            "progress": 74,
            "keyMilestone": "Complete Dynamic Programming sheet",
        },
        {
            "id": "g-2",
            "title": "Finish Stanford CS229",
            "type": "Short-Term",
            "category": "Academic",
            "priority": "High",
            "status": "In Progress",
            "startDate": today,
            "targetDate": future,
            "progress": 55,
        },
    ]

    mock_tasks = [
        {
            "id": "t-1",
            "title": "Implement NIYANTRA Dashboard Layout",
            "description": "Design 3-part layout",
            "taskType": "Short-Term",
            "category": "Coding",
            "priority": "High",
            "status": "In Progress",
            "startDate": today,
            "dueDate": today,
            "associatedGoalId": "g-1",
        },
        {
            "id": "t-2",
            "title": "Linear Algebra Problem Set 3",
            "taskType": "Daily",
            "category": "Academic",
            "priority": "Medium",
            "status": "Completed",
            "startDate": today,
            "dueDate": today,
            "associatedGoalId": "g-2",
        },
    ]

    # 1. First Import
    payload = {"goals": mock_goals, "tasks": mock_tasks, "overwrite": False}
    res = client.post("/api/migration/import", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["status"] == "success"
    assert data["goalsImported"] == 2
    assert data["tasksImported"] == 2
    assert data["goalsSkipped"] == 0
    assert data["tasksSkipped"] == 0

    # Verify task-goal relationship is preserved
    t1 = client.get("/api/tasks/t-1").json()
    assert t1["id"] == "t-1"
    assert t1["goalId"] == "g-1"
    assert t1["associatedGoalTitle"] == "Solve 100 DSA Problems on LeetCode"

    # 2. Second Import (Idempotency test without overwrite)
    res2 = client.post("/api/migration/import", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["goalsImported"] == 0
    assert data2["tasksImported"] == 0
    assert data2["goalsSkipped"] == 2
    assert data2["tasksSkipped"] == 2

    # Verify total count in status endpoint
    status_res = client.get("/api/migration/status")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["totalTasksInDb"] == 2
    assert s_data["totalGoalsInDb"] == 2

    # 3. Third Import with Overwrite
    mock_goals[0]["title"] = "Updated Goal Title via Overwrite"
    res3 = client.post("/api/migration/import", json={"goals": mock_goals, "tasks": mock_tasks, "overwrite": True})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["goalsUpdated"] == 2
    assert data3["tasksUpdated"] == 2

    # Verify updated title
    g1 = client.get("/api/goals/g-1").json()
    assert g1["title"] == "Updated Goal Title via Overwrite"

def test_migration_habits_and_timeblocks_idempotency(client):
    habits_payload = [
        {
            "id": "h-mig-1",
            "name": "DSA LeetCode",
            "target": "2 problems",
            "category": "Coding",
            "baseStreak": 10,
            "completedDates": {
                "2026-11-16": True,
                "2026-11-17": True,
            }
        }
    ]

    timeblocks_payload = {
        "2026-11-18": [
            {
                "id": "blk-mig-1",
                "title": "Deep Work Morning",
                "time": "09:00 AM",
                "durationMinutes": 90,
                "actualDurationMinutes": 80,
                "category": "Coding",
                "status": "Completed",
            }
        ]
    }

    # 1. First import
    res1 = client.post("/api/migration/import", json={
        "habits": habits_payload,
        "timeblocks": timeblocks_payload,
        "overwrite": False,
    })
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["habitsImported"] == 1
    assert d1["habitLogsImported"] == 2
    assert d1["timeblocksImported"] == 1

    # Verify status
    stat = client.get("/api/migration/status").json()
    assert stat["totalHabitsInDb"] == 1
    assert stat["totalHabitLogsInDb"] == 2
    assert stat["totalTimeblocksInDb"] == 1

    # 2. Second import (idempotent skip)
    res2 = client.post("/api/migration/import", json={
        "habits": habits_payload,
        "timeblocks": timeblocks_payload,
        "overwrite": False,
    })
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["habitsImported"] == 0
    assert d2["habitsSkipped"] == 1
    assert d2["timeblocksImported"] == 0
    assert d2["timeblocksSkipped"] == 1

