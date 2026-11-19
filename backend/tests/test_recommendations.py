import uuid
from datetime import date, timedelta
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.recommendation import Recommendation

def test_prioritization_engine_urgent_task(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="High Priority Production Hotfix",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_active"] >= 1
    
    prio_items = [i for i in data["items"] if i["type"] == "PRIORITIZATION"]
    assert len(prio_items) >= 1
    assert "Hotfix" in prio_items[0]["title"]
    assert prio_items[0]["priority"] in ("HIGH", "MEDIUM")
    assert prio_items[0]["action_type"] == "FOCUS_TASK"

def test_workload_balancing_and_accept_action(client, db_session):
    today = date.today()
    task1 = Task(
        id=str(uuid.uuid4()),
        title="Core Architecture Redesign",
        task_type="Short-Term",
        category="Coding",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=5),
    )
    db_session.add(task1)
    db_session.commit()

    # Add a 400 min timeblock for today to exceed 360 min limit
    tb = DailyTimeblock(
        id=str(uuid.uuid4()),
        task_id=task1.id,
        block_date=today,
        title="Deep Work Marathon",
        time="09:00 AM",
        duration_minutes=400,
        category="Coding",
        status="Pending",
    )
    db_session.add(tb)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    
    wb_items = [i for i in data["items"] if i["type"] == "WORKLOAD_BALANCE"]
    assert len(wb_items) >= 1
    wb_rec = wb_items[0]
    assert wb_rec["action_type"] == "RESCHEDULE_TASK"
    suggested_date = wb_rec["action_payload"]["suggested_date"]
    assert suggested_date is not None

    # Test accepting recommendation
    rec_id = wb_rec["id"]
    accept_resp = client.post(f"/api/recommendations/{rec_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Verify task start_date was updated
    db_session.refresh(task1)
    assert str(task1.start_date) == suggested_date

    # Verify activity was logged
    act = db_session.query(ActivityLog).filter(ActivityLog.event_type == "TASK_RESCHEDULED").first()
    assert act is not None
    assert act.entity_id == task1.id

def test_deadline_risk_engine(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Critical Security Audit",
        task_type="Short-Term",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    db_session.add(task)
    db_session.commit()

    # Log 2 postponements
    log1 = ActivityLog(event_type="TASK_POSTPONED", entity_type="TASK", entity_id=task.id)
    log2 = ActivityLog(event_type="TASK_POSTPONED", entity_type="TASK", entity_id=task.id)
    db_session.add_all([log1, log2])
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    risk_items = [i for i in data["items"] if i["type"] == "DEADLINE_RISK"]
    assert len(risk_items) >= 1
    assert "Security Audit" in risk_items[0]["title"]
    assert "postponed" in risk_items[0]["reason"].lower()

def test_goal_progress_intelligence(client, db_session):
    today = date.today()
    goal = Goal(
        id=str(uuid.uuid4()),
        title="Launch Version 2.0",
        description="Public rollout",
        goal_type="Short-Term",
        category="Coding",
        priority="High",
        start_date=today,
        target_date=today + timedelta(days=30),
        status="In Progress",
        progress=0,
    )
    db_session.add(goal)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    goal_items = [i for i in data["items"] if i["type"] == "GOAL_PROGRESS"]
    assert len(goal_items) >= 1
    assert goal_items[0]["action_type"] == "ADD_GOAL_TASK"

def test_habit_improvement_streak_protection(client, db_session):
    today = date.today()
    habit = Habit(
        id=str(uuid.uuid4()),
        name="Daily Morning Reading",
        category="Reading",
        frequency="Daily",
        base_streak=5,
    )
    db_session.add(habit)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    habit_items = [i for i in data["items"] if i["type"] == "HABIT_IMPROVEMENT"]
    assert len(habit_items) >= 1
    assert "Protect Streak" in habit_items[0]["title"]
    assert habit_items[0]["priority"] == "HIGH"

def test_recommendation_dismiss_and_complete(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Refactor CSS Modules",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    rec_id = resp.json()["items"][0]["id"]

    # Dismiss
    dismiss_resp = client.post(f"/api/recommendations/{rec_id}/dismiss")
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "DISMISSED"

    # Verify no longer in PENDING list
    pending_resp = client.get("/api/recommendations?status=PENDING")
    pending_ids = [r["id"] for r in pending_resp.json()["items"]]
    assert rec_id not in pending_ids

def test_recommendations_deduplication(client, db_session):
    today = date.today()
    task = Task(
        id=str(uuid.uuid4()),
        title="Review PR #42",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(task)
    db_session.commit()

    # Generate twice
    client.post("/api/recommendations/generate")
    client.post("/api/recommendations/generate")

    all_recs = db_session.query(Recommendation).filter(
        Recommendation.entity_id == task.id,
        Recommendation.status == "PENDING"
    ).all()
    assert len(all_recs) == 1
