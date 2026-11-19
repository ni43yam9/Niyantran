from datetime import datetime, date, timedelta, timezone
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog

def test_analytics_overview_productivity_score(client, db_session):
    now = datetime.now(timezone.utc)
    today = date.today()
    # Add tasks
    t1 = Task(id="t-1", title="Task 1", category="Coding", status="Completed", completed_at=now, start_date=today, due_date=today)
    t2 = Task(id="t-2", title="Task 2", category="Academic", status="Pending", start_date=today, due_date=today)
    db_session.add_all([t1, t2])

    # Add habit
    h1 = Habit(id="h-1", name="Morning Exercise", target="Daily", category="Health")
    db_session.add(h1)
    db_session.commit()

    # Log habit
    hl = HabitLog(id="hl-1", habit_id="h-1", log_date=today, completed=True)
    db_session.add(hl)
    db_session.commit()

    resp = client.get("/api/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["productivity_score"] <= 100
    assert data["total_completed_tasks"] == 1
    assert data["total_pending_tasks"] == 1
    assert "daily_completion_rate" in data

def test_daily_analytics_calculations(client, db_session):
    now = datetime.now(timezone.utc)
    today = date.today()
    t1 = Task(id="t-d1", title="Daily Task", category="Coding", status="Completed", completed_at=now, start_date=today, due_date=today)
    db_session.add(t1)

    b1 = DailyTimeblock(
        id="blk-d1",
        block_date=today,
        title="Deep Work",
        time="09:00 AM",
        duration_minutes=90,
        actual_duration_minutes=90,
        status="Completed",
    )
    db_session.add(b1)
    db_session.commit()

    resp = client.get(f"/api/analytics/daily?date={today.isoformat()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_date"] == today.isoformat()
    assert data["tasks_completed"] == 1
    assert data["focus_minutes_planned"] == 90
    assert data["focus_minutes_actual"] == 90

def test_weekly_analytics_trend(client, db_session):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    resp = client.get(f"/api/analytics/weekly?start_date={start_of_week.isoformat()}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["daily_breakdown"]) == 7
    assert data["daily_breakdown"][0]["day_name"] == "Mon"
    assert data["daily_breakdown"][6]["day_name"] == "Sun"
    assert "productivity_trend" in data

def test_monthly_analytics_comparison(client, db_session):
    now = datetime.now(timezone.utc)
    today = date.today()

    t_curr = Task(id="t-m1", title="Current Month Task", category="Coding", status="Completed", completed_at=now, start_date=today, due_date=today)
    db_session.add(t_curr)
    db_session.commit()

    resp = client.get(f"/api/analytics/monthly?year={today.year}&month={today.month}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == today.year
    assert data["month"] == today.month
    assert data["tasks_completed"] >= 1
    assert "trend" in data

def test_time_analytics_quadrants(client, db_session):
    today = date.today()
    now_morning = datetime.now(timezone.utc).replace(hour=8, minute=30)
    t_m = Task(id="t-tm1", title="Morning Code", category="Coding", status="Completed", completed_at=now_morning, start_date=today, due_date=today)
    db_session.add(t_m)

    b_est = DailyTimeblock(
        id="blk-est1",
        block_date=today,
        title="Architecture",
        time="08:30 AM",
        duration_minutes=60,
        actual_duration_minutes=90,
        status="Completed",
    )
    db_session.add(b_est)
    db_session.commit()

    resp = client.get("/api/analytics/time?tz_offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "quadrant_distribution" in data
    assert "quadrant_percentages" in data
    assert "most_productive_window" in data
    assert data["total_actual_minutes"] == 90
    assert data["total_estimated_minutes"] == 60

def test_goal_analytics_progress(client, db_session):
    today = date.today()
    g1 = Goal(
        id="g-1",
        title="Master Machine Learning",
        category="Academic",
        goal_type="Short-Term",
        priority="High",
        status="In Progress",
        start_date=today,
        target_date=today + timedelta(days=90),
        progress=50,
    )
    db_session.add(g1)
    db_session.commit()

    t_g1 = Task(id="t-g1", title="Lecture 1", category="Academic", status="Completed", goal_id="g-1", start_date=today, due_date=today)
    t_g2 = Task(id="t-g2", title="Lecture 2", category="Academic", status="Pending", goal_id="g-1", start_date=today, due_date=today)
    db_session.add_all([t_g1, t_g2])
    db_session.commit()

    resp = client.get("/api/analytics/goals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_goals"] == 1
    assert data["active_goals"] == 1
    assert len(data["goals"]) == 1
    assert data["goals"][0]["total_tasks"] == 2
    assert data["goals"][0]["completed_tasks"] == 1
    assert data["goals"][0]["task_completion_rate"] == 50.0

def test_productivity_insights_generation(client, db_session):
    now = datetime.now(timezone.utc)
    today = date.today()
    # Seed 3 completed tasks to trigger timing insight
    for i in range(3):
        t = Task(
            id=f"t-ins-{i}",
            title=f"Insight Task {i}",
            category="Coding",
            status="Completed",
            completed_at=now.replace(hour=9, minute=i * 10),
            created_at=now - timedelta(hours=2),
            start_date=today,
            due_date=today,
        )
        db_session.add(t)

    # Seed an underestimated block
    b = DailyTimeblock(
        id="blk-ins-1",
        block_date=today,
        title="Underestimated Block",
        time="09:00 AM",
        duration_minutes=30,
        actual_duration_minutes=60,
        status="Completed",
    )
    b2 = DailyTimeblock(
        id="blk-ins-2",
        block_date=today,
        title="Underestimated Block 2",
        time="10:00 AM",
        duration_minutes=45,
        actual_duration_minutes=80,
        status="Completed",
    )
    db_session.add_all([b, b2])

    # Seed habit with streak
    h = Habit(id="h-ins", name="Deep Focus Habit", target="Daily", base_streak=7)
    db_session.add(h)
    db_session.commit()

    resp = client.get("/api/analytics/insights?tz_offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_sufficient_data"] is True
    assert data["total_insights"] >= 1
    assert any(ins["category"] == "Estimation" for ins in data["insights"])
