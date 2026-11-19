import uuid
from datetime import date, timedelta, datetime, timezone
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog

# ===========================================================================
# WORKFLOW A: Task Lifecycle
# Create task -> Edit task -> Add to daily plan -> Complete task ->
# Verify dashboard -> Verify analytics -> Verify behaviour history
# ===========================================================================
def test_workflow_a_task_lifecycle(client, db_session):
    today = date.today()

    # 1. Create task
    task_payload = {
        "title": "Audit Workflow Task",
        "description": "Testing full end-to-end task lifecycle",
        "taskType": "Daily",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": (today + timedelta(days=1)).isoformat(),
    }
    create_resp = client.post("/api/tasks", json=task_payload)
    assert create_resp.status_code == 201
    created_task = create_resp.json()
    task_id = created_task["id"]
    assert created_task["title"] == "Audit Workflow Task"
    assert created_task["status"] == "Pending"

    # 2. Edit task
    edit_payload = {
        "title": "Audit Workflow Task - Updated Title",
        "priority": "Medium",
    }
    update_resp = client.put(f"/api/tasks/{task_id}", json=edit_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Audit Workflow Task - Updated Title"
    assert update_resp.json()["priority"] == "Medium"

    # 3. Add to daily plan (create timeblock)
    tb_payload = {
        "block_date": today.isoformat(),
        "title": "Audit Execution Block",
        "time": "10:00 AM",
        "duration_minutes": 90,
        "actual_duration_minutes": 85,
        "category": "Coding",
        "status": "Pending",
        "is_break": False,
        "task_id": task_id,
    }
    tb_resp = client.post("/api/timeblocks", json=tb_payload)
    assert tb_resp.status_code == 201
    tb_data = tb_resp.json()
    assert tb_data.get("taskId") == task_id or tb_data.get("task_id") == task_id

    # 4. Complete task
    complete_resp = client.patch(f"/api/tasks/{task_id}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "Completed"
    assert complete_resp.json()["completedAt"] is not None

    # 5. Verify dashboard summary
    dash_resp = client.get("/api/dashboard/summary")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    metrics = dash_data.get("metrics", {})
    total_t = metrics.get("totalTasks", metrics.get("total_tasks", 0))
    comp_t = metrics.get("completedTasks", metrics.get("completed_tasks", 0))
    assert total_t >= 1
    assert comp_t >= 1

    # 6. Verify analytics overview
    analytics_resp = client.get("/api/analytics/overview")
    assert analytics_resp.status_code == 200
    overview = analytics_resp.json()
    assert overview["total_completed_tasks"] >= 1

    # 7. Verify behaviour activities recorded
    act_resp = client.get("/api/behaviour/activities")
    assert act_resp.status_code == 200
    activities = act_resp.json()
    event_types = [a["event_type"] for a in activities]
    assert "TASK_CREATED" in event_types
    assert "TASK_COMPLETED" in event_types
    assert "DAILY_PLAN_CREATED" in event_types


# ===========================================================================
# WORKFLOW B: Goal Lifecycle
# Create goal -> Add associated tasks -> Complete tasks ->
# Verify goal progress -> Verify goal analytics
# ===========================================================================
def test_workflow_b_goal_lifecycle(client, db_session):
    today = date.today()

    # 1. Create goal
    goal_payload = {
        "title": "Master Backend Architecture",
        "description": "Enterprise-level FastAPI & SQLAlchemy proficiency",
        "goalType": "Short-Term",
        "category": "Coding",
        "priority": "High",
        "status": "In Progress",
        "startDate": today.isoformat(),
        "targetDate": (today + timedelta(days=60)).isoformat(),
        "progress": 0,
        "keyMilestone": "Pass all 40+ automated tests",
    }
    g_resp = client.post("/api/goals", json=goal_payload)
    assert g_resp.status_code == 201
    goal_id = g_resp.json()["id"]

    # 2. Add two associated tasks
    t1_payload = {
        "title": "Goal Deliverable 1",
        "taskType": "Short-Term",
        "category": "Coding",
        "priority": "High",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": (today + timedelta(days=10)).isoformat(),
        "goalId": goal_id,
    }
    t2_payload = {
        "title": "Goal Deliverable 2",
        "taskType": "Short-Term",
        "category": "Coding",
        "priority": "Medium",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": (today + timedelta(days=20)).isoformat(),
        "goalId": goal_id,
    }
    t1_resp = client.post("/api/tasks", json=t1_payload)
    t2_resp = client.post("/api/tasks", json=t2_payload)
    assert t1_resp.status_code == 201
    assert t2_resp.status_code == 201
    t1_id = t1_resp.json()["id"]

    # 3. Complete 1 of the 2 tasks
    client.patch(f"/api/tasks/{t1_id}/complete")

    # 4. Update goal progress
    patch_resp = client.patch(f"/api/goals/{goal_id}/progress", json={"progress": 50})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["progress"] == 50

    # 5. Verify goal analytics
    g_analytics = client.get("/api/analytics/goals")
    assert g_analytics.status_code == 200
    data = g_analytics.json()
    assert data["active_goals"] >= 1
    found_g = next((g for g in data["goals"] if g["goal_id"] == goal_id), None)
    assert found_g is not None
    assert found_g["total_tasks"] == 2
    assert found_g["completed_tasks"] == 1
    assert found_g["progress"] == 50


# ===========================================================================
# WORKFLOW C: Habit Lifecycle
# Create habit -> Complete habit for multiple dates -> Verify streak ->
# Miss a scheduled day -> Verify consistency
# ===========================================================================
def test_workflow_c_habit_lifecycle(client, db_session):
    today = date.today()
    d1 = today - timedelta(days=2)
    d2 = today - timedelta(days=1)
    d3 = today

    # 1. Create habit
    habit_payload = {
        "name": "Evening Code Review",
        "target": "30 mins",
        "category": "Coding",
        "frequency": "Daily",
        "base_streak": 0,
    }
    h_resp = client.post("/api/habits", json=habit_payload)
    assert h_resp.status_code == 201
    habit_id = h_resp.json()["id"]

    # 2. Toggle completion for d1, d2, d3 using date query param
    for d in [d1, d2, d3]:
        t_resp = client.post(f"/api/habits/{habit_id}/toggle?date={d.isoformat()}&completed=true")
        assert t_resp.status_code == 200

    # Verify 3 dates in completed_dates
    get_h = client.get(f"/api/habits/{habit_id}")
    assert get_h.status_code == 200
    h_data = get_h.json()
    dates = h_data.get("completedDates") or h_data.get("completed_dates", {})
    assert dates.get(d1.isoformat()) is True
    assert dates.get(d2.isoformat()) is True
    assert dates.get(d3.isoformat()) is True

    # 3. Toggle d3 to false (missed day)
    t_miss = client.post(f"/api/habits/{habit_id}/toggle?date={d3.isoformat()}&completed=false")
    assert t_miss.status_code == 200
    dates_after = t_miss.json().get("completedDates") or t_miss.json().get("completed_dates", {})
    assert d3.isoformat() not in dates_after or dates_after.get(d3.isoformat()) is False

    # 4. Verify habit consistency analytics calculation does not error
    h_cons = client.get("/api/behaviour/habit-consistency")
    assert h_cons.status_code == 200
    assert "habit_summaries" in h_cons.json()


# ===========================================================================
# WORKFLOW D: Postponement Tracking
# Create task -> Postpone task -> Reschedule task -> Complete task ->
# Verify activity history -> Verify postponement analytics
# ===========================================================================
def test_workflow_d_postponement_tracking(client, db_session):
    today = date.today()

    # 1. Create task scheduled for today
    task = Task(
        id=f"t_pp_{uuid.uuid4().hex[:8]}",
        title="Delayed Code Refactoring",
        task_type="Daily",
        category="Coding",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # 2. Postpone task to tomorrow
    tomorrow = today + timedelta(days=1)
    p1 = client.put(f"/api/tasks/{task.id}", json={"dueDate": tomorrow.isoformat()})
    assert p1.status_code == 200

    # 3. Reschedule task again to day after tomorrow
    day_after = today + timedelta(days=2)
    p2 = client.put(f"/api/tasks/{task.id}", json={"dueDate": day_after.isoformat()})
    assert p2.status_code == 200

    # 4. Complete task
    p3 = client.patch(f"/api/tasks/{task.id}/complete")
    assert p3.status_code == 200

    # 5. Verify behaviour postponement analysis captures 2 postponements
    pp_resp = client.get("/api/behaviour/postponements")
    assert pp_resp.status_code == 200
    pp_data = pp_resp.json()
    assert pp_data["total_postponements"] >= 2
    assert pp_data["postponed_task_count"] >= 1
    found_task = next((t for t in pp_data["repeatedly_postponed_tasks"] if t["task_id"] == task.id), None)
    assert found_task is not None
    assert found_task["postpone_count"] == 2


# ===========================================================================
# WORKFLOW E: Daily Planning & Workload Capacity
# Create daily plan -> Add multiple tasks -> Check capacity ->
# Use Auto-Schedule / shift -> Verify planned vs actual analytics
# ===========================================================================
def test_workflow_e_daily_planning(client, db_session):
    today = date.today()

    # 1. Create 3 timeblocks for today
    b1 = client.post("/api/timeblocks", json={
        "block_date": today.isoformat(),
        "title": "Deep Architecture Session",
        "time": "09:00 AM",
        "duration_minutes": 120,
        "actual_duration_minutes": 130,
        "category": "Coding",
        "status": "Completed",
    })
    b2 = client.post("/api/timeblocks", json={
        "block_date": today.isoformat(),
        "title": "API Documentation",
        "time": "11:30 AM",
        "duration_minutes": 60,
        "actual_duration_minutes": 55,
        "category": "Reading",
        "status": "Completed",
    })
    b3 = client.post("/api/timeblocks", json={
        "block_date": today.isoformat(),
        "title": "System Audit Sprint",
        "time": "02:00 PM",
        "duration_minutes": 90,
        "actual_duration_minutes": None,
        "category": "Coding",
        "status": "Pending",
    })
    assert b1.status_code == 201
    assert b2.status_code == 201
    assert b3.status_code == 201

    # 2. Query timeblocks by date
    list_resp = client.get(f"/api/timeblocks?block_date={today.isoformat()}")
    assert list_resp.status_code == 200
    blocks = list_resp.json()
    assert len(blocks) == 3

    # 3. Verify planned vs actual aggregation
    pva_resp = client.get("/api/timeblocks/analytics/planned-vs-actual")
    assert pva_resp.status_code == 200
    pva_data = pva_resp.json()
    coding_cat = next((c for c in pva_data if c["category"] == "Coding"), None)
    assert coding_cat is not None
    assert coding_cat["plannedHours"] >= 3.5  # 120 + 90 = 210 mins = 3.5 hrs


# ===========================================================================
# WORKFLOW F: Analytics Validation with Manually Verified Math
# Generate sufficient test activity -> Verify calculated numbers
# ===========================================================================
def test_workflow_f_analytics_exact_math(client, db_session):
    today = date.today()

    # Clear tasks & goals in this isolated db session to test exact math
    db_session.query(Task).delete()
    db_session.commit()

    # Zero tasks -> Rates should safely be 0.0 without division by zero
    zero_resp = client.get("/api/analytics/overview")
    assert zero_resp.status_code == 200
    assert zero_resp.json()["daily_completion_rate"] == 0.0
    assert zero_resp.json()["weekly_completion_rate"] == 0.0

    # Insert exactly 4 tasks: 2 completed, 2 pending -> Rate must be exactly 50.0%
    for i in range(2):
        t_done = Task(
            id=f"t_math_done_{i}",
            title=f"Completed Task {i}",
            task_type="Daily",
            category="Coding",
            priority="Medium",
            status="Completed",
            start_date=today,
            due_date=today,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(t_done)
    for i in range(2):
        t_pend = Task(
            id=f"t_math_pend_{i}",
            title=f"Pending Task {i}",
            task_type="Daily",
            category="Coding",
            priority="Medium",
            status="Pending",
            start_date=today,
            due_date=today,
        )
        db_session.add(t_pend)
    db_session.commit()

    math_resp = client.get("/api/analytics/overview")
    assert math_resp.status_code == 200
    math_data = math_resp.json()
    assert math_data["total_completed_tasks"] == 2
    assert math_data["total_pending_tasks"] == 2
    assert math_data["daily_completion_rate"] == 50.0
    assert math_data["weekly_completion_rate"] == 50.0


# ===========================================================================
# WORKFLOW G: Persistence & Restart Simulation
# Create records -> Simulate DB disconnect/reconnect -> Verify records
# ===========================================================================
def test_workflow_g_database_persistence(client, db_session):
    today = date.today()
    unique_title = f"Persistent Kernel Task {uuid.uuid4().hex[:6]}"

    # 1. Insert via API
    resp = client.post("/api/tasks", json={
        "title": unique_title,
        "taskType": "Daily",
        "category": "Career",
        "priority": "High",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": today.isoformat(),
    })
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # 2. Simulate session close & refresh directly from db engine
    db_session.expire_all()
    queried_task = db_session.query(Task).filter(Task.id == task_id).first()
    assert queried_task is not None
    assert queried_task.title == unique_title
    assert queried_task.category == "Career"
    assert queried_task.priority == "High"


# ===========================================================================
# WORKFLOW H: Error Recovery
# Submit invalid data -> Verify error handling -> Correct input ->
# Submit again -> Verify successful operation
# ===========================================================================
def test_workflow_h_error_recovery(client, db_session):
    today = date.today()

    # 1. Submit invalid task (missing title, invalid priority, invalid taskType)
    invalid_payload = {
        "taskType": "InvalidType123",
        "category": "NonExistentCategory",
        "priority": "UltraPriority",
        "startDate": "invalid-date-format",
    }
    err_resp = client.post("/api/tasks", json=invalid_payload)
    assert err_resp.status_code == 422  # Pydantic validation error
    err_json = err_resp.json()
    assert "detail" in err_json

    # 2. Submit corrected payload
    valid_payload = {
        "title": "Corrected Task After Validation Error",
        "taskType": "Daily",
        "category": "Personal",
        "priority": "Low",
        "status": "Pending",
        "startDate": today.isoformat(),
        "dueDate": today.isoformat(),
    }
    success_resp = client.post("/api/tasks", json=valid_payload)
    assert success_resp.status_code == 201
    assert success_resp.json()["title"] == "Corrected Task After Validation Error"
