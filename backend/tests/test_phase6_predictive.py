import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.services.predictive.data_preparation import prepare_predictive_dataset
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.ml_models import MachineLearningPredictor
from backend.app.services.predictive.predictors.completion_estimator import (
    predict_task_completion_likelihood,
    predict_all_task_completions,
)
from backend.app.services.predictive.predictors.deadline_predictor import predict_deadline_risks
from backend.app.services.predictive.predictors.goal_risk_predictor import predict_goal_risks
from backend.app.services.predictive.predictors.workload_forecaster import forecast_workload_distribution
from backend.app.services.predictive.predictors.habit_predictor import predict_habit_decay
from backend.app.services.predictive.predictors.productivity_predictor import predict_productivity_trend
from backend.app.services.predictive.predictive_engine import predictive_engine

def test_task_completion_prediction_likelihood_calculation(db_session):
    """
    Verifies that task completion prediction analyzes duration, bias, deadline proximity,
    priority, and postponements to estimate completion likelihood (0.0% to 100.0%).
    """
    today = date.today()
    t_id = f"t_{uuid.uuid4().hex[:10]}"

    task = Task(
        id=t_id,
        title="Implement OAuth2 Provider Integration",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    # Timeblock: planned 120m, actual 180m -> 1.5x estimation bias
    tb = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="OAuth Deep Work",
        time="09:00 AM",
        block_date=today,
        duration_minutes=120,
        actual_duration_minutes=180,
        task_id=t_id,
        status="Completed",
    )
    # Postponement log
    act = ActivityLog(
        id=f"act_{uuid.uuid4().hex[:10]}",
        event_type="TASK_POSTPONED",
        entity_id=t_id,
        entity_type="Task",
        timestamp=datetime.now(timezone.utc),
    )
    db_session.add_all([task, tb, act])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)
    ml_pred = MachineLearningPredictor()

    pred = predict_task_completion_likelihood(task, container, extractor, ml_pred)

    assert pred["task_id"] == t_id
    assert 0.0 <= pred["completion_likelihood"] <= 100.0
    assert pred["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert 0.0 <= pred["confidence_score"] <= 1.0
    assert len(pred["supporting_evidence"]) >= 3
    assert "Estimated completion likelihood" in pred["supporting_evidence"][0]
    assert len(pred["suggested_action"]) > 10

def test_deadline_risk_prediction_overdue_and_upcoming(db_session):
    """
    Verifies deadline risk prediction for overdue deliverables (100% risk, 0% likelihood)
    and upcoming deliverables with supporting evidence and preventive guidance.
    """
    today = date.today()
    t_overdue_id = f"t_{uuid.uuid4().hex[:10]}"
    t_upcoming_id = f"t_{uuid.uuid4().hex[:10]}"

    t_overdue = Task(
        id=t_overdue_id,
        title="Critical Security Compliance Audit",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2),
    )
    t_upcoming = Task(
        id=t_upcoming_id,
        title="Write Documentation Handbook",
        category="Reading",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add_all([t_overdue, t_upcoming])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)
    ml_pred = MachineLearningPredictor()

    insights = predict_deadline_risks(container, extractor, ml_pred)
    overdue_ins = next((i for i in insights if i["entity_id"] == t_overdue_id), None)
    upcoming_ins = next((i for i in insights if i["entity_id"] == t_upcoming_id), None)

    assert overdue_ins is not None
    assert overdue_ins["risk_score"] == 100.0
    assert overdue_ins["risk_category"] == "CRITICAL"
    assert overdue_ins["predicted_outcome"] == "OVERDUE"
    assert any("0.0%" in ev for ev in overdue_ins["supporting_evidence"])

    assert upcoming_ins is not None
    assert upcoming_ins["risk_category"] in ("LOW", "MODERATE", "HIGH", "INSUFFICIENT_DATA")
    assert any("Estimated completion likelihood" in ev for ev in upcoming_ins["supporting_evidence"])

def test_goal_achievement_prediction_and_insufficient_data_guard(db_session):
    """
    Verifies goal trajectory estimation:
    - Avoids making predictions on young goals (< 3 days elapsed, 0 completions) with INSUFFICIENT_DATA.
    - Estimates trajectory velocity and required pace when sufficient history exists.
    """
    today = date.today()

    # Goal A: Brand new goal (created today, 0 progress, 0 tasks completed) -> INSUFFICIENT_DATA
    g_new_id = f"g_{uuid.uuid4().hex[:10]}"
    g_new = Goal(
        id=g_new_id,
        title="Enterprise Scalability Overhaul",
        goal_type="Long-Term",
        category="Coding",
        priority="High",
        status="In Progress",
        start_date=today,
        target_date=today + timedelta(days=60),
        progress=0,
    )

    # Goal B: Active goal with history and velocity deficit
    g_active_id = f"g_{uuid.uuid4().hex[:10]}"
    g_active = Goal(
        id=g_active_id,
        title="Cloud Cost Reduction",
        goal_type="Short-Term",
        category="Career",
        priority="Medium",
        status="In Progress",
        start_date=today - timedelta(days=20),
        target_date=today + timedelta(days=10),
        progress=15, # 15% in 20 days = 0.75%/day; required: 85% in 10 days = 8.5%/day (severe deficit!)
    )
    t_linked = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Audit S3 Buckets",
        goal_id=g_active_id,
        category="Career",
        priority="Medium",
        status="Completed",
        start_date=today - timedelta(days=15),
        due_date=today - timedelta(days=10),
        completed_at=datetime.now(timezone.utc) - timedelta(days=5),
    )

    db_session.add_all([g_new, g_active, t_linked])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    insights = predict_goal_risks(container, extractor)

    # Goal A should have INSUFFICIENT_DATA
    ins_new = next((i for i in insights if i["entity_id"] == g_new_id), None)
    assert ins_new is not None
    assert ins_new["has_sufficient_data"] is False
    assert ins_new["risk_category"] == "INSUFFICIENT_DATA"
    assert ins_new["predicted_outcome"] == "INSUFFICIENT_DATA"

    # Goal B should have high risk due to velocity deficit
    ins_active = next((i for i in insights if i["entity_id"] == g_active_id), None)
    assert ins_active is not None
    assert ins_active["has_sufficient_data"] is True
    assert ins_active["risk_category"] in ("HIGH", "CRITICAL")
    assert any("Velocity deficit" in ev for ev in ins_active["supporting_evidence"])

def test_workload_forecasting_conflicts_and_non_destructiveness(db_session):
    """
    Verifies that workload forecasting detects overloaded days, scheduling conflicts,
    and available capacity WITHOUT mutating task dates.
    """
    today = date.today()
    conflict_date = today + timedelta(days=2)
    original_start_date = today

    # Two high priority tasks due on the same date -> Scheduling Conflict
    t1 = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Database Migration Execution",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=original_start_date,
        due_date=conflict_date,
    )
    t2 = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Executive Security Briefing",
        category="Career",
        priority="High",
        status="Pending",
        start_date=original_start_date,
        due_date=conflict_date,
    )
    # Heavy timeblock on conflict_date: 420 mins (> 360m threshold)
    tb_heavy = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="All Day Workshop",
        time="09:00 AM",
        block_date=conflict_date,
        duration_minutes=420,
        status="Pending",
    )
    db_session.add_all([t1, t2, tb_heavy])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    insights = forecast_workload_distribution(container, extractor)

    # Verify overloaded day bottleneck
    overload_ins = next((i for i in insights if i["entity_id"] == f"workload_{conflict_date.isoformat()}"), None)
    assert overload_ins is not None
    assert overload_ins["risk_category"] in ("HIGH", "CRITICAL")
    assert overload_ins["predicted_outcome"] == "BOTTLENECK"

    # Verify scheduling conflict detection
    conflict_ins = next((i for i in insights if i["entity_id"] == f"conflict_{conflict_date.isoformat()}"), None)
    assert conflict_ins is not None
    assert "Scheduling Conflict" in conflict_ins["title"]
    assert conflict_ins["predicted_outcome"] == "SCHEDULING_CONFLICT"

    # Verify non-destructive invariant: Task start_date and due_date MUST NOT change
    t1_check = db_session.query(Task).filter(Task.id == t1.id).first()
    assert t1_check.start_date == original_start_date
    assert t1_check.due_date == conflict_date

def test_habit_consistency_prediction_early_warnings(db_session):
    """
    Verifies habit early warnings:
    - Streak break risk when active streak is unlogged today.
    - Increasing missed-day patterns when multiple recent days were missed.
    - Insufficient data handling when habit has < 2 logs.
    """
    today = date.today()

    # Habit 1: Active 6-day streak, unlogged today -> Early Warning: STREAK_BREAK
    h1_id = f"h_{uuid.uuid4().hex[:10]}"
    h1 = Habit(
        id=h1_id,
        name="Daily Deep Reading",
        category="Reading",
        frequency="Daily",
        base_streak=6,
    )
    hl1 = HabitLog(
        id=f"hl_{uuid.uuid4().hex[:10]}",
        habit_id=h1_id,
        log_date=today - timedelta(days=1),
        completed=True,
    )
    hl2 = HabitLog(
        id=f"hl_{uuid.uuid4().hex[:10]}",
        habit_id=h1_id,
        log_date=today - timedelta(days=2),
        completed=True,
    )

    # Habit 2: Brand new habit with 0 logs -> INSUFFICIENT_DATA
    h2_id = f"h_{uuid.uuid4().hex[:10]}"
    h2 = Habit(
        id=h2_id,
        name="New Piano Practice",
        category="Personal",
        frequency="Daily",
        base_streak=0,
    )

    db_session.add_all([h1, hl1, hl2, h2])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    insights = predict_habit_decay(container, extractor)

    # Habit 1: Streak break warning
    h1_ins = next((i for i in insights if i["entity_id"] == h1_id), None)
    assert h1_ins is not None
    assert h1_ins["predicted_outcome"] == "STREAK_BREAK"
    assert h1_ins["risk_category"] == "HIGH"

    # Habit 2: Insufficient data
    h2_ins = next((i for i in insights if i["entity_id"] == h2_id), None)
    assert h2_ins is not None
    assert h2_ins["has_sufficient_data"] is False
    assert h2_ins["risk_category"] == "INSUFFICIENT_DATA"

def test_productivity_trend_backlog_expansion_vs_real_productivity(db_session):
    """
    Verifies that increased task creation is NOT confused with increased productivity.
    When 6 tasks are created but only 1 is completed, trend must be flagged as DECLINING / BACKLOG EXPANSION.
    """
    today = date.today()

    # 1 Task completed in last 7 days
    t_comp = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Completed Bugfix",
        category="Coding",
        priority="Medium",
        status="Completed",
        start_date=today - timedelta(days=3),
        due_date=today - timedelta(days=1),
        completed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(t_comp)

    # 6 new tasks created in last 7 days without completions -> Backlog Expansion!
    for i in range(6):
        t_new = Task(
            id=f"t_new_{i}_{uuid.uuid4().hex[:6]}",
            title=f"New Task {i}",
            category="Academic",
            priority="Low",
            status="Pending",
            start_date=today,
            due_date=today + timedelta(days=5),
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(t_new)

    # Add 4 additional completed historical tasks beyond 14d so total_observations >= 5
    for i in range(4):
        t_hist = Task(
            id=f"t_hist_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Historical Completed {i}",
            category="Coding",
            priority="Low",
            status="Completed",
            start_date=today - timedelta(days=30),
            due_date=today - timedelta(days=25),
            completed_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        db_session.add(t_hist)

    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    insights = predict_productivity_trend(container, extractor)
    assert len(insights) >= 1
    trend_ins = insights[0]

    # Must be DECLINING due to backlog expansion
    assert trend_ins["predicted_outcome"] == "DECLINING"
    assert trend_ins["risk_category"] == "HIGH"
    assert "backlog expansion" in trend_ins["summary"].lower()
    assert any("not represent increased productivity" in ev.lower() or "not represent" in trend_ins["summary"].lower() for ev in trend_ins["contributing_factors"] + [trend_ins["summary"]])

def test_api_task_completion_predictions(client, db_session):
    """
    Verifies the new Phase 6 task completion prediction REST endpoints:
    - GET /api/predictions/tasks
    - GET /api/predictions/tasks/{task_id}
    """
    today = date.today()
    t_id = f"t_{uuid.uuid4().hex[:10]}"

    task = Task(
        id=t_id,
        title="Performance Profiling Engine",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=3),
    )
    db_session.add(task)
    db_session.commit()

    # List all task completion predictions
    resp_list = client.get("/api/predictions/tasks")
    assert resp_list.status_code == 200
    tasks_data = resp_list.json()
    assert isinstance(tasks_data, list)
    target = next((item for item in tasks_data if item["task_id"] == t_id), None)
    assert target is not None
    assert 0.0 <= target["completion_likelihood"] <= 100.0
    assert target["risk_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert "explanation" in target
    assert "suggested_action" in target

    # Single task prediction
    resp_single = client.get(f"/api/predictions/tasks/{t_id}")
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["task_id"] == t_id
    assert single_data["title"] == "Performance Profiling Engine"

    # Nonexistent task returns 404
    assert client.get("/api/predictions/tasks/nonexistent-id").status_code == 404
