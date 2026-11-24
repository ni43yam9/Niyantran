from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)

def forecast_workload_distribution(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor
) -> List[Dict[str, Any]]:
    """
    Forecasts daily workload across the next 7 days and identifies projected bottlenecks.
    """
    workload_features = extractor.extract_workload_features()
    daily_capacity = workload_features["daily_capacity_minutes"]
    forecast_7d = workload_features["forecast_7d"]

    insights = []
    overloaded_days = []
    conflict_days = []
    light_days = []

    for date_str, day_data in forecast_7d.items():
        f_date = day_data["date"]
        task_count = day_data["task_count"]
        high_prio_count = day_data.get("high_priority_task_count", 0)
        total_mins = day_data["total_estimated_minutes"]
        ratio = day_data["overload_ratio"]

        # 1. Overloaded Day Detection
        if ratio > 1.25 or total_mins > 360:
            overloaded_days.append(day_data)
            risk_score = min(100.0, round(ratio * 50.0, 1))
            category = classify_risk(risk_score, has_sufficient_data=data.has_sufficient_history)
            predicted_outcome = "BOTTLENECK"

            evidence = [
                f"Date: {f_date.isoformat()}",
                f"Scheduled tasks: {task_count} ({high_prio_count} high-priority)",
                f"Estimated workload: {total_mins} mins ({round(total_mins / 60.0, 1)} hrs)",
                f"Daily capacity threshold: {round(daily_capacity)} mins ({round(daily_capacity / 60.0, 1)} hrs)",
                f"Overload ratio: {ratio}x capacity",
            ]

            factors = [
                f"Workload exceeds daily capacity threshold by {round((ratio - 1.0) * 100)}%",
                f"{task_count} tasks converge on the same due date",
            ]

            action = f"Preemptively reschedule non-urgent tasks from {f_date.strftime('%a, %b %d')} to adjacent low-density days."

            confidence = calculate_confidence_score(
                sample_size=data.timeblock_count + data.completed_task_count,
                benchmark_size=15,
                base_confidence=0.85
            )

            insights.append({
                "prediction_type": "WORKLOAD_OVERLOAD",
                "entity_type": "Workload",
                "entity_id": f"workload_{f_date.isoformat()}",
                "risk_score": risk_score,
                "risk_category": category,
                "confidence_score": confidence,
                "has_sufficient_data": data.has_sufficient_history,
                "title": f"Workload Bottleneck Projected: {f_date.strftime('%a, %b %d')}",
                "summary": (
                    f"Projected workload on {f_date.isoformat()} ({total_mins} mins) "
                    f"exceeds sustainable daily capacity by {ratio}x."
                ),
                "supporting_evidence": evidence,
                "contributing_factors": factors,
                "suggested_action": action,
                "time_horizon": f"Single Day: {f_date.isoformat()}",
                "horizon_date": f_date,
                "predicted_outcome": predicted_outcome,
                "model_version": "workload_projection_v1",
            })

        # 2. Scheduling Conflict Detection (Multiple High Priority Tasks on Same Day)
        if high_prio_count >= 2:
            conflict_days.append(f_date)
            insights.append({
                "prediction_type": "WORKLOAD_OVERLOAD",
                "entity_type": "Workload",
                "entity_id": f"conflict_{f_date.isoformat()}",
                "risk_score": 65.0,
                "risk_category": "HIGH",
                "confidence_score": 0.85,
                "has_sufficient_data": data.has_sufficient_history,
                "title": f"Scheduling Conflict: {f_date.strftime('%a, %b %d')}",
                "summary": f"{high_prio_count} high-priority deliverables are due on {f_date.strftime('%a, %b %d')}, creating focus fragmentation.",
                "supporting_evidence": [
                    f"Date: {f_date.isoformat()}",
                    f"High-priority deliverables due: {high_prio_count}",
                    f"Total deliverables: {task_count}",
                ],
                "contributing_factors": [
                    "Multiple critical milestones converging without sequential buffers",
                ],
                "suggested_action": f"Sequence high-priority tasks across {f_date.strftime('%a, %b %d')} and adjacent days to preserve deep focus.",
                "time_horizon": f"Single Day: {f_date.isoformat()}",
                "horizon_date": f_date,
                "predicted_outcome": "SCHEDULING_CONFLICT",
                "model_version": "workload_conflict_v1",
            })

        # Track light days
        if day_data.get("is_light"):
            light_days.append(f_date)

    # 3. High-Pressure Period Detection (Consecutive heavy days)
    high_pressure_periods = workload_features.get("high_pressure_periods", [])
    for streak in high_pressure_periods:
        start_d = streak[0]
        end_d = streak[-1]
        streak_mins = sum(forecast_7d[d.isoformat()]["total_estimated_minutes"] for d in streak)
        insights.append({
            "prediction_type": "WORKLOAD_OVERLOAD",
            "entity_type": "Workload",
            "entity_id": f"period_{start_d.isoformat()}_{end_d.isoformat()}",
            "risk_score": 70.0,
            "risk_category": "HIGH",
            "confidence_score": 0.85,
            "has_sufficient_data": data.has_sufficient_history,
            "title": f"High-Pressure Period: {start_d.strftime('%a')} - {end_d.strftime('%a')}",
            "summary": f"Sustained heavy workload projected across {len(streak)} consecutive days ({streak_mins} mins total, {round(streak_mins / len(streak))}m avg/day).",
            "supporting_evidence": [
                f"Consecutive high-demand dates: {', '.join(d.strftime('%b %d') for d in streak)}",
                f"Cumulative planned effort: {streak_mins} mins ({round(streak_mins / 60.0, 1)} hrs)",
            ],
            "contributing_factors": [
                "Consecutive near-capacity or over-capacity days risk cognitive fatigue and rollover delays",
            ],
            "suggested_action": "Insert explicit breaks and protect non-working buffer blocks between high-load days.",
            "time_horizon": f"{len(streak)} Days: {start_d.isoformat()} to {end_d.isoformat()}",
            "horizon_date": end_d,
            "predicted_outcome": "HIGH_PRESSURE_PERIOD",
            "model_version": "workload_pressure_v1",
        })

    # 4. Available Capacity Identification
    if light_days:
        insights.append({
            "prediction_type": "WORKLOAD_OVERLOAD",
            "entity_type": "Workload",
            "entity_id": f"capacity_{data.today.isoformat()}",
            "risk_score": 10.0,
            "risk_category": "LOW",
            "confidence_score": 0.80,
            "has_sufficient_data": data.has_sufficient_history,
            "title": f"Available Capacity: {len(light_days)} Light Day(s) Ahead",
            "summary": f"{', '.join(d.strftime('%a, %b %d') for d in light_days[:3])} have available focus bandwidth (< 3.0 hrs planned effort).",
            "supporting_evidence": [
                f"Identified low-density dates: {', '.join(d.isoformat() for d in light_days)}",
                "Planned commitments on these days remain well below 50% sustainable capacity",
            ],
            "contributing_factors": [
                "Unallocated calendar bandwidth provides opportunity for proactive execution",
            ],
            "suggested_action": "Use available capacity on light days for accelerated goal milestones or pulling forward future work.",
            "time_horizon": "Upcoming 7 Days",
            "horizon_date": data.today + timedelta(days=7),
            "predicted_outcome": "AVAILABLE_CAPACITY",
            "model_version": "capacity_forecast_v1",
        })

    # If no individual days are overloaded, emit a balanced distribution insight
    if not overloaded_days:
        horizon_date = data.today + timedelta(days=7)
        total_week_mins = sum(d["total_estimated_minutes"] for d in forecast_7d.values())
        insights.append({
            "prediction_type": "WORKLOAD_OVERLOAD",
            "entity_type": "Workload",
            "entity_id": f"workload_week_{data.today.isoformat()}",
            "risk_score": 15.0,
            "risk_category": "LOW",
            "confidence_score": calculate_confidence_score(
                sample_size=data.completed_task_count,
                benchmark_size=10,
                base_confidence=0.80
            ),
            "has_sufficient_data": data.has_sufficient_history,
            "title": "7-Day Workload Distribution Feasible",
            "summary": "Projected task distribution across the upcoming 7 days remains within sustainable capacity.",
            "supporting_evidence": [
                f"Total projected effort: {total_week_mins} mins across 7 days",
                f"Peak single-day demand remains below {round(daily_capacity * 1.25)} mins",
            ],
            "contributing_factors": [
                "Tasks are evenly distributed across upcoming days without acute clustering",
            ],
            "suggested_action": "Maintain scheduled pacing.",
            "time_horizon": "Next 7 Days",
            "horizon_date": horizon_date,
            "predicted_outcome": "BALANCED",
            "model_version": "workload_projection_v1",
        })

    return insights
