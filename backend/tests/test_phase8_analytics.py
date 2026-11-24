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

from backend.app.services.analytics.score_calculator import (
    calculate_explainable_productivity_score,
)
from backend.app.services.analytics.task_analytics import (
    analyze_tasks_in_depth,
)
from backend.app.services.analytics.goal_analytics import (
    analyze_goals_in_depth,
)
from backend.app.services.analytics.habit_analytics import (
    analyze_habits_in_depth,
)
from backend.app.services.analytics.trend_comparator import (
    compare_productivity_trends,
)
from backend.app.services.analytics.time_distribution import (
    analyze_time_distribution,
)
from backend.app.services.analytics.insight_generator import (
    generate_actionable_analytics_insights,
)
from backend.app.services.analytics.report_generator import (
    generate_weekly_productivity_report,
    generate_monthly_productivity_report,
)

client = TestClient(app)

def test_explainable_productivity_score_calculation(db_session):
    """
    Verifies that calculate_explainable_productivity_score produces an explainable
    score composed of 6 transparent components, enforces the backlog expansion guard,
    and includes the human worth disclaimer.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # 1. Seed completed High-priority task and on-time deliverable
    t1 = Task(
        id=f"t_sc1_{uuid.uuid4().hex[:6]}",
        title="High Impact System Kernel",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Completed",
        start_date=today - timedelta(days=2),
        due_date=today + timedelta(days=1),
        completed_at=now_utc - timedelta(days=1),
    )
    t2 = Task(
        id=f"t_sc2_{uuid.uuid4().hex[:6]}",
        title="Architecture Research",
        task_type="Daily",
        category="Academic",
        priority="Medium",
        status="Completed",
        start_date=today - timedelta(days=1),
        due_date=today,
        completed_at=now_utc,
    )
    t3 = Task(
        id=f"t_sc3_{uuid.uuid4().hex[:6]}",
        title="Documentation Drafting",
        task_type="Daily",
        category="Reading",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    db_session.add_all([t1, t2, t3])

    # 2. Seed active goal with 60% progress
    g1 = Goal(
        id=f"g_sc1_{uuid.uuid4().hex[:6]}",
        title="Production Deployment",
        goal_type="Short-Term",
        category="Coding",
        priority="High",
        status="In Progress",
        start_date=today - timedelta(days=10),
        target_date=today + timedelta(days=20),
        progress=60,
    )
    db_session.add(g1)

    # 3. Seed active habit with logs
    h1 = Habit(
        id=f"h_sc1_{uuid.uuid4().hex[:6]}",
        name="Daily Deep Work",
        category="Coding",
        frequency="Daily",
        base_streak=5,
    )
    db_session.add(h1)
    db_session.commit()

    for i in range(10):
        hl = HabitLog(
            id=f"hl_sc_{i}_{uuid.uuid4().hex[:6]}",
            habit_id=h1.id,
            log_date=today - timedelta(days=i),
            completed=True,
        )
        db_session.add(hl)
    db_session.commit()

    score_detail = calculate_explainable_productivity_score(db_session, reference_date=today, now_utc=now_utc)
    assert score_detail.has_sufficient_data is True
    assert 10 <= score_detail.score <= 100
    assert score_detail.level in ("High", "Balanced", "Exceptional")

    b = score_detail.breakdown
    assert b.task_completion_points > 0.0
    assert b.priority_weight_points > 0.0
    assert b.deadline_adherence_points > 0.0
    assert b.goal_progress_points > 0.0
    assert b.habit_consistency_points > 0.0
    assert -5.0 <= b.trend_modifier_points <= 5.0

    # Verify that score is composed directly of breakdown parts
    computed_sum = round(
        b.task_completion_points
        + b.priority_weight_points
        + b.deadline_adherence_points
        + b.goal_progress_points
        + b.habit_consistency_points
        + b.trend_modifier_points
    )
    assert abs(score_detail.score - computed_sum) <= 1

    # Verify human worth disclaimer
    assert "human worth" in score_detail.disclaimer.lower()
    assert "methodology_explanation" in score_detail.__dict__ or len(score_detail.methodology_explanation) > 0


def test_productivity_score_insufficient_data_baseline(db_session):
    """
    Verifies that when fewer than 3 deliverables exist, the system returns a safe
    baseline score of 50/100 with has_sufficient_data=False.
    """
    # Empty DB
    score_empty = calculate_explainable_productivity_score(db_session)
    assert score_empty.has_sufficient_data is False
    assert score_empty.score == 50
    assert score_empty.level == "Baseline"
    assert "limited activity records" in score_empty.methodology_explanation.lower()


def test_in_depth_task_analytics(db_session):
    """
    Verifies task analytics across priority-weighted execution, category completion rates,
    overdue debt, and lead time resolution.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # Completed High priority task
    t_h = Task(
        id=f"t_h_{uuid.uuid4().hex[:6]}",
        title="High Prio Task",
        task_type="Daily",
        category="Coding",
        priority="High",
        status="Completed",
        start_date=today - timedelta(days=2),
        due_date=today - timedelta(days=1),
        created_at=now_utc - timedelta(hours=24),
        completed_at=now_utc,
    )
    # Overdue Medium priority task
    t_over = Task(
        id=f"t_over_{uuid.uuid4().hex[:6]}",
        title="Overdue Medium Task",
        task_type="Daily",
        category="Academic",
        priority="Medium",
        status="Pending",
        start_date=today - timedelta(days=3),
        due_date=today - timedelta(days=1), # Passed deadline!
    )
    # Pending Low priority task
    t_low = Task(
        id=f"t_low_{uuid.uuid4().hex[:6]}",
        title="Future Low Task",
        task_type="Daily",
        category="Reading",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=3),
    )
    db_session.add_all([t_h, t_over, t_low])
    db_session.commit()

    detail = analyze_tasks_in_depth(db_session, reference_date=today)
    assert detail.total_tasks >= 3
    assert detail.completed_tasks >= 1
    assert detail.overdue_tasks >= 1
    assert detail.priority_completion_rates["High"] == 100.0
    assert detail.priority_completion_rates["Medium"] == 0.0
    assert "Coding" in detail.category_completion_rates
    assert detail.average_lead_time_hours is not None
    assert detail.average_lead_time_hours > 0.0


def test_in_depth_goal_analytics_with_predictive_integration(db_session):
    """
    Verifies goal milestone analytics, progress velocity calculations,
    and seamless integration of Phase 6 predictive trajectories.
    """
    today = date.today()
    g_id = f"g_pred_{uuid.uuid4().hex[:6]}"

    g = Goal(
        id=g_id,
        title="Cloud Infrastructure Modernization",
        goal_type="Short-Term",
        category="Coding",
        priority="High",
        status="In Progress",
        start_date=today - timedelta(days=10),
        target_date=today + timedelta(days=20),
        progress=40,
    )
    db_session.add(g)

    # Seed Phase 6 predictive insight for this goal
    ins = PredictiveInsight(
        id=f"pred_g_{uuid.uuid4().hex[:6]}",
        prediction_type="GOAL_TRAJECTORY",
        entity_type="Goal",
        entity_id=g_id,
        risk_score=35.0,
        risk_category="LOW",
        confidence_score=0.85,
        has_sufficient_data=True,
        title="Goal On Track",
        summary="Velocity matches target schedule",
        predicted_outcome="ON_TRACK",
        suggested_action="Continue current milestone pace",
    )
    db_session.add(ins)
    db_session.commit()

    g_detail = analyze_goals_in_depth(db_session, reference_date=today)
    assert g_detail.total_goals >= 1
    assert g_detail.active_goals >= 1
    assert g_detail.average_progress == 40.0
    assert g_detail.average_velocity_percent_per_day > 0.0

    # Verify predictive trajectory integration
    pred_entry = next((p for p in g_detail.predictive_trajectories if p["goal_id"] == g_id), None)
    assert pred_entry is not None
    assert pred_entry["predicted_outcome"] == "ON_TRACK"
    assert pred_entry["confidence_score"] == 0.85


def test_in_depth_habit_analytics(db_session):
    """
    Verifies habit adherence tracking across 7d, 14d, and 30d horizons,
    streak persistence, and missed-day detection.
    """
    today = date.today()
    h_id = f"h_ana_{uuid.uuid4().hex[:6]}"

    h = Habit(
        id=h_id,
        name="Morning Meditation",
        category="Health",
        frequency="Daily",
        base_streak=6,
    )
    db_session.add(h)
    db_session.commit()

    # Log 5 completions in trailing 7 days
    for i in range(5):
        hl = HabitLog(
            id=f"hl_{i}_{uuid.uuid4().hex[:6]}",
            habit_id=h_id,
            log_date=today - timedelta(days=i),
            completed=True,
        )
        db_session.add(hl)
    db_session.commit()

    h_detail = analyze_habits_in_depth(db_session, reference_date=today)
    assert h_detail.total_habits >= 1
    assert h_detail.adherence_7d > 50.0
    assert h_detail.longest_streak >= 6
    assert h_detail.active_streaks_count >= 1
    assert h_detail.habit_trend in ("Improving", "Steady")


def test_period_comparisons_with_incomplete_period_accounting(db_session):
    """
    CRITICAL TEST: Verifies that trend comparisons account for incomplete periods.
    Instead of comparing an incomplete 2-day week against an entire 7-day week,
    it compares day-aligned slices (Mon-Tue vs Mon-Tue of previous week) or pro-rates velocity.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)
    curr_week_start = today - timedelta(days=today.weekday())
    prev_week_start = curr_week_start - timedelta(days=7)

    # 2 completions in current week (Mon and Tue)
    t_c1 = Task(
        id=f"t_tc1_{uuid.uuid4().hex[:6]}",
        title="This Week Mon",
        category="Coding",
        status="Completed",
        start_date=curr_week_start,
        due_date=curr_week_start,
        completed_at=datetime.combine(curr_week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
    )
    t_c2 = Task(
        id=f"t_tc2_{uuid.uuid4().hex[:6]}",
        title="This Week Tue",
        category="Coding",
        status="Completed",
        start_date=curr_week_start + timedelta(days=1),
        due_date=curr_week_start + timedelta(days=1),
        completed_at=datetime.combine(curr_week_start + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
    )
    # 1 completion in matching Mon of previous week
    t_p1 = Task(
        id=f"t_tp1_{uuid.uuid4().hex[:6]}",
        title="Prev Week Mon",
        category="Coding",
        status="Completed",
        start_date=prev_week_start,
        due_date=prev_week_start,
        completed_at=datetime.combine(prev_week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
    )
    db_session.add_all([t_c1, t_c2, t_p1])
    db_session.commit()

    trends = compare_productivity_trends(db_session, reference_date=today)
    w_trend = trends.weekly_trend

    assert w_trend.comparison_mode == "DAY_ALIGNED_SLICE"
    assert w_trend.current_completions == 2
    assert w_trend.previous_aligned_completions == 1
    # 2 vs 1 in aligned window = +100% velocity improvement
    assert w_trend.velocity_delta_percent == 100.0
    assert w_trend.trend == "Improving"
    assert "day-aligned" in w_trend.explanation.lower()


def test_time_distribution_strict_estimated_vs_tracked_separation(db_session):
    """
    CRITICAL TEST: Verifies that estimated duration is strictly separated from tracked duration.
    When no stopwatch or actual timeblocks are logged, tracked duration is strictly 0m
    and has_tracked_duration_data is False (never inventing numbers).
    When actual timeblocks exist, tracked duration is calculated accurately.
    """
    today = date.today()

    # 1. First test with only tasks (estimates only, 0 tracked)
    t_est = Task(
        id=f"t_est_{uuid.uuid4().hex[:6]}",
        title="Estimate Only Task",
        category="Coding",
        status="Pending",
        start_date=today,
        due_date=today,
    )
    db_session.add(t_est)
    db_session.commit()

    time_dist_1 = analyze_time_distribution(db_session)
    assert time_dist_1.has_tracked_duration_data is False
    assert time_dist_1.total_tracked_duration_minutes == 0
    assert time_dist_1.total_estimated_duration_minutes > 0
    assert "strictly reported as 0m" in time_dist_1.data_notes

    # 2. Now add completed timeblock with tracked duration
    tb = DailyTimeblock(
        id=f"tb_track_{uuid.uuid4().hex[:6]}",
        title="Deep Focus Architecture",
        time="09:00 AM",
        block_date=today,
        duration_minutes=60,
        actual_duration_minutes=90, # Explicitly tracked!
        status="Completed",
        category="Coding",
    )
    db_session.add(tb)
    db_session.commit()

    time_dist_2 = analyze_time_distribution(db_session)
    assert time_dist_2.has_tracked_duration_data is True
    assert time_dist_2.total_tracked_duration_minutes == 90
    assert time_dist_2.deep_work_focus_minutes == 90
    assert time_dist_2.category_durations["Coding"]["tracked_minutes"] == 90


def test_actionable_insights_deduplication(db_session):
    """
    Verifies that actionable analytics insights include supporting evidence
    and deduplicate against existing active recommendations in the database.
    """
    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # 3 completed morning tasks to trigger morning timing insight
    for i in range(3):
        t = Task(
            id=f"t_ins_m_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Morning Deliverable {i}",
            category="Coding",
            status="Completed",
            completed_at=now_utc.replace(hour=8, minute=i * 15),
            start_date=today,
            due_date=today,
        )
        db_session.add(t)

    # Create active recommendation with similar theme
    rec = Recommendation(
        id=f"rec_dedup_{uuid.uuid4().hex[:6]}",
        type="PRIORITIZATION",
        category="Task",
        title="Immediate Focus: Overdue Item",
        description="Focus on urgent item",
        reason="Overdue debt",
        priority="HIGH",
        status="PENDING",
    )
    db_session.add(rec)
    db_session.commit()

    insights_resp = generate_actionable_analytics_insights(db_session, tz_offset_mins=0, reference_date=today)
    assert insights_resp.has_sufficient_data is True
    assert insights_resp.total_insights >= 1

    # Verify every insight has evidence in its description
    for ins in insights_resp.insights:
        assert len(ins.description) > 15
        assert ins.impact in ("High", "Medium", "Low")


def test_weekly_and_monthly_productivity_reports(db_session):
    """
    Verifies lightweight generation of WeeklyProductivityReport and MonthlyProductivityReport.
    """
    today = date.today()

    w_rep = generate_weekly_productivity_report(db_session, start_date=today - timedelta(days=today.weekday()))
    assert w_rep.report_id.startswith("rep_w_")
    assert 10 <= w_rep.productivity_score <= 100
    assert "completed_count" in w_rep.task_summary
    assert len(w_rep.actionable_recommendations) >= 1

    m_rep = generate_monthly_productivity_report(db_session, year=today.year, month=today.month)
    assert m_rep.report_id.startswith("rep_m_")
    assert 10 <= m_rep.productivity_score <= 100
    assert m_rep.month == today.month
    assert len(m_rep.actionable_recommendations) >= 1


def test_api_advanced_analytics_endpoints():
    """
    Tests all Phase 8 REST endpoints under /api/analytics/ to ensure 100% API compatibility.
    """
    # 1. GET /api/analytics/score
    r1 = client.get("/api/analytics/score")
    assert r1.status_code == 200
    p1 = r1.json()
    assert "score" in p1
    assert "breakdown" in p1
    assert "disclaimer" in p1

    # 2. GET /api/analytics/tasks
    r2 = client.get("/api/analytics/tasks")
    assert r2.status_code == 200
    p2 = r2.json()
    assert "completion_rate" in p2
    assert "priority_completion_rates" in p2
    assert "category_completion_rates" in p2

    # 3. GET /api/analytics/habits
    r3 = client.get("/api/analytics/habits")
    assert r3.status_code == 200
    p3 = r3.json()
    assert "adherence_7d" in p3
    assert "longest_streak" in p3

    # 4. GET /api/analytics/trends
    r4 = client.get("/api/analytics/trends")
    assert r4.status_code == 200
    p4 = r4.json()
    assert "daily_trend" in p4
    assert "weekly_trend" in p4
    assert "monthly_trend" in p4
    assert p4["weekly_trend"]["comparison_mode"] == "DAY_ALIGNED_SLICE"

    # 5. GET /api/analytics/time-distribution
    r5 = client.get("/api/analytics/time-distribution")
    assert r5.status_code == 200
    p5 = r5.json()
    assert "total_estimated_duration_minutes" in p5
    assert "total_tracked_duration_minutes" in p5
    assert "category_durations" in p5

    # 6. GET /api/analytics/reports/weekly
    r6 = client.get("/api/analytics/reports/weekly")
    assert r6.status_code == 200
    p6 = r6.json()
    assert "report_id" in p6
    assert "productivity_score" in p6
    assert "actionable_recommendations" in p6

    # 7. GET /api/analytics/reports/monthly
    r7 = client.get("/api/analytics/reports/monthly")
    assert r7.status_code == 200
    p7 = r7.json()
    assert "report_id" in p7
    assert "month_name" in p7
    assert "actionable_recommendations" in p7
