from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)

def predict_goal_risks(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor
) -> List[Dict[str, Any]]:
    """
    Evaluates all active goals to predict trajectory deviation and completion risk.
    """
    insights = []

    for goal in data.goals:
        if goal.status == "Completed":
            continue

        gf = extractor.extract_goal_features(goal)
        progress = gf["progress"]
        days_remaining = gf["days_remaining"]
        historical_vel = gf["historical_velocity"]
        required_vel = gf["required_velocity"]
        velocity_deficit = gf["velocity_deficit"]
        pending_tasks = gf["linked_tasks_pending"]
        total_tasks = gf["linked_tasks_total"]
        recent_7d = gf.get("recent_completed_7d", 0)

        # Insufficient data guard: avoid making predictions when data is sparse
        if not gf.get("has_sufficient_history", True):
            insights.append({
                "prediction_type": "GOAL_TRAJECTORY",
                "entity_type": "Goal",
                "entity_id": goal.id,
                "risk_score": 0.0,
                "risk_category": "INSUFFICIENT_DATA",
                "confidence_score": 0.20,
                "has_sufficient_data": False,
                "title": f"Goal Trajectory: '{goal.title}' (Calibrating)",
                "summary": (
                    f"Insufficient historical progress data to estimate achievement trajectory for '{goal.title}'. "
                    f"Goal was created recently ({gf['days_elapsed']} day(s) elapsed) with no completed deliverables yet."
                ),
                "supporting_evidence": [
                    f"Days elapsed since start: {gf['days_elapsed']} day(s)",
                    f"Current progress: {progress:.1f}%",
                    f"Completed linked tasks: {gf['linked_tasks_completed']}/{total_tasks}",
                    "Minimum 3 days of active tracking or completed deliverables required for statistical trajectory modeling",
                ],
                "contributing_factors": [
                    "Early lifecycle stage with insufficient empirical data points",
                ],
                "suggested_action": f"Complete initial linked deliverable for '{goal.title}' to establish baseline progress velocity.",
                "time_horizon": f"Until Target: {goal.target_date}",
                "horizon_date": goal.target_date,
                "predicted_outcome": "INSUFFICIENT_DATA",
                "model_version": "goal_trajectory_v1",
            })
            continue

        # Check overdue goal
        if days_remaining <= 0 and progress < 100.0:
            risk_score = 100.0
            category = "CRITICAL"
            predicted_outcome = "MISSED_TARGET"
            factors = [
                f"Goal target date ({goal.target_date}) has already passed with progress at {progress:.1f}%",
                f"Unfinished deliverables remaining: {pending_tasks} task(s)",
            ]
            evidence = [
                f"Target date: {goal.target_date}",
                f"Current progress: {progress:.1f}%",
                f"Linked tasks pending: {pending_tasks}/{total_tasks}",
                f"Recent 7-day milestone completions: {recent_7d}",
            ]
            action = f"Extend target date or archive goal '{goal.title}' with actual progress achieved."
            confidence = 0.95
        else:
            # Future deadline: assess trajectory and recent progress trends
            if historical_vel == 0.0 and progress == 0.0 and gf["days_elapsed"] > 7:
                # Inactive goal
                risk_score = 85.0
                category = "CRITICAL"
                predicted_outcome = "STALLED"
                factors = [
                    f"Zero progress recorded despite {gf['days_elapsed']} days elapsed since start",
                    f"Required velocity is now {required_vel:.2f}% per day to hit target date",
                ]
            elif historical_vel > 0 and required_vel > 2.5 * historical_vel:
                risk_score = 75.0
                category = "HIGH"
                predicted_outcome = "AT_RISK"
                factors = [
                    f"Current pace ({historical_vel:.2f}%/day) is less than half the required pace ({required_vel:.2f}%/day)",
                    f"Velocity deficit: {velocity_deficit:.2f}% per day",
                ]
            elif historical_vel > 0 and required_vel > 1.25 * historical_vel:
                risk_score = 50.0
                category = "MODERATE"
                predicted_outcome = "NEEDS_ATTENTION"
                factors = [
                    f"Minor velocity gap: pace must increase from {historical_vel:.2f}% to {required_vel:.2f}% daily",
                ]
            else:
                risk_score = 20.0
                category = "LOW"
                predicted_outcome = "ON_TRACK"
                factors = [
                    f"Pace ({historical_vel:.2f}%/day) matches or exceeds required velocity ({required_vel:.2f}%/day)",
                ]

            evidence = [
                f"Current progress: {progress:.1f}% ({gf['remaining_progress']:.1f}% remaining)",
                f"Days remaining: {days_remaining} day(s)",
                f"Historical progress pace: {historical_vel:.2f}%/day",
                f"Required daily velocity: {required_vel:.2f}%/day",
                f"Velocity deficit: {velocity_deficit:.2f}%/day",
                f"Recent 7-day progress trend: {recent_7d} task(s) completed",
                f"Linked deliverables: {gf['linked_tasks_completed']}/{total_tasks} completed",
            ]

            action = (
                f"Break down remaining milestones and schedule {min(3, max(1, pending_tasks))} linked task(s) this week."
                if risk_score >= 50.0
                else f"Maintain current execution pace to complete by {goal.target_date}."
            )

            # Confidence based on days elapsed
            confidence = calculate_confidence_score(
                sample_size=gf["days_elapsed"],
                benchmark_size=14,
                base_confidence=0.85
            )

        insights.append({
            "prediction_type": "GOAL_TRAJECTORY",
            "entity_type": "Goal",
            "entity_id": goal.id,
            "risk_score": risk_score,
            "risk_category": category,
            "confidence_score": confidence,
            "has_sufficient_data": True,
            "title": f"Goal Trajectory: {goal.title}",
            "summary": (
                f"Goal '{goal.title}' is currently {predicted_outcome.lower().replace('_', ' ')} "
                f"with a {category.lower()} trajectory risk (Risk score: {risk_score}/100)."
            ),
            "supporting_evidence": evidence,
            "contributing_factors": factors,
            "suggested_action": action,
            "time_horizon": f"Until {goal.target_date}",
            "horizon_date": goal.target_date,
            "predicted_outcome": predicted_outcome,
            "model_version": "trajectory_v1",
        })

    return insights
