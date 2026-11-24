from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)

def estimate_queue_completion_feasibility(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor
) -> List[Dict[str, Any]]:
    """
    Evaluates whether the entire active deliverable backlog is feasible within
    sustainable weekly capacity.
    """
    task_features = extractor.extract_task_features()
    workload_features = extractor.extract_workload_features()

    bias_factor = task_features["estimation_bias_ratio"]
    daily_capacity = workload_features["daily_capacity_minutes"]
    weekly_capacity = daily_capacity * 5.0  # 5 working days

    active_tasks = data.active_tasks
    raw_backlog_mins = sum(extractor.get_task_estimated_duration(t) for t in active_tasks)
    adjusted_backlog_mins = raw_backlog_mins * bias_factor

    feasibility_ratio = (
        adjusted_backlog_mins / weekly_capacity if weekly_capacity > 0 else 1.0
    )

    if feasibility_ratio > 1.8:
        risk_score = 88.0
        category = "CRITICAL"
        predicted_outcome = "UNREALISTIC_QUEUE"
        factors = [
            f"Active backlog ({round(adjusted_backlog_mins / 60, 1)} hrs) exceeds 1.8x available weekly capacity ({round(weekly_capacity / 60, 1)} hrs)",
            f"{len(active_tasks)} active deliverables competing for execution time",
        ]
        action = "Prune or defer lower-priority tasks; adjust scope across active goals."
    elif feasibility_ratio > 1.2:
        risk_score = 65.0
        category = "HIGH"
        predicted_outcome = "STRETCH_QUEUE"
        factors = [
            f"Backlog ({round(adjusted_backlog_mins / 60, 1)} hrs) requires stretch capacity exceeding normal bounds by {int((feasibility_ratio - 1.0) * 100)}%",
        ]
        action = "Prioritize top 3 high-impact deliverables; postpone remaining tasks to next week."
    elif feasibility_ratio > 0.8:
        risk_score = 40.0
        category = "MODERATE"
        predicted_outcome = "FULL_CAPACITY"
        factors = [
            f"Backlog represents a full but manageable workload ({round(adjusted_backlog_mins / 60, 1)} hrs)",
        ]
        action = "Maintain disciplined focus blocks to ensure timely delivery."
    else:
        risk_score = 15.0
        category = "LOW"
        predicted_outcome = "HEALTHY_CAPACITY"
        factors = [
            f"Backlog ({round(adjusted_backlog_mins / 60, 1)} hrs) is well within weekly bandwidth",
        ]
        action = "Ample bandwidth available for deep work or accelerated goal milestones."

    evidence = [
        f"Active task count: {len(active_tasks)} tasks",
        f"Raw estimated effort: {raw_backlog_mins} mins ({round(raw_backlog_mins / 60, 1)} hrs)",
        f"Adjusted effort (with {bias_factor:.2f}x bias): {round(adjusted_backlog_mins)} mins ({round(adjusted_backlog_mins / 60, 1)} hrs)",
        f"Weekly baseline capacity: {round(weekly_capacity)} mins ({round(weekly_capacity / 60, 1)} hrs)",
        f"Capacity demand ratio: {round(feasibility_ratio, 2)}x",
    ]

    confidence = calculate_confidence_score(
        sample_size=len(data.completed_tasks),
        benchmark_size=15,
        base_confidence=0.85
    )

    insight = {
        "prediction_type": "WORKLOAD_FEASIBILITY",
        "entity_type": "Workload",
        "entity_id": f"queue_{data.today.isoformat()}",
        "risk_score": risk_score,
        "risk_category": category,
        "confidence_score": confidence,
        "has_sufficient_data": data.has_sufficient_history,
        "title": f"Backlog Feasibility: {predicted_outcome.replace('_', ' ').title()}",
        "summary": (
            f"Total active deliverable backlog ({round(adjusted_backlog_mins / 60, 1)} hrs) is "
            f"{predicted_outcome.lower().replace('_', ' ')} against weekly capacity ({round(weekly_capacity / 60, 1)} hrs)."
        ),
        "supporting_evidence": evidence,
        "contributing_factors": factors,
        "suggested_action": action,
        "time_horizon": "Current Week (7 Days)",
        "horizon_date": data.today + timedelta(days=7),
        "predicted_outcome": predicted_outcome,
        "model_version": "queue_feasibility_v1",
    }

    return [insight]

def predict_task_completion_likelihood(
    task: Any,
    data: HistoricalDataContainer,
    extractor: FeatureExtractor,
    ml_predictor: Any,
) -> Dict[str, Any]:
    """
    Estimates the likelihood (0.0 to 100.0%) of completing an individual task
    before its deadline, considering historical completion rates, task priorities,
    estimated duration, estimation bias, deadline proximity, and postponements.
    """
    task_features = extractor.extract_task_features()
    workload_features = extractor.extract_workload_features()

    bias_factor = task_features["estimation_bias_ratio"]
    daily_velocity = task_features["daily_task_velocity"]
    daily_capacity = workload_features["daily_capacity_minutes"]

    days_remaining = (task.due_date - data.today).days if task.due_date else None
    est_duration = extractor.get_task_estimated_duration(task)
    adjusted_duration = est_duration * bias_factor
    postpones = extractor.get_task_postpone_count(task)
    priority = getattr(task, "priority", "Medium") or "Medium"

    if days_remaining is not None and days_remaining < 0:
        overdue_prob = 1.0
        completion_likelihood = 0.0
        risk_level = "CRITICAL"
        predicted_outcome = "OVERDUE"
        evidence = [
            f"Task is already {abs(days_remaining)} day(s) overdue (Due date: {task.due_date})",
            f"Priority level: {priority}",
            f"Estimated duration: {est_duration}m (adjusted: {round(adjusted_duration)}m)",
        ]
        factors = [f"Deadline expired on {task.due_date}"]
        action = f"Complete or reschedule '{task.title}' immediately to prevent project slip."
        confidence = 0.95
    else:
        eff_days = max(1, days_remaining) if days_remaining is not None else 7
        avail_capacity = float(eff_days * daily_capacity)
        buffer_ratio = max(0.1, avail_capacity / max(30.0, adjusted_duration))

        overdue_prob = ml_predictor.predict_deadline_overdue_prob(
            estimated_duration=adjusted_duration,
            postpone_count=postpones,
            priority=priority,
            buffer_ratio=buffer_ratio,
        )

        completion_likelihood = round(max(2.0, min(98.0, (1.0 - overdue_prob) * 100.0)), 1)
        risk_score = round(overdue_prob * 100.0, 1)

        if risk_score >= 75.0:
            risk_level = "CRITICAL"
            predicted_outcome = "UNLIKELY_TO_COMPLETE"
        elif risk_score >= 50.0:
            risk_level = "HIGH"
            predicted_outcome = "AT_RISK"
        elif risk_score >= 25.0:
            risk_level = "MODERATE"
            predicted_outcome = "POSSIBLE_DELAY"
        else:
            risk_level = "LOW"
            predicted_outcome = "LIKELY_ON_TIME"

        evidence = [
            f"Estimated completion likelihood: {completion_likelihood}%",
            f"Deadline proximity: {days_remaining if days_remaining is not None else 'No deadline'} day(s) remaining",
            f"Effort requirement: {est_duration}m (adjusted to {round(adjusted_duration)}m with {bias_factor:.2f}x bias)",
            f"Historical daily velocity: {daily_velocity:.2f} tasks/day",
            f"Workload buffer ratio: {buffer_ratio:.2f}x available capacity",
            f"Prior postponements: {postpones}",
        ]
        factors = []
        if buffer_ratio < 1.2:
            factors.append("Tight workload buffer available before deadline")
        if postpones > 0:
            factors.append(f"Task has been postponed {postpones} time(s)")
        if priority == "High":
            factors.append("High priority deliverable requiring undivided deep work")

        action = (
            f"Schedule dedicated {round(adjusted_duration)}m focus session before {task.due_date}."
            if risk_score >= 50.0
            else f"On track for on-time delivery by {task.due_date or 'target date'}."
        )
        confidence = calculate_confidence_score(
            sample_size=task_features["bias_sample_size"] if not task_features["is_bias_heuristic"] else 1,
            benchmark_size=10,
            base_confidence=0.85,
        )

    explanation = (
        f"Task '{task.title}' has an estimated {completion_likelihood}% likelihood of on-time completion "
        f"({risk_level} risk level) based on historical velocity ({daily_velocity:.2f} tasks/day) and "
        f"{postpones} prior postponement(s)."
    )

    return {
        "task_id": task.id,
        "title": task.title,
        "priority": priority,
        "due_date": task.due_date,
        "days_remaining": days_remaining,
        "estimated_duration_minutes": est_duration,
        "adjusted_duration_minutes": round(adjusted_duration),
        "completion_likelihood": completion_likelihood,
        "risk_level": risk_level,
        "confidence_score": confidence,
        "has_sufficient_data": data.has_sufficient_history,
        "supporting_evidence": evidence,
        "contributing_factors": factors,
        "explanation": explanation,
        "suggested_action": action,
        "predicted_outcome": predicted_outcome,
    }

def predict_all_task_completions(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor,
    ml_predictor: Any,
) -> List[Dict[str, Any]]:
    """
    Returns completion likelihood predictions for all active tasks.
    """
    return [
        predict_task_completion_likelihood(t, data, extractor, ml_predictor)
        for t in data.active_tasks
    ]
