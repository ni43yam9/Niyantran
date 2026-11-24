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
from backend.app.models.recommendation import Recommendation
from backend.app.services.intelligence.context_analyzer import build_productivity_context
from backend.app.services.intelligence.priority_scorer import calculate_recommendation_priority
from backend.app.services.intelligence.explainability import StructuredExplanation
from backend.app.services.intelligence.engine import generate_intelligent_recommendations
from backend.app.services.recommendation_service import get_recommendations

def test_context_aware_multi_source_aggregation(db_session):
    """
    Verifies that the context analyzer compiles tasks, goals, habits, timeblocks,
    postponements, and behavioral bias into a unified productivity context.
    """
    today = date.today()
    t_id = f"t_{uuid.uuid4().hex[:10]}"
    g_id = f"g_{uuid.uuid4().hex[:10]}"
    h_id = f"h_{uuid.uuid4().hex[:10]}"

    goal = Goal(
        id=g_id,
        title="Q4 System Release",
        goal_type="Short-Term",
        category="Coding",
        priority="High",
        status="In Progress",
        start_date=today - timedelta(days=10),
        target_date=today + timedelta(days=12),
        progress=30,
    )
    task = Task(
        id=t_id,
        title="Database Migration Script",
        goal_id=g_id,
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    habit = Habit(
        id=h_id,
        name="Daily Code Review",
        category="Coding",
        frequency="Daily",
        base_streak=4,
    )
    # Log 3 timeblocks with actuals: 60 planned, 90 actual -> bias = 1.5
    tb1 = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="Deep Work Session 1",
        time="09:00 AM",
        block_date=today - timedelta(days=1),
        duration_minutes=60,
        actual_duration_minutes=90,
        status="Completed",
    )
    tb2 = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="Deep Work Session 2",
        time="11:00 AM",
        block_date=today - timedelta(days=2),
        duration_minutes=60,
        actual_duration_minutes=90,
        status="Completed",
    )
    tb3 = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="Deep Work Session 3",
        time="02:00 PM",
        block_date=today - timedelta(days=3),
        duration_minutes=60,
        actual_duration_minutes=90,
        status="Completed",
    )
    # Postponement activity
    act = ActivityLog(
        id=f"act_{uuid.uuid4().hex[:10]}",
        event_type="TASK_POSTPONED",
        entity_id=t_id,
        entity_type="Task",
        timestamp=datetime.now(timezone.utc),
    )
    db_session.add_all([goal, task, habit, tb1, tb2, tb3, act])
    db_session.commit()

    ctx = build_productivity_context(db_session, reference_date=today)
    assert len(ctx.pending_tasks) >= 1
    assert len(ctx.active_goals) >= 1
    assert len(ctx.habits) >= 1
    assert ctx.task_postpones.get(t_id) == 1
    assert ctx.bias_factor == 1.5
    assert ctx.goal_map[g_id].title == "Q4 System Release"

def test_priority_scorer_mathematical_breakdown():
    """
    Verifies that calculate_recommendation_priority generates bounded (0-100) scores
    with transparent mathematical breakdowns across urgency, importance, goal, habit,
    and behavioral weighting.
    """
    # Overdue high priority task tied to goal with postponements
    high_res = calculate_recommendation_priority(
        urgency_days=-2,
        importance_level="High",
        goal_relevance_pts=15.0,
        postpone_count=2,
        bias_factor=1.4,
        historical_acceptance_rate=0.75,
    )
    assert high_res.level == "HIGH"
    assert high_res.score >= 70.0
    assert high_res.breakdown["urgency"] == 35.0
    assert high_res.breakdown["importance"] == 35.0
    assert high_res.breakdown["goal_relevance"] == 15.0
    assert high_res.breakdown["behavioral_weight"] > 5.0
    assert high_res.score <= 100.0

    # Low priority distant task
    low_res = calculate_recommendation_priority(
        urgency_days=14,
        importance_level="Low",
        goal_relevance_pts=0.0,
        habit_impact_pts=0.0,
        postpone_count=0,
        bias_factor=1.0,
        historical_acceptance_rate=0.5,
    )
    assert low_res.level == "LOW"
    assert low_res.score < 40.0
    assert low_res.breakdown["urgency"] == 6.0
    assert low_res.breakdown["importance"] == 8.0

def test_explainable_recommendation_four_facets(client, db_session):
    """
    Verifies that every generated recommendation includes the 4 explainability facets:
    - what_happened
    - why_generated
    - suggested_action
    - why_prioritize
    both in structured JSON format and human-readable reason text.
    """
    today = date.today()
    t_id = f"t_{uuid.uuid4().hex[:10]}"
    task = Task(
        id=t_id,
        title="Payment Gateway Integration",
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
    items = resp.json()["items"]
    target = next((i for i in items if i["entity_id"] == t_id), None)
    assert target is not None

    payload = target["action_payload"]
    assert "explanation" in payload
    expl = payload["explanation"]
    assert "what_happened" in expl and len(expl["what_happened"]) > 5
    assert "why_generated" in expl and len(expl["why_generated"]) > 5
    assert "suggested_action" in expl and len(expl["suggested_action"]) > 5
    assert "why_prioritize" in expl and len(expl["why_prioritize"]) > 5
    assert "priority_score" in payload
    assert "score_breakdown" in payload

def test_goal_progress_intelligence_safe_timeline_buffer(client, db_session):
    """
    Verifies that goals with ample time (> 30 days left) do NOT prematurely trigger panic,
    while goals with <= 14 days and < 50% progress trigger actionable interventions.
    """
    today = date.today()
    # Goal A: distant deadline (60 days left, 10% progress) -> should NOT trigger lagging panic
    g_distant_id = f"g_{uuid.uuid4().hex[:10]}"
    g_distant = Goal(
        id=g_distant_id,
        title="Long Range Architecture Evolution",
        goal_type="Long-Term",
        category="Coding",
        status="In Progress",
        start_date=today - timedelta(days=5),
        target_date=today + timedelta(days=60),
        progress=10,
    )
    # Linked task so it doesn't trigger 0-task structure rule
    t_linked = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Research Tech Stack",
        goal_id=g_distant_id,
        task_type="Daily",
        category="Coding",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=30),
    )

    # Goal B: urgent deadline (10 days left, 20% progress) -> SHOULD trigger lagging recommendation
    g_urgent_id = f"g_{uuid.uuid4().hex[:10]}"
    g_urgent = Goal(
        id=g_urgent_id,
        title="Customer Beta Launch",
        goal_type="Short-Term",
        category="Career",
        status="In Progress",
        start_date=today - timedelta(days=20),
        target_date=today + timedelta(days=10),
        progress=20,
    )
    t_urgent = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Onboarding Walkthrough",
        goal_id=g_urgent_id,
        task_type="Daily",
        category="Career",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=5),
    )

    db_session.add_all([g_distant, t_linked, g_urgent, t_urgent])
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    items = resp.json()["items"]

    # Goal B should have a lagging alert
    urgent_rec = next((i for i in items if i["entity_id"] == g_urgent_id and "Lagging" in i["title"]), None)
    assert urgent_rec is not None
    assert urgent_rec["priority"] == "HIGH"

    # Goal A should NOT have a lagging alert
    distant_rec = next((i for i in items if i["entity_id"] == g_distant_id and "Lagging" in i["title"]), None)
    assert distant_rec is None

def test_habit_behavior_streak_and_recovery(client, db_session):
    """
    Verifies habit behavior analysis:
    - Active streak defense (streak >= 3) generates HIGH priority streak alert.
    - Dropped consistency (missed >= 2 of 4 days) generates recovery suggestion with micro-session.
    """
    today = date.today()
    # Habit 1: Active 5-day streak
    h1_id = f"h_{uuid.uuid4().hex[:10]}"
    h1 = Habit(
        id=h1_id,
        name="Nightly Reflection",
        category="Personal",
        frequency="Daily",
        base_streak=5,
    )

    # Habit 2: Decaying habit with 2 missed days
    h2_id = f"h_{uuid.uuid4().hex[:10]}"
    h2 = Habit(
        id=h2_id,
        name="Hydration Routine",
        category="Health",
        frequency="Daily",
        base_streak=1,
    )
    # Log only 1 completed day in the last 4 days
    hl = HabitLog(
        id=f"hl_{uuid.uuid4().hex[:10]}",
        habit_id=h2_id,
        log_date=today - timedelta(days=3),
        completed=True,
    )

    db_session.add_all([h1, h2, hl])
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    items = resp.json()["items"]

    # Habit 1: Streak protection
    h1_rec = next((i for i in items if i["entity_id"] == h1_id), None)
    assert h1_rec is not None
    assert "Protect Streak" in h1_rec["title"]
    assert h1_rec["priority"] == "HIGH"

    # Habit 2: Momentum recovery
    h2_rec = next((i for i in items if i["entity_id"] == h2_id), None)
    assert h2_rec is not None
    assert "Rebuild Momentum" in h2_rec["title"]
    assert h2_rec["priority"] == "MEDIUM"

def test_workload_balancing_and_non_destructive_reschedule(client, db_session):
    """
    Verifies workload balancing:
    Overloaded days (> 360 min) suggest moving movable tasks to lighter days (< 240 min).
    Original user dates are preserved until approved.
    """
    today = date.today()
    # Heavy day today: 400 minutes scheduled
    t_fixed = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Board Presentation",
        task_type="Daily",
        category="Career",
        start_date=today,
        due_date=today,
        priority="High",
        status="Pending",
    )
    t_movable = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Internal Team Retrospective",
        task_type="Daily",
        category="Career",
        start_date=today,
        due_date=today + timedelta(days=4),
        priority="Low",
        status="Pending",
    )
    tb_heavy = DailyTimeblock(
        id=f"tb_{uuid.uuid4().hex[:10]}",
        title="Extended Sprint Workshop",
        time="09:00 AM",
        block_date=today,
        duration_minutes=400,
        status="Pending",
    )
    # Tomorrow is light (0 min)
    db_session.add_all([t_fixed, t_movable, tb_heavy])
    db_session.commit()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    items = resp.json()["items"]

    wl_rec = next((i for i in items if i["type"] == "WORKLOAD_BALANCE" and i["entity_id"] == t_movable.id), None)
    assert wl_rec is not None
    assert "Balance Workload" in wl_rec["title"]
    assert wl_rec["action_payload"]["source_date"] == str(today)
    assert wl_rec["action_payload"]["suggested_date"] == str(today + timedelta(days=1))
    # Original task start date must remain unmutated until user explicitly executes
    t_check = db_session.query(Task).filter(Task.id == t_movable.id).first()
    assert t_check.start_date == today

def test_intelligent_recommendation_sorting_order(client, db_session):
    """
    Verifies that recommendations are sorted in descending order of priority_score,
    ensuring critical overdue and deadline risk items appear at the very top.
    """
    today = date.today()
    # 1. Critical Overdue High Task
    t_overdue = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Zero-Day Vulnerability Patch",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2),
    )
    # 2. Medium Task Due Today
    t_today = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Update Release Notes",
        task_type="Daily",
        category="Coding",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add_all([t_overdue, t_today])
    db_session.commit()

    resp = client.get("/api/recommendations?status=PENDING")
    assert resp.status_code == 200
    items = resp.json()["items"]

    idx_overdue = next((idx for idx, i in enumerate(items) if i["entity_id"] == t_overdue.id), None)
    idx_today = next((idx for idx, i in enumerate(items) if i["entity_id"] == t_today.id), None)

    assert idx_overdue is not None
    assert idx_today is not None
    assert idx_overdue < idx_today
    score_overdue = items[idx_overdue]["action_payload"]["priority_score"]
    score_today = items[idx_today]["action_payload"]["priority_score"]
    assert score_overdue >= score_today
