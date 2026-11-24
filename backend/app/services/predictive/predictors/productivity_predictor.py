from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)

def predict_productivity_trend(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor
) -> List[Dict[str, Any]]:
    """
    Forecasts weekly overall productivity trend (IMPROVING, STABLE, DECLINING)
    with strict data safety checks for cold-start scenarios.
    """
    task_features = extractor.extract_task_features()
    horizon_date = data.today + timedelta(days=7)

    # Check for insufficient historical observations
    if not data.has_sufficient_history:
        confidence = calculate_confidence_score(
            sample_size=data.total_observations,
            benchmark_size=15,
            base_confidence=0.50
        )
        return [{
            "prediction_type": "PRODUCTIVITY_TREND",
            "entity_type": "System",
            "entity_id": f"trend_{data.today.isoformat()}",
            "risk_score": 0.0,
            "risk_category": "INSUFFICIENT_DATA",
            "confidence_score": confidence,
            "has_sufficient_data": False,
            "title": "Productivity Forecast: Baseline Calibration",
            "summary": (
                f"Predictive engine has recorded {data.total_observations} historical events. "
                "At least 5 verifiable observations are required before establishing a statistical trajectory forecast."
            ),
            "supporting_evidence": [
                f"Total completed deliverables: {data.completed_task_count}",
                f"Activity log count: {data.activity_log_count}",
                f"Habit completions logged: {data.habit_log_count}",
                f"Timeblock sessions logged: {data.timeblock_count}",
            ],
            "contributing_factors": [
                "Early application usage lifecycle",
                "Historical baseline still accumulating observations",
            ],
            "suggested_action": "Continue tracking daily tasks and habits to unlock automated trajectory forecasting.",
            "time_horizon": "Upcoming 7 Days",
            "horizon_date": horizon_date,
            "predicted_outcome": "INSUFFICIENT_DATA",
            "model_version": "trend_v1",
        }]

    # We have sufficient observations (>= 5)
    # Evaluate momentum and backlog expansion vs true productivity
    velocity = task_features["daily_task_velocity"]
    overdue_count = len(data.overdue_tasks)
    total_active = len(data.active_tasks)
    is_expanding = task_features.get("is_backlog_expanding", False)
    comp_recent = task_features.get("completions_recent_7d", 0)
    comp_prev = task_features.get("completions_prev_7d", 0)
    creat_recent = task_features.get("creations_recent_7d", 0)
    creat_prev = task_features.get("creations_prev_7d", 0)

    # 1. Backlog Expansion Guard: Do not confuse increased task creation with increased productivity
    if is_expanding:
        predicted_outcome = "DECLINING"
        risk_score = 65.0
        category = "HIGH"
        summary = (
            f"Productivity trajectory is strained by backlog expansion: "
            f"{creat_recent} tasks created over the last 7 days vs only {comp_recent} completed. "
            f"Increased task creation does not represent increased productivity."
        )
        factors = [
            f"Task creation velocity ({creat_recent} tasks/wk) outpaces completion velocity ({comp_recent} tasks/wk)",
            "Accumulating unprioritized tasks creates cognitive friction and execution drag",
        ]
        action = "Halt adding non-urgent tasks; dedicate upcoming focus blocks to burning down existing backlog."
    elif overdue_count > total_active * 0.4 and overdue_count > 0:
        predicted_outcome = "DECLINING"
        risk_score = 70.0
        category = "HIGH"
        summary = "Productivity trend is under downward pressure due to accumulating overdue deliverables."
        factors = [
            f"{overdue_count} overdue task(s) creating cognitive friction and execution backlog",
            f"Daily velocity ({velocity:.2f} tasks/day) is lagging behind incoming demand",
        ]
        action = "Run a backlog recovery block to clear or reschedule aging overdue tasks."
    elif (velocity >= 1.0 or comp_recent > comp_prev) and overdue_count == 0:
        predicted_outcome = "IMPROVING"
        risk_score = 15.0
        category = "LOW"
        summary = "Productivity momentum is strong and projected to rise over the coming week."
        factors = [
            f"Healthy daily completion pace ({velocity:.2f} tasks/day; {comp_recent} tasks completed this week)",
            "Zero overdue tasks currently blocking execution flow",
        ]
        action = "Capitalize on current momentum by advancing key goal milestones."
    else:
        predicted_outcome = "STABLE"
        risk_score = 35.0
        category = "LOW"
        summary = "Productivity pace is steady with sustainable day-to-day throughput."
        factors = [
            f"Consistent throughput of approximately {round(velocity * 7, 1)} tasks per week",
            f"Manageable overdue count ({overdue_count} tasks)",
        ]
        action = "Maintain structured planning rituals to protect focus blocks."

    evidence = [
        f"Daily task completion pace: {velocity:.2f} tasks/day",
        f"Weekly completions (recent vs prior 7d): {comp_recent} vs {comp_prev}",
        f"Weekly task creations: {creat_recent} tasks (net backlog change: {creat_recent - comp_recent:+d})",
        f"Active backlog size: {total_active} tasks ({overdue_count} overdue)",
        f"Total historical observations: {data.total_observations}",
    ]

    confidence = calculate_confidence_score(
        sample_size=data.total_observations,
        benchmark_size=25,
        base_confidence=0.86
    )

    return [{
        "prediction_type": "PRODUCTIVITY_TREND",
        "entity_type": "System",
        "entity_id": f"trend_{data.today.isoformat()}",
        "risk_score": risk_score,
        "risk_category": category,
        "confidence_score": confidence,
        "has_sufficient_data": True,
        "title": f"Productivity Forecast: {predicted_outcome.title()}",
        "summary": summary,
        "supporting_evidence": evidence,
        "contributing_factors": factors,
        "suggested_action": action,
        "time_horizon": "Upcoming 7 Days",
        "horizon_date": horizon_date,
        "predicted_outcome": predicted_outcome,
        "model_version": "trend_v1",
    }]
