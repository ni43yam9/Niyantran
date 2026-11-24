import pytest
import uuid
from datetime import date, datetime, timedelta, timezone

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.models.recommendation import Recommendation

from backend.app.services.predictive.data_preparation import prepare_predictive_dataset
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import calculate_confidence_score, classify_risk
from backend.app.services.predictive.ml_models import MachineLearningPredictor
from backend.app.services.predictive.predictive_engine import predictive_engine
from backend.app.services.predictive.prediction_evaluator import evaluate_matured_predictions


def test_data_preparation_and_safety(db_session):
    today = date.today()

    # Initial state
    container = prepare_predictive_dataset(db_session, reference_date=today)
    assert container.total_observations >= 0
    assert isinstance(container.completed_tasks, list)

    # Insert 1 completed task and 1 active task with explicit IDs and valid constraints
    t1 = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Completed Task 1",
        category="Coding",
        priority="High",
        status="Completed",
        start_date=today - timedelta(days=2),
        due_date=today,
        completed_at=datetime.now(timezone.utc),
    )
    t2 = Task(
        id=f"t_{uuid.uuid4().hex[:10]}",
        title="Pending Task 1",
        category="Academic",
        priority="Medium",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=2),
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    container2 = prepare_predictive_dataset(db_session, reference_date=today)
    assert container2.completed_task_count >= 1
    assert any(t.id == t1.id for t in container2.completed_tasks)
    assert any(t.id == t2.id for t in container2.active_tasks)


def test_feature_extraction_bias_and_velocity(db_session):
    today = date.today()

    # Create 3 timeblocks with actual vs planned durations to test empirical bias
    for i in range(3):
        t = Task(
            id=f"t_bias_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Bias Task {i}",
            category="Coding",
            priority="Medium",
            status="Completed",
            start_date=today - timedelta(days=5),
            due_date=today,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(t)
        db_session.commit()

        tb = DailyTimeblock(
            id=f"tb_bias_{i}_{uuid.uuid4().hex[:6]}",
            block_date=today,
            title=f"Bias Block {i}",
            time="10:00 AM",
            duration_minutes=100,
            actual_duration_minutes=150,  # 1.5x bias
            task_id=t.id,
            status="Completed",
        )
        db_session.add(tb)

    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)
    tf = extractor.extract_task_features()

    assert tf["is_bias_heuristic"] is False
    assert tf["bias_sample_size"] >= 3
    assert tf["estimation_bias_ratio"] >= 1.4


def test_deadline_risk_predictor(db_session):
    today = date.today()

    # Overdue task -> CRITICAL risk
    overdue_task = Task(
        id=f"t_overdue_{uuid.uuid4().hex[:8]}",
        title="Severely Overdue Task",
        category="Academic",
        priority="High",
        status="Pending",
        start_date=today - timedelta(days=7),
        due_date=today - timedelta(days=3),
    )
    # Upcoming task with plenty of time -> LOW risk
    comfortable_task = Task(
        id=f"t_comfortable_{uuid.uuid4().hex[:8]}",
        title="Comfortable Future Task",
        category="Reading",
        priority="Low",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=14),
    )
    db_session.add_all([overdue_task, comfortable_task])
    db_session.commit()

    # Add a postponement activity log for overdue task
    act = ActivityLog(
        id=f"act_post_{uuid.uuid4().hex[:8]}",
        event_type="TASK_POSTPONED",
        entity_type="task",
        entity_id=overdue_task.id,
        original_date=today - timedelta(days=5),
        new_date=today - timedelta(days=3),
    )
    db_session.add(act)
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)
    ml_pred = MachineLearningPredictor()

    from backend.app.services.predictive.predictors.deadline_predictor import predict_deadline_risks
    insights = predict_deadline_risks(container, extractor, ml_pred)

    overdue_ins = next((i for i in insights if i["entity_id"] == overdue_task.id), None)
    comf_ins = next((i for i in insights if i["entity_id"] == comfortable_task.id), None)

    assert overdue_ins is not None
    assert overdue_ins["risk_score"] == 100.0
    assert overdue_ins["risk_category"] == "CRITICAL"
    assert overdue_ins["predicted_outcome"] == "OVERDUE"

    assert comf_ins is not None
    assert comf_ins["risk_score"] < 40.0
    assert comf_ins["risk_category"] in ("LOW", "INSUFFICIENT_DATA")
    assert comf_ins["predicted_outcome"] == "ON_TIME"


def test_goal_risk_predictor(db_session):
    today = date.today()

    # Stalled goal (10 days elapsed, 0% progress)
    stalled_goal = Goal(
        id=f"g_stalled_{uuid.uuid4().hex[:8]}",
        title="Stalled Career Goal",
        goal_type="Short-Term",
        category="Career",
        priority="High",
        status="In Progress",
        progress=0,
        start_date=today - timedelta(days=10),
        target_date=today + timedelta(days=5),
    )
    # On-track goal (80% completed with 10 days left)
    on_track_goal = Goal(
        id=f"g_healthy_{uuid.uuid4().hex[:8]}",
        title="Healthy Progress Goal",
        goal_type="Short-Term",
        category="Coding",
        priority="Medium",
        status="In Progress",
        progress=80,
        start_date=today - timedelta(days=20),
        target_date=today + timedelta(days=10),
    )
    db_session.add_all([stalled_goal, on_track_goal])
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    from backend.app.services.predictive.predictors.goal_risk_predictor import predict_goal_risks
    insights = predict_goal_risks(container, extractor)

    stalled_ins = next((i for i in insights if i["entity_id"] == stalled_goal.id), None)
    healthy_ins = next((i for i in insights if i["entity_id"] == on_track_goal.id), None)

    assert stalled_ins is not None
    assert stalled_ins["risk_score"] >= 75.0
    assert stalled_ins["risk_category"] in ("CRITICAL", "HIGH")
    assert stalled_ins["predicted_outcome"] in ("STALLED", "AT_RISK")

    assert healthy_ins is not None
    assert healthy_ins["risk_score"] <= 30.0
    assert healthy_ins["risk_category"] == "LOW"
    assert healthy_ins["predicted_outcome"] == "ON_TRACK"


def test_workload_forecaster(db_session):
    today = date.today()
    bottleneck_date = today + timedelta(days=2)

    # Schedule 5 tasks on the same due date
    tasks = []
    for i in range(5):
        t = Task(
            id=f"t_cluster_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Clustered Task {i}",
            category="Academic",
            priority="Medium",
            status="Pending",
            start_date=today,
            due_date=bottleneck_date,
        )
        tasks.append(t)
    db_session.add_all(tasks)
    db_session.commit()

    # Create timeblocks for each task with duration = 90 mins (total 450 mins > 240 mins)
    for t in tasks:
        tb = DailyTimeblock(
            id=f"tb_cl_{t.id}",
            block_date=bottleneck_date,
            title=t.title,
            time="11:00 AM",
            duration_minutes=90,
            task_id=t.id,
            status="Pending",
        )
        db_session.add(tb)
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    from backend.app.services.predictive.predictors.workload_forecaster import forecast_workload_distribution
    insights = forecast_workload_distribution(container, extractor)

    bottleneck_ins = next(
        (i for i in insights if i["horizon_date"] == bottleneck_date and i["predicted_outcome"] == "BOTTLENECK"),
        None
    )
    assert bottleneck_ins is not None
    assert bottleneck_ins["risk_score"] >= 60.0
    assert bottleneck_ins["risk_category"] in ("HIGH", "CRITICAL")
    assert "Workload Bottleneck" in bottleneck_ins["title"]


def test_habit_decay_predictor(db_session):
    today = date.today()

    # Habit with base_streak of 10 days, but no logs in DB for last 3 days
    vulnerable_habit = Habit(
        id=f"h_vuln_{uuid.uuid4().hex[:8]}",
        name="Vulnerable Daily Meditation",
        target="15m",
        category="Health",
        frequency="Daily",
        base_streak=10,
    )
    db_session.add(vulnerable_habit)
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    from backend.app.services.predictive.predictors.habit_predictor import predict_habit_decay
    insights = predict_habit_decay(container, extractor)

    habit_ins = next((i for i in insights if i["entity_id"] == vulnerable_habit.id), None)
    assert habit_ins is not None
    assert habit_ins["predicted_outcome"] == "STREAK_BREAK"
    assert habit_ins["risk_category"] == "HIGH"
    assert habit_ins["risk_score"] >= 70.0


def test_completion_feasibility_estimator(db_session):
    today = date.today()

    # Backlog of tasks totaling high workload
    tasks = []
    for i in range(8):
        t = Task(
            id=f"t_heavy_{i}_{uuid.uuid4().hex[:6]}",
            title=f"Heavy Backlog Task {i}",
            category="Career",
            priority="High",
            status="Pending",
            start_date=today,
            due_date=today + timedelta(days=5),
        )
        tasks.append(t)
    db_session.add_all(tasks)
    db_session.commit()

    for t in tasks:
        tb = DailyTimeblock(
            id=f"tb_heavy_{t.id}",
            block_date=today,
            title=t.title,
            time="02:00 PM",
            duration_minutes=300,  # 5 hours per task * 8 = 40 hours!
            task_id=t.id,
            status="Pending",
        )
        db_session.add(tb)
    db_session.commit()

    container = prepare_predictive_dataset(db_session, reference_date=today)
    extractor = FeatureExtractor(container)

    from backend.app.services.predictive.predictors.completion_estimator import estimate_queue_completion_feasibility
    insights = estimate_queue_completion_feasibility(container, extractor)

    assert len(insights) == 1
    assert insights[0]["predicted_outcome"] in ("UNREALISTIC_QUEUE", "STRETCH_QUEUE")
    assert insights[0]["risk_score"] >= 60.0


def test_productivity_trend_predictor_cold_start_and_sufficient(db_session):
    today = date.today()

    # Test Cold Start (empty container)
    empty_container = prepare_predictive_dataset(db_session, reference_date=today)
    if not empty_container.has_sufficient_history:
        extractor = FeatureExtractor(empty_container)
        from backend.app.services.predictive.predictors.productivity_predictor import predict_productivity_trend
        cold_insights = predict_productivity_trend(empty_container, extractor)
        assert len(cold_insights) == 1
        assert cold_insights[0]["risk_category"] == "INSUFFICIENT_DATA"
        assert cold_insights[0]["has_sufficient_data"] is False
        assert cold_insights[0]["confidence_score"] <= 0.35

    # Add 5 completed tasks to unlock trajectory
    for i in range(5):
        t = Task(
            id=f"t_hist_{i}_{uuid.uuid4().hex[:6]}",
            title=f"History Task {i}",
            category="Coding",
            priority="Medium",
            status="Completed",
            start_date=today - timedelta(days=7),
            due_date=today - timedelta(days=1),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(t)
    db_session.commit()

    rich_container = prepare_predictive_dataset(db_session, reference_date=today)
    assert rich_container.has_sufficient_history is True
    rich_extractor = FeatureExtractor(rich_container)
    from backend.app.services.predictive.predictors.productivity_predictor import predict_productivity_trend
    rich_insights = predict_productivity_trend(rich_container, rich_extractor)
    assert len(rich_insights) == 1
    assert rich_insights[0]["has_sufficient_data"] is True
    assert rich_insights[0]["predicted_outcome"] in ("IMPROVING", "STABLE", "DECLINING")


def test_ml_model_activation_threshold(db_session):
    today = date.today()
    ml_pred = MachineLearningPredictor()

    # Case 1: N < 15 -> Not eligible, falls back to statistical
    tasks_sparse = [
        Task(
            id=f"t_sparse_{i}",
            title=f"Task {i}",
            category="Coding",
            status="Completed",
            start_date=today - timedelta(days=3),
            due_date=today,
            completed_at=datetime.now(timezone.utc)
        )
        for i in range(5)
    ]
    eligible, reason = ml_pred.evaluate_training_eligibility(tasks_sparse)
    assert eligible is False
    assert "N=5 < 15" in reason

    # Case 2: N >= 15 with balanced classes -> Eligible and trains
    tasks_rich = []
    for i in range(16):
        is_overdue = (i % 2 == 0)
        completed_offset = timedelta(days=1) if is_overdue else timedelta(days=-1)
        t = Task(
            id=f"t_rich_{i}_{uuid.uuid4().hex[:6]}",
            title=f"ML Task {i}",
            category="Coding",
            status="Completed",
            priority="High" if i % 2 == 0 else "Medium",
            start_date=today - timedelta(days=10),
            due_date=today - timedelta(days=2),
            completed_at=datetime.combine(today - timedelta(days=2) + completed_offset, datetime.min.time(), tzinfo=timezone.utc),
        )
        tasks_rich.append(t)

    eligible_rich, reason_rich = ml_pred.evaluate_training_eligibility(tasks_rich)
    assert eligible_rich is True

    trained = ml_pred.train_deadline_model(tasks_rich)
    assert trained is True
    assert ml_pred.is_trained is True
    assert ml_pred.model_version == "sklearn_logistic_v1"

    prob = ml_pred.predict_deadline_overdue_prob(
        estimated_duration=120,
        postpone_count=2,
        priority="High",
        buffer_ratio=0.5
    )
    assert 0.0 <= prob <= 1.0


def test_predictive_persistence_and_deduplication(db_session):
    today = date.today()

    t = Task(
        id=f"t_dedup_{uuid.uuid4().hex[:8]}",
        title="Deduplication Task",
        category="Academic",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add(t)
    db_session.commit()

    # Run cycle 1
    recs1 = predictive_engine.generate_all_predictions(db_session, reference_date=today, persist=True)
    count1 = db_session.query(PredictiveInsight).filter(PredictiveInsight.evaluation_status == "PENDING").count()

    # Run cycle 2 immediately
    recs2 = predictive_engine.generate_all_predictions(db_session, reference_date=today, persist=True)
    count2 = db_session.query(PredictiveInsight).filter(PredictiveInsight.evaluation_status == "PENDING").count()

    # Deduplication check: count should NOT double
    assert count1 == count2


def test_prediction_horizon_evaluation(db_session):
    today = date.today()

    past_date = today - timedelta(days=2)
    t = Task(
        id=f"t_eval_past_{uuid.uuid4().hex[:8]}",
        title="Unfinished Past Task",
        category="Coding",
        priority="High",
        status="Pending",
        start_date=today - timedelta(days=5),
        due_date=past_date,
    )
    db_session.add(t)
    db_session.commit()

    insight_matured = PredictiveInsight(
        prediction_type="DEADLINE_RISK",
        entity_type="Task",
        entity_id=t.id,
        risk_score=95.0,
        risk_category="CRITICAL",
        confidence_score=0.88,
        has_sufficient_data=True,
        title=f"Deadline Risk: {t.title}",
        summary="Task is predicted to be overdue",
        horizon_date=past_date,
        predicted_outcome="OVERDUE",
        evaluation_status="PENDING",
    )

    future_date = today + timedelta(days=5)
    insight_immature = PredictiveInsight(
        prediction_type="DEADLINE_RISK",
        entity_type="Task",
        entity_id=t.id,
        risk_score=60.0,
        risk_category="HIGH",
        confidence_score=0.80,
        has_sufficient_data=True,
        title=f"Future Risk: {t.title}",
        summary="Future task",
        horizon_date=future_date,
        predicted_outcome="OVERDUE",
        evaluation_status="PENDING",
    )
    db_session.add_all([insight_matured, insight_immature])
    db_session.commit()

    result = evaluate_matured_predictions(db_session, reference_date=today)

    db_session.refresh(insight_matured)
    db_session.refresh(insight_immature)

    assert insight_immature.evaluation_status == "PENDING"
    assert insight_immature.actual_outcome is None

    assert insight_matured.evaluation_status == "EVALUATED"
    assert insight_matured.actual_outcome == "OVERDUE"
    assert insight_matured.predicted_outcome == insight_matured.actual_outcome
    assert "ACCURATE" in insight_matured.evaluation_notes


def test_predictive_recommendation_bridge(db_session):
    today = date.today()

    t = Task(
        id=f"t_bridge_{uuid.uuid4().hex[:8]}",
        title="Bridge Urgent Task",
        category="Reading",
        priority="High",
        status="Pending",
        start_date=today,
        due_date=today + timedelta(days=1),
    )
    db_session.add(t)
    db_session.commit()

    insight = PredictiveInsight(
        prediction_type="DEADLINE_RISK",
        entity_type="Task",
        entity_id=t.id,
        risk_score=85.0,
        risk_category="CRITICAL",
        confidence_score=0.85,
        has_sufficient_data=True,
        title=f"Deadline Risk: {t.title}",
        summary="Task is at critical breach risk",
        suggested_action="Schedule focus block now.",
        horizon_date=t.due_date,
        predicted_outcome="OVERDUE",
        evaluation_status="PENDING",
    )
    db_session.add(insight)
    db_session.commit()

    spawned = predictive_engine.bridge_predictive_recommendations(db_session, reference_date=today)
    assert spawned >= 1

    rec = (
        db_session.query(Recommendation)
        .filter(Recommendation.entity_id == t.id)
        .first()
    )
    assert rec is not None
    assert rec.status == "PENDING"
    assert "[Predictive]" in rec.title
    assert rec.action_payload["predictive_insight_id"] == insight.id

    spawned_again = predictive_engine.bridge_predictive_recommendations(db_session, reference_date=today)
    assert spawned_again == 0
