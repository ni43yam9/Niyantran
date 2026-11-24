from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)
from backend.app.services.predictive.ml_models import MachineLearningPredictor

def predict_deadline_risks(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor,
    ml_predictor: MachineLearningPredictor
) -> List[Dict[str, Any]]:
    """
    Evaluates all active tasks and estimates deadline breach risk.
    """
    task_features = extractor.extract_task_features()
    workload_features = extractor.extract_workload_features()

    bias_factor = task_features["estimation_bias_ratio"]
    is_heuristic = task_features["is_bias_heuristic"]
    daily_capacity = workload_features["daily_capacity_minutes"]

    insights = []

    for task in data.active_tasks:
        if not task.due_date:
            continue

        days_remaining = (task.due_date - data.today).days
        est_duration = extractor.get_task_estimated_duration(task)
        adjusted_duration = est_duration * bias_factor
        postpones = extractor.get_task_postpone_count(task)

        # Check if already overdue
        if days_remaining < 0:
            risk_score = 100.0
            category = "CRITICAL"
            predicted_outcome = "OVERDUE"
            factors = [
                f"Task is already {abs(days_remaining)} day(s) past its due date ({task.due_date})",
                f"Priority level is {task.priority}",
            ]
            if postpones > 0:
                factors.append(f"Previously postponed {postpones} time(s)")
            evidence = [
                "Estimated completion likelihood: 0.0%",
                f"Due date: {task.due_date}",
                f"Current status: {task.status}",
                f"Estimated effort: {est_duration}m (adjusted: {round(adjusted_duration)}m)",
            ]
            action = f"Reschedule or break down task '{task.title}' immediately to prevent cascading project delays."
            confidence = calculate_confidence_score(
                sample_size=task_features["bias_sample_size"] if not is_heuristic else 1,
                benchmark_size=10,
                base_confidence=0.95
            )
        else:
            # Task is upcoming
            avail_minutes = max(60.0, float(max(1, days_remaining) * daily_capacity))
            buffer_ratio = avail_minutes / max(30.0, adjusted_duration)

            overdue_prob = ml_predictor.predict_deadline_overdue_prob(
                estimated_duration=adjusted_duration,
                postpone_count=postpones,
                priority=task.priority or "Medium",
                buffer_ratio=buffer_ratio
            )

            risk_score = round(overdue_prob * 100.0, 1)
            category = classify_risk(risk_score, has_sufficient_data=data.has_sufficient_history)
            predicted_outcome = "OVERDUE" if risk_score >= 60.0 else "ON_TIME"

            factors = []
            if buffer_ratio < 1.0:
                factors.append(f"Available capacity buffer ratio is dangerously low ({round(buffer_ratio, 2)}x)")
            elif buffer_ratio < 1.5:
                factors.append(f"Tight scheduling buffer ({round(buffer_ratio, 2)}x capacity)")

            if postpones > 0:
                factors.append(f"Postponed {postpones} time(s) in past planning cycles")

            if is_heuristic:
                factors.append("Estimated using standard 1.25x effort bias heuristic due to early historical data")
            else:
                factors.append(f"Adjusted using your historical {bias_factor:.2f}x duration bias factor")

            completion_likelihood = round(max(2.0, min(98.0, (1.0 - overdue_prob) * 100.0)), 1)
            evidence = [
                f"Estimated completion likelihood: {completion_likelihood}%",
                f"Due date: {task.due_date} ({days_remaining} day(s) remaining)",
                f"Estimated effort: {est_duration}m (adjusted: {round(adjusted_duration)}m)",
                f"Projected breach probability: {round(overdue_prob * 100, 1)}%",
            ]

            action = (
                f"Schedule a dedicated {round(adjusted_duration)}m focus block before {task.due_date}."
                if risk_score >= 50.0
                else f"On track for completion by {task.due_date}."
            )

            sample_size = len(data.completed_tasks)
            confidence = calculate_confidence_score(
                sample_size=sample_size,
                benchmark_size=15,
                base_confidence=0.88
            )

        insights.append({
            "prediction_type": "DEADLINE_RISK",
            "entity_type": "Task",
            "entity_id": task.id,
            "risk_score": risk_score,
            "risk_category": category,
            "confidence_score": confidence,
            "has_sufficient_data": data.has_sufficient_history,
            "title": f"Deadline Risk: {task.title}",
            "summary": (
                f"Task '{task.title}' carries a {category.lower()} risk of missing its deadline "
                f"on {task.due_date} (Risk score: {risk_score}/100)."
            ),
            "supporting_evidence": evidence,
            "contributing_factors": factors,
            "suggested_action": action,
            "time_horizon": f"Until {task.due_date}",
            "horizon_date": task.due_date,
            "predicted_outcome": predicted_outcome,
            "model_version": ml_predictor.model_version,
        })

    return insights
