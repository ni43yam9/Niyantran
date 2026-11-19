from datetime import datetime, date, timedelta, timezone
from backend.app.models.task import Task
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.services import behaviour_service

def test_activity_creation_and_duplicate_prevention(db_session):
    now = datetime.now(timezone.utc)
    # First activity log
    act1 = behaviour_service.record_activity(
        db=db_session,
        event_type="TASK_CREATED",
        entity_type="task",
        entity_id="t-101",
        timestamp=now,
        details={"title": "Test Task"},
    )
    assert act1.id is not None
    assert act1.event_type == "TASK_CREATED"
    assert act1.entity_id == "t-101"

    # Immediate duplicate attempt should return existing record without adding a new row
    act2 = behaviour_service.record_activity(
        db=db_session,
        event_type="TASK_CREATED",
        entity_type="task",
        entity_id="t-101",
        timestamp=now + timedelta(seconds=1),
        details={"title": "Test Task"},
    )
    assert act2.id == act1.id

    total = db_session.query(ActivityLog).count()
    assert total == 1

def test_task_completion_monitoring(db_session):
    now = datetime.now(timezone.utc)
    today = date.today()
    # Create sample tasks
    t1 = Task(id="t-1", title="Task 1", category="Coding", status="Completed", created_at=now - timedelta(hours=3), completed_at=now, start_date=today, due_date=today)
    t2 = Task(id="t-2", title="Task 2", category="Academic", status="Completed", created_at=now - timedelta(hours=5), completed_at=now - timedelta(hours=1), start_date=today, due_date=today)
    t3 = Task(id="t-3", title="Task 3", category="Personal", status="Pending", created_at=now, start_date=today, due_date=today + timedelta(days=1))
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    analysis = behaviour_service.get_task_completion_analysis(db_session)
    assert analysis.total_created == 3
    assert analysis.total_completed == 2
    assert analysis.total_pending == 1
    assert analysis.completion_rate == 66.7
    assert analysis.has_sufficient_data is True
    assert analysis.average_completion_time_hours is not None
    assert analysis.average_completion_time_hours > 0

def test_repeated_postponement_detection(db_session):
    now = datetime.now(timezone.utc)
    today = date.today()
    # Task postponed twice
    t_postponed = Task(id="t-delayed", title="Delayed Research", category="Coding", status="Pending", start_date=today - timedelta(days=2), due_date=today + timedelta(days=2))
    db_session.add(t_postponed)
    db_session.commit()

    # Log 2 postponements
    behaviour_service.record_activity(
        db_session,
        event_type="TASK_POSTPONED",
        entity_type="task",
        entity_id="t-delayed",
        timestamp=now - timedelta(days=2),
        original_date=today - timedelta(days=2),
        new_date=today - timedelta(days=1),
        deduplicate_window_seconds=0,
    )
    behaviour_service.record_activity(
        db_session,
        event_type="TASK_POSTPONED",
        entity_type="task",
        entity_id="t-delayed",
        timestamp=now - timedelta(days=1),
        original_date=today - timedelta(days=1),
        new_date=today + timedelta(days=2),
        deduplicate_window_seconds=0,
    )

    analysis = behaviour_service.get_postponement_analysis(db_session)
    assert analysis.total_postponements == 2
    assert len(analysis.repeatedly_postponed_tasks) == 1
    assert analysis.repeatedly_postponed_tasks[0].task_id == "t-delayed"
    assert analysis.repeatedly_postponed_tasks[0].postpone_count == 2

def test_time_estimation_comparison_and_bias(db_session):
    # Add timeblocks with underestimation (actual > duration)
    b1 = DailyTimeblock(
        id="blk-1",
        block_date=date.today(),
        title="DSA Practice",
        time="08:00 AM",
        duration_minutes=60,
        actual_duration_minutes=90,
        category="Coding",
        status="Completed",
    )
    b2 = DailyTimeblock(
        id="blk-2",
        block_date=date.today(),
        title="Component Build",
        time="10:00 AM",
        duration_minutes=90,
        actual_duration_minutes=120,
        category="Coding",
        status="Completed",
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    analysis = behaviour_service.get_time_estimation_analysis(db_session)
    assert analysis.total_tracked_tasks == 2
    assert analysis.total_planned_minutes == 150
    assert analysis.total_actual_minutes == 210
    assert analysis.underestimated_count == 2
    assert analysis.estimation_bias == "Underestimation"
    assert analysis.has_sufficient_data is True
    assert len(analysis.category_breakdown) == 1
    assert analysis.category_breakdown[0].category == "Coding"
    assert analysis.category_breakdown[0].is_underestimated is True

def test_insufficient_data_graceful_handling(db_session):
    # Empty database should gracefully return insufficient data
    comp_analysis = behaviour_service.get_task_completion_analysis(db_session)
    assert comp_analysis.has_sufficient_data is False
    assert "Not enough activity data" in comp_analysis.message

    est_analysis = behaviour_service.get_time_estimation_analysis(db_session)
    assert est_analysis.has_sufficient_data is False
    assert est_analysis.estimation_bias == "Insufficient Data"

    prod_analysis = behaviour_service.get_productivity_hours_analysis(db_session)
    assert prod_analysis.has_sufficient_data is False
    assert prod_analysis.peak_period == "Insufficient Data"

def test_behaviour_summary_api_endpoint(client):
    resp = client.get("/api/behaviour/summary?tz_offset=330")
    assert resp.status_code == 200
    data = resp.json()
    assert "task_completion" in data
    assert "procrastination" in data
    assert "time_estimation" in data
    assert "productivity_hours" in data
    assert "habit_consistency" in data
    assert "daily_planning" in data
    assert "overall_assessment" in data
