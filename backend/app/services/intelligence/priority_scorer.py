from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class PriorityScoreResult:
    score: float                        # 0.0 to 100.0
    level: str                          # HIGH, MEDIUM, LOW
    breakdown: Dict[str, float] = field(default_factory=dict)

def calculate_recommendation_priority(
    urgency_days: Optional[int],          # None, negative (overdue), 0 (today), 1, 2, ...
    importance_level: str = "Medium",     # High, Medium, Low
    goal_relevance_pts: float = 0.0,      # 0.0 to 20.0
    habit_impact_pts: float = 0.0,        # 0.0 to 15.0
    postpone_count: int = 0,
    bias_factor: float = 1.0,
    historical_acceptance_rate: float = 0.5,
) -> PriorityScoreResult:
    """
    Computes an explainable, multi-variable priority score (0.0 to 100.0)
    for a productivity recommendation, avoiding arbitrary assignments.
    """
    # 1. Urgency Component (Max 35 pts)
    if urgency_days is None:
        urgency_score = 5.0
    elif urgency_days < 0:
        # Overdue: Maximum urgency
        urgency_score = 35.0
    elif urgency_days == 0:
        # Due today
        urgency_score = 30.0
    elif urgency_days <= 2:
        urgency_score = 22.0
    elif urgency_days <= 5:
        urgency_score = 14.0
    else:
        urgency_score = 6.0

    # 2. Importance Component (Max 35 pts)
    imp_upper = (importance_level or "Medium").upper()
    if imp_upper == "HIGH":
        importance_score = 35.0
    elif imp_upper == "MEDIUM":
        importance_score = 20.0
    else:
        importance_score = 8.0

    # 3. Goal Relevance Component (Max 20 pts)
    goal_score = min(20.0, max(0.0, goal_relevance_pts))

    # 4. Habit Impact Component (Max 20 pts)
    habit_score = min(20.0, max(0.0, habit_impact_pts))

    # 5. Behavioral Personalization Weight (Max 10 pts)
    behavioral_score = 0.0
    if postpone_count >= 2:
        behavioral_score += 5.0
    elif postpone_count == 1:
        behavioral_score += 2.0

    if bias_factor >= 1.3:
        behavioral_score += 3.0

    # Acceptance preference modifier (-2.0 to +2.0)
    pref_modifier = (historical_acceptance_rate - 0.5) * 4.0
    behavioral_score = min(10.0, max(0.0, behavioral_score + pref_modifier))

    # Total Score
    total_score = round(
        min(100.0, max(0.0, urgency_score + importance_score + goal_score + habit_score + behavioral_score)),
        1
    )

    # Classification
    if total_score >= 70.0:
        level = "HIGH"
    elif total_score >= 40.0:
        level = "MEDIUM"
    else:
        level = "LOW"

    breakdown = {
        "urgency": round(urgency_score, 1),
        "importance": round(importance_score, 1),
        "goal_relevance": round(goal_score, 1),
        "habit_impact": round(habit_score, 1),
        "behavioral_weight": round(behavioral_score, 1),
        "total_score": total_score,
    }

    return PriorityScoreResult(score=total_score, level=level, breakdown=breakdown)
