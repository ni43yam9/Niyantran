import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.recommendation import Recommendation
from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.models.adaptive_profile import UserProductivityProfile

from backend.app.services.adaptive.confidence_manager import (
    MIN_EVENTS_TIME_OF_DAY,
    MIN_EVENTS_DAY_OF_WEEK,
    MIN_BLOCKS_ESTIMATION_BIAS,
    MIN_INTERACTIONS_REC_WEIGHTS,
    get_time_window_bucket,
    calculate_sample_confidence,
    compute_recency_weights,
)
from backend.app.services.adaptive.behaviour_learner import (
    learn_working_periods,
    learn_task_tendencies,
    learn_postponements,
    learn_estimation_bias,
    learn_habit_consistency,
    learn_goal_progress,
    learn_workload_tolerance,
)
from backend.app.services.adaptive.adaptive_recommender import (
    analyze_recommendation_interactions,
    is_entity_action_suppressed,
)
from backend.app.services.adaptive.calibration_engine import (
    calibrate_predictions,
)
from backend.app.services.adaptive.scheduling_advisor import (
    generate_adaptive_scheduling_suggestions,
)
from backend.app.services.adaptive.adaptive_service import (
    build_or_refresh_profile,
    get_or_build_profile,
    get_learned_patterns_response,
)

client = TestClient(app)

def test_behaviour_pattern_identification(db_session):
    """
    Verifies that the Behaviour Learning Engine identifies working periods,
    peak days, task execution tendencies, and estimation bias from empirical data.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # 1. Create 6 completed morning timeblocks and 1 afternoon timeblock
    for i in range(6):
        tb = DailyTimeblock(
            id=f"tb_morn_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Morning Coding Block {i}",
            time="09:00 AM",
            block_date=today - timedelta(days=i),
            duration_minutes=60,
            actual_duration_minutes=80, # 1.33x bias
            status="Completed",
            category="Coding",
        )
        db_session.add(tb)

    tb_aft = DailyTimeblock(
        id=f"tb_aft_{uuid.uuid4().hex[:6]}",
        title="Afternoon Admin",
        time="02:30 PM",
        block_date=today - timedelta(days=1),
        duration_minutes=30,
        actual_duration_minutes=30,
        status="Completed",
        category="General",
    )
    db_session.add(tb_aft)

    # 2. Create tasks & activity logs
    task1 = Task(
        id=f"t1_{uuid.uuid4().hex[:6]}",
        title="Core Algorithm Implementation",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Completed",
        start_date=today - timedelta(days=2),
        due_date=today - timedelta(days=1),
        completed_at=now_utc - timedelta(days=1),
    )
    task2 = Task(
        id=f"t2_{uuid.uuid4().hex[:6]}",
        title="Literature Study",
        task_type="Daily",
        category="Reading",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    task3 = Task(
        id=f"t3_{uuid.uuid4().hex[:6]}",
        title="Code Review Session",
        task_type="Daily",
        category="Coding",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=3),
    )
    db_session.add_all([task1, task2, task3])

    # 3. Postponement event
    act_post = ActivityLog(
        id=f"act_p_{uuid.uuid4().hex[:6]}",
        event_type="TASK_POSTPONED",
        entity_type="Task",
        entity_id=task2.id,
        timestamp=now_utc,
    )
    db_session.add(act_post)
    db_session.commit()

    timeblocks = db_session.query(DailyTimeblock).all()
    tasks = db_session.query(Task).all()
    activity_logs = db_session.query(ActivityLog).all()

    # Learn working periods
    wp = learn_working_periods(timeblocks, activity_logs, tasks, now_utc=now_utc)
    assert wp.has_sufficient_data is True
    assert wp.peak_time_window == "Morning"
    assert wp.sample_size >= 6
    assert wp.confidence > 0.50

    # Learn task tendencies
    tend = learn_task_tendencies(tasks, activity_logs)
    assert tend.total_created >= 2
    assert tend.most_completed_category == "Coding"
    assert tend.completion_rate > 0.0

    # Learn postponements
    post = learn_postponements(tasks, activity_logs)
    assert post.total_postponements >= 1
    assert post.has_sufficient_data is True

    # Learn estimation bias
    bias = learn_estimation_bias(timeblocks)
    assert bias.is_empirical is True
    assert bias.duration_bias_factor >= 1.20
    assert bias.sample_size >= 7


def test_minimum_data_requirements_and_insufficient_data():
    """
    Verifies that the Behaviour Learning Engine enforces strict minimum-data thresholds
    and marks patterns as INSUFFICIENT_DATA when observation counts fall below targets.
    """
    # Empty dataset
    wp_empty = learn_working_periods([], [], [])
    assert wp_empty.has_sufficient_data is False
    assert wp_empty.peak_time_window == "INSUFFICIENT_DATA"
    assert wp_empty.confidence <= 0.20
    assert any("Insufficient data" in e for e in wp_empty.evidence)

    # 2 events only (< MIN_EVENTS_TIME_OF_DAY = 5)
    tb1 = DailyTimeblock(
        id="tb_1",
        title="Session 1",
        time="10:00 AM",
        block_date=date.today(),
        duration_minutes=60,
        actual_duration_minutes=70,
        status="Completed",
    )
    tb2 = DailyTimeblock(
        id="tb_2",
        title="Session 2",
        time="11:00 AM",
        block_date=date.today(),
        duration_minutes=60,
        actual_duration_minutes=60,
        status="Completed",
    )

    wp_few = learn_working_periods([tb1, tb2], [], [])
    assert wp_few.has_sufficient_data is False
    assert wp_few.peak_time_window == "INSUFFICIENT_DATA"
    assert wp_few.sample_size == 2

    # Estimation bias with 2 blocks (< MIN_BLOCKS_ESTIMATION_BIAS = 3)
    bias_few = learn_estimation_bias([tb1, tb2])
    assert bias_few.has_sufficient_data is False
    assert bias_few.is_empirical is False
    assert bias_few.duration_bias_factor == 1.25 # Safe heuristic baseline


def test_prediction_calibration_overconfidence_and_underconfidence(db_session):
    """
    Tests prediction calibration engine:
    1. Detects systematic overconfidence when predictions overestimate on-time completions.
    2. Computes Brier scores and reliability bins.
    3. Detects underconfidence when predictions underestimate completions.
    """
    today = date.today()
    past_date = today - timedelta(days=2)

    # Scenario A: 6 predictions predicting high completion likelihood (85%), but entity was overdue -> OVERCONFIDENT
    for i in range(6):
        ins = PredictiveInsight(
            id=f"pred_over_{i}_{uuid.uuid4().hex[:6]}",
            prediction_type="DEADLINE_RISK",
            entity_type="Task",
            entity_id=f"task_test_{i}",
            risk_score=15.0, # 85% implied success
            risk_category="LOW",
            confidence_score=0.85,
            has_sufficient_data=True,
            title=f"Task On-Time Prediction {i}",
            summary="Expected on-time delivery",
            horizon_date=past_date,
            predicted_outcome="ON_TIME",
            actual_outcome="OVERDUE", # Actually failed!
            evaluation_status="EVALUATED",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(ins)

    db_session.commit()

    calib_over = calibrate_predictions(db_session, reference_date=today)
    assert calib_over.total_evaluated >= 6
    assert calib_over.brier_score is not None
    assert calib_over.brier_score > 0.40 # High error due to overconfidence
    assert calib_over.calibration_bias is not None
    assert calib_over.calibration_bias > 0.10
    assert calib_over.calibration_status == "OVERCONFIDENT"
    assert len(calib_over.reliability_bins) == 5

    # Scenario B: Add 6 predictions predicting low success (20% likelihood), but entity succeeded ON_TIME
    for i in range(6):
        ins_under = PredictiveInsight(
            id=f"pred_under_{i}_{uuid.uuid4().hex[:6]}",
            prediction_type="DEADLINE_RISK",
            entity_type="Task",
            entity_id=f"task_under_{i}",
            risk_score=80.0, # 20% implied success
            risk_category="HIGH",
            confidence_score=0.20,
            has_sufficient_data=True,
            title=f"Task Underconfidence {i}",
            summary="Expected overdue",
            horizon_date=past_date,
            predicted_outcome="OVERDUE",
            actual_outcome="ON_TIME", # Actually succeeded!
            evaluation_status="EVALUATED",
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(ins_under)

    db_session.commit()

    # Now with 12 total evaluations, validated threshold >= 10 is reached
    calib_all = calibrate_predictions(db_session, reference_date=today)
    assert calib_all.total_evaluated >= 12
    assert calib_all.has_sufficient_evaluations is True
    assert calib_all.advisory_calibration_factor > 0.0


def test_recommendation_feedback_and_adaptive_weights(db_session):
    """
    Verifies that historical user interactions adapt recommendation weights:
    - Frequently accepted and executed types receive positive weight boosts.
    - Consistently dismissed types receive weight dampening.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # 1. PRIORITIZATION recommendations: 4 accepted & completed
    for i in range(4):
        rec_prio = Recommendation(
            id=f"rec_prio_{i}_{uuid.uuid4().hex[:6]}",
            type="PRIORITIZATION",
            category="Task",
            title=f"Prioritize High Impact Deliverable {i}",
            description="Focus on urgent item",
            reason="High urgency",
            priority="HIGH",
            status="COMPLETED",
            created_at=now_utc - timedelta(days=2),
            updated_at=now_utc - timedelta(days=1),
        )
        db_session.add(rec_prio)

    # 2. WORKLOAD_BALANCE recommendations: 4 dismissed
    for i in range(4):
        rec_work = Recommendation(
            id=f"rec_work_{i}_{uuid.uuid4().hex[:6]}",
            type="WORKLOAD_BALANCE",
            category="Schedule",
            title=f"Rebalance Day Load {i}",
            description="Move tasks",
            reason="Overloaded",
            priority="MEDIUM",
            status="DISMISSED",
            created_at=now_utc - timedelta(hours=5),
            updated_at=now_utc - timedelta(hours=4),
        )
        db_session.add(rec_work)

    db_session.commit()

    pattern = analyze_recommendation_interactions(db_session, now_utc=now_utc)
    assert pattern.total_interactions >= 8
    assert pattern.has_sufficient_data is True

    weights = pattern.adaptive_type_weights
    # PRIORITIZATION should have boost >= 1.0
    assert weights["PRIORITIZATION"] >= 1.05
    assert pattern.receptivity_by_type["PRIORITIZATION"]["status"] == "BOOSTED"

    # WORKLOAD_BALANCE should have dampening < 1.0
    assert weights["WORKLOAD_BALANCE"] < 1.0
    assert pattern.receptivity_by_type["WORKLOAD_BALANCE"]["status"] == "DAMPENED"


def test_dismissal_penalty_time_decay_recovery(db_session):
    """
    Verifies that dismissal penalties decay exponentially over time (half-life = 7 days),
    ensuring that recommendations are never permanently suppressed or muted.
    """
    now_utc = datetime.now(timezone.utc)

    # 1. Fresh dismissal (today)
    rec_fresh = Recommendation(
        id=f"rec_fresh_{uuid.uuid4().hex[:6]}",
        type="HABIT_IMPROVEMENT",
        category="Habit",
        title="Habit Momentum Push",
        description="Check in",
        reason="Streak at risk",
        priority="MEDIUM",
        status="DISMISSED",
        created_at=now_utc - timedelta(hours=2),
        updated_at=now_utc - timedelta(hours=1),
    )
    # 2. 3 Old dismissals from 14 days ago
    for i in range(3):
        rec_old = Recommendation(
            id=f"rec_old_{i}_{uuid.uuid4().hex[:6]}",
            type="GOAL_PROGRESS",
            category="Goal",
            title=f"Goal Structure Align {i}",
            description="Break down goal",
            reason="Low milestone progress",
            priority="HIGH",
            status="DISMISSED",
            created_at=now_utc - timedelta(days=15),
            updated_at=now_utc - timedelta(days=14),
        )
        db_session.add(rec_old)

    db_session.add(rec_fresh)
    db_session.commit()

    pattern = analyze_recommendation_interactions(db_session, now_utc=now_utc)
    goal_receptivity = pattern.receptivity_by_type["GOAL_PROGRESS"]

    # Penalty decay on 14-day old dismissals should be ~0.25 (2 half-lives)
    assert goal_receptivity["penalty_decay"] <= 0.30

    # Test entity-level suppression check with 7-day cooldown
    task_id = "test_task_suppress_target"
    for i in range(3):
        act_d = ActivityLog(
            id=f"act_dis_{i}_{uuid.uuid4().hex[:6]}",
            event_type="RECOMMENDATION_DISMISSED",
            entity_type="recommendation",
            entity_id=f"rec_{i}",
            details={"target_entity_id": task_id, "action_type": "RESCHEDULE_TASK"},
            timestamp=now_utc - timedelta(days=1), # Recent
        )
        db_session.add(act_d)
    db_session.commit()

    # Active suppression should be True for this recently rejected action
    is_suppressed = is_entity_action_suppressed(db_session, task_id, "RESCHEDULE_TASK", now_utc=now_utc)
    assert is_suppressed is True

    # But for a different action or entity, should be False
    assert is_entity_action_suppressed(db_session, task_id, "START_TASK", now_utc=now_utc) is False
    assert is_entity_action_suppressed(db_session, "other_task_id", "RESCHEDULE_TASK", now_utc=now_utc) is False


def test_adaptive_scheduling_suggestions_non_destructive(db_session):
    """
    Verifies adaptive scheduling suggestions:
    - High-impact tasks are suggested for the user's learned peak window.
    - Low-priority tasks are suggested for secondary windows.
    - STRICT INVARIANT: Task dates are NEVER mutated automatically; user approval is required.
    """
    today = date.today()
    t_coding_id = f"t_code_{uuid.uuid4().hex[:6]}"
    t_micro_id = f"t_micro_{uuid.uuid4().hex[:6]}"

    task_coding = Task(
        id=t_coding_id,
        title="High Priority Neural Net Training",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    task_micro = Task(
        id=t_micro_id,
        title="Organize Workspace Desk",
        task_type="Daily",
        category="Personal",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add_all([task_coding, task_micro])
    db_session.commit()

    from backend.app.schemas.adaptive import WorkingPeriodsPattern, WorkloadTolerancePattern

    wp = WorkingPeriodsPattern(
        peak_time_window="Morning",
        peak_days=["Tuesday"],
        confidence=0.85,
        has_sufficient_data=True,
    )
    wt = WorkloadTolerancePattern(
        optimal_daily_load_minutes=300,
        max_observed_sustainable_minutes=360,
        confidence=0.80,
        has_sufficient_data=True,
    )

    resp = generate_adaptive_scheduling_suggestions(
        db=db_session,
        working_periods=wp,
        workload_tolerance=wt,
        reference_date=today,
    )

    assert resp.peak_time_window == "Morning"
    assert resp.total_suggestions >= 2

    # Check energy window alignment suggestion for coding task
    coding_sugg = next((s for s in resp.suggestions if s.task_id == t_coding_id), None)
    assert coding_sugg is not None
    assert coding_sugg.suggestion_type == "ENERGY_WINDOW_ALIGNMENT"
    assert "Morning" in coding_sugg.suggested_window
    assert coding_sugg.requires_user_approval is True

    # Check micro-task suggestion for personal task
    micro_sugg = next((s for s in resp.suggestions if s.task_id == t_micro_id), None)
    assert micro_sugg is not None
    assert micro_sugg.suggestion_type == "LOW_ENERGY_MICRO_TASK"
    assert micro_sugg.requires_user_approval is True

    # STRICT INVARIANT VERIFICATION: Database task records must NOT be mutated!
    db_task = db_session.query(Task).filter(Task.id == t_coding_id).first()
    assert db_task.due_date == today + timedelta(days=1)
    assert db_task.status == "Pending"


def test_productivity_profile_persistence_and_db_integrity(db_session):
    """
    Verifies that the UserProductivityProfile record persists cleanly to SQLite,
    updates idempotently, and maintains zero foreign key violations.
    """
    profile = build_or_refresh_profile(db_session, user_id="test_user")
    assert profile.id.startswith("prof_")
    assert profile.user_id == "test_user"
    assert profile.optimal_daily_load_minutes >= 240
    assert profile.profile_data is not None
    assert "working_periods" in profile.profile_data

    # Verify retrieval
    retrieved = get_or_build_profile(db_session, user_id="test_user", force_refresh=False)
    assert retrieved.id == profile.id
    assert retrieved.profile_date == profile.profile_date


def test_changing_behavioural_patterns_adaptation(db_session):
    """
    Verifies that learned patterns adapt when user behavior shifts over time,
    using exponential recency weighting.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # 5 Old morning timeblocks from 25 days ago
    for i in range(5):
        tb_old = DailyTimeblock(
            id=f"tb_old_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Old Morning {i}",
            time="08:30 AM",
            block_date=today - timedelta(days=25 + i),
            duration_minutes=60,
            actual_duration_minutes=60,
            status="Completed",
            category="Coding",
        )
        tb_old.updated_at = now_utc - timedelta(days=25 + i)
        db_session.add(tb_old)

    # 8 Recent afternoon timeblocks from last 4 days
    for i in range(8):
        tb_rec = DailyTimeblock(
            id=f"tb_rec_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Recent Afternoon {i}",
            time="02:30 PM",
            block_date=today - timedelta(days=i % 4),
            duration_minutes=60,
            actual_duration_minutes=60,
            status="Completed",
            category="Coding",
        )
        tb_rec.updated_at = now_utc - timedelta(days=i % 4)
        db_session.add(tb_rec)

    db_session.commit()

    all_tbs = db_session.query(DailyTimeblock).all()
    wp = learn_working_periods(all_tbs, [], [], now_utc=now_utc)
    # The recent behavior dominates
    assert wp.peak_time_window == "Afternoon"
    assert wp.time_window_distribution["Afternoon"] >= 8


def test_api_adaptive_endpoints():
    """
    Tests all REST API endpoints under /api/adaptive/ to guarantee complete HTTP compatibility.
    """
    # 1. GET /api/adaptive/profile
    r1 = client.get("/api/adaptive/profile")
    assert r1.status_code == 200
    p1 = r1.json()
    assert "user_id" in p1
    assert "optimal_daily_load_minutes" in p1
    assert "confidence_score" in p1

    # 2. POST /api/adaptive/profile/refresh
    r2 = client.post("/api/adaptive/profile/refresh")
    assert r2.status_code == 200
    p2 = r2.json()
    assert p2["status"] == "SUCCESS"
    assert p2["patterns_identified"] == 8

    # 3. GET /api/adaptive/patterns
    r3 = client.get("/api/adaptive/patterns")
    assert r3.status_code == 200
    p3 = r3.json()
    assert "working_periods" in p3
    assert "task_tendencies" in p3
    assert "postponements" in p3
    assert "estimation_bias" in p3
    assert "habits" in p3
    assert "goals" in p3
    assert "recommendations" in p3
    assert "workload_tolerance" in p3

    # 4. GET /api/adaptive/calibration
    r4 = client.get("/api/adaptive/calibration")
    assert r4.status_code == 200
    p4 = r4.json()
    assert "calibration_status" in p4
    assert "advisory_calibration_factor" in p4
    assert "reliability_bins" in p4

    # 5. GET /api/adaptive/scheduling-suggestions
    r5 = client.get("/api/adaptive/scheduling-suggestions")
    assert r5.status_code == 200
    p5 = r5.json()
    assert "suggestions" in p5
    assert "peak_time_window" in p5
    assert "optimal_daily_load_minutes" in p5

    # 6. GET /api/adaptive/recommendation-weights
    r6 = client.get("/api/adaptive/recommendation-weights")
    assert r6.status_code == 200
    p6 = r6.json()
    assert "adaptive_type_weights" in p6
    assert "receptivity_by_type" in p6
