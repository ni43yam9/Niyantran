from datetime import date, timedelta
from typing import List, Dict, Any
from backend.app.services.predictive.data_preparation import HistoricalDataContainer
from backend.app.services.predictive.feature_extraction import FeatureExtractor
from backend.app.services.predictive.risk_assessment import (
    calculate_confidence_score,
    classify_risk
)

def predict_habit_decay(
    data: HistoricalDataContainer,
    extractor: FeatureExtractor
) -> List[Dict[str, Any]]:
    """
    Evaluates active habits to predict streak vulnerability and adherence decay.
    """
    insights = []

    for habit in data.habits:
        hf = extractor.extract_habit_features(habit)
        streak = hf["streak_count"]
        adherence_7d = hf["adherence_rate_7d"]
        adherence_14d = hf.get("adherence_rate_14d", adherence_7d)
        missed_last_4 = hf.get("missed_last_4", 0)
        days_since_last = hf["days_since_last_log"]
        is_vulnerable = hf["is_streak_vulnerable"]
        is_declining = hf.get("declining_consistency", False)
        is_missed_pattern = hf.get("missed_pattern", False)

        has_sufficient = hf["total_logs"] >= 2 or streak > 0

        # Check Insufficient Data
        if not has_sufficient:
            insights.append({
                "prediction_type": "HABIT_DECAY",
                "entity_type": "Habit",
                "entity_id": habit.id,
                "risk_score": 0.0,
                "risk_category": "INSUFFICIENT_DATA",
                "confidence_score": 0.25,
                "has_sufficient_data": False,
                "title": f"Habit Consistency: '{habit.name}' (Calibrating)",
                "summary": f"Habit '{habit.name}' has fewer than 2 logged entries. Statistical adherence modeling requires additional check-ins.",
                "supporting_evidence": [
                    f"Total logged completions: {hf['total_logs']}",
                    f"Current streak: {streak}",
                    "Minimum 2 historical observations required for consistency trend prediction",
                ],
                "contributing_factors": ["Early habit initialization stage"],
                "suggested_action": f"Log initial completions for '{habit.name}' to calibrate consistency forecasting.",
                "time_horizon": "Upcoming 7 Days",
                "horizon_date": data.today + timedelta(days=7),
                "predicted_outcome": "INSUFFICIENT_DATA",
                "model_version": "habit_continuity_v1",
            })
            continue

        # 1. Early Warning: Streak Loss Risk
        if is_vulnerable and streak > 0:
            risk_score = 80.0
            category = "HIGH"
            predicted_outcome = "STREAK_BREAK"
            title = f"Habit Early Warning: '{habit.name}' Streak at Risk"
            factors = [
                f"Active streak of {streak} days will reset to zero if not completed today",
                f"No completion recorded yet for {data.today.isoformat()}",
            ]
            action = f"Complete a 5-10 minute micro-session for '{habit.name}' today to defend your streak record."

        # 2. Early Warning: Increasing Missed-Day Pattern
        elif is_missed_pattern:
            risk_score = 65.0
            category = "HIGH"
            predicted_outcome = "MISSED_DAY_PATTERN"
            title = f"Habit Early Warning: '{habit.name}' Missed Days Accumulating"
            factors = [
                f"Missed {missed_last_4} of the last 4 days, breaking daily automaticity",
                f"7-day adherence is currently {int(adherence_7d * 100)}%",
            ]
            action = f"Re-anchor '{habit.name}' by scheduling it immediately after an established daily routine."

        # 3. Early Warning: Declining Consistency
        elif is_declining:
            risk_score = 55.0
            category = "MODERATE"
            predicted_outcome = "DECLINING_CONSISTENCY"
            title = f"Habit Early Warning: Declining Consistency on '{habit.name}'"
            factors = [
                f"Adherence dropped from {int(adherence_14d * 100)}% (14d) down to {int(adherence_7d * 100)}% (7d)",
                f"Consistency gap of {int((adherence_14d - adherence_7d) * 100)}% detected",
            ]
            action = f"Lower target effort or remove friction to stabilize '{habit.name}' consistency."

        # 4. Stable Habit
        else:
            risk_score = 15.0
            category = "LOW"
            predicted_outcome = "STABLE"
            title = f"Habit Consistent: {habit.name}"
            factors = [
                f"Consistent adherence maintained ({int(adherence_7d * 100)}% over last 7 days)",
                f"Active streak: {streak} day(s)",
            ]
            action = f"Maintain regular check-ins for habit '{habit.name}'."

        evidence = [
            f"Frequency: {habit.frequency}",
            f"Current streak: {streak} days",
            f"7-day adherence: {int(adherence_7d * 100)}% (14-day: {int(adherence_14d * 100)}%)",
            f"Missed days in last 4: {missed_last_4}/4",
            f"Total logged completions: {hf['total_logs']}",
        ]

        confidence = calculate_confidence_score(
            sample_size=hf["total_logs"],
            benchmark_size=10,
            base_confidence=0.85
        )

        insights.append({
            "prediction_type": "HABIT_DECAY",
            "entity_type": "Habit",
            "entity_id": habit.id,
            "risk_score": risk_score,
            "risk_category": category,
            "confidence_score": confidence,
            "has_sufficient_data": True,
            "title": title,
            "summary": (
                f"Habit '{habit.name}' has a {category.lower()} decay risk "
                f"(Predicted outcome: {predicted_outcome.lower().replace('_', ' ')})."
            ),
            "supporting_evidence": evidence,
            "contributing_factors": factors,
            "suggested_action": action,
            "time_horizon": "Next 24-48 Hours",
            "horizon_date": data.today + timedelta(days=1),
            "predicted_outcome": predicted_outcome,
            "model_version": "habit_continuity_v1",
        })

    return insights
