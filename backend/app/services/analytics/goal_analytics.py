import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.goal import Goal
from backend.app.models.task import Task
from backend.app.models.predictive_insight import PredictiveInsight
from backend.app.schemas.analytics import GoalAnalyticsDetail

logger = logging.getLogger(__name__)

def analyze_goals_in_depth(
    db: Session,
    reference_date: Optional[date] = None,
) -> GoalAnalyticsDetail:
    """
    Performs comprehensive goal analytics, tracking milestone velocity,
    identifying stalled or delayed milestones, and integrating Phase 6 predictive trajectories.
    """
    today = reference_date or date.today()
    goals = db.query(Goal).all()
    total_goals = len(goals)

    if total_goals == 0:
        return GoalAnalyticsDetail(
            total_goals=0,
            completed_goals=0,
            active_goals=0,
            average_progress=0.0,
            delayed_goals_count=0,
            on_track_goals_count=0,
            average_velocity_percent_per_day=0.0,
            predictive_trajectories=[],
            has_sufficient_data=False,
            summary="No goals tracked in system.",
        )

    completed_goals = sum(1 for g in goals if g.status == "Completed")
    active_goals_list = [g for g in goals if g.status != "Completed"]
    active_goals = len(active_goals_list)

    avg_progress = round(sum(float(g.progress or 0) for g in goals) / total_goals, 1)

    # Calculate velocities & status
    velocities: List[float] = []
    delayed_count = 0
    on_track_count = 0

    for g in active_goals_list:
        prog = float(g.progress or 0)
        c_date = g.created_at.date() if g.created_at else today
        days_elapsed = max(1, (today - c_date).days)
        velocity = round(prog / days_elapsed, 2)
        velocities.append(velocity)

        # Check deadline delay
        if g.target_date and g.target_date < today and prog < 100.0:
            delayed_count += 1
        elif prog < 10.0 and days_elapsed >= 7:
            delayed_count += 1
        elif prog >= 50.0 or velocity >= 1.5:
            on_track_count += 1

    avg_velocity = round(sum(velocities) / max(1, len(velocities)), 2)

    # 4. Integrate Phase 6 Predictive Trajectories
    predictive_trajectories: List[Dict[str, Any]] = []
    goal_insights = (
        db.query(PredictiveInsight)
        .filter(PredictiveInsight.prediction_type == "GOAL_TRAJECTORY")
        .all()
    )
    insight_map = {ins.entity_id: ins for ins in goal_insights if ins.entity_id}

    for g in active_goals_list:
        ins = insight_map.get(g.id)
        if ins:
            predictive_trajectories.append({
                "goal_id": g.id,
                "title": g.title,
                "progress": g.progress or 0,
                "predicted_outcome": ins.predicted_outcome,
                "risk_category": ins.risk_category,
                "confidence_score": ins.confidence_score,
                "has_sufficient_data": ins.has_sufficient_data,
                "suggested_action": ins.suggested_action,
            })
        else:
            # Fallback empirical trajectory
            target_days = (g.target_date - today).days if g.target_date else 30
            req_velocity = round((100.0 - float(g.progress or 0)) / max(1, target_days), 2)
            predictive_trajectories.append({
                "goal_id": g.id,
                "title": g.title,
                "progress": g.progress or 0,
                "predicted_outcome": "ON_TRACK" if avg_velocity >= req_velocity else "NEEDS_ATTENTION",
                "risk_category": "LOW" if avg_velocity >= req_velocity else "MODERATE",
                "confidence_score": 0.70,
                "has_sufficient_data": True,
                "suggested_action": "Maintain execution velocity to achieve target milestone.",
            })

    summary = (
        f"{total_goals} total goals ({completed_goals} completed, {active_goals} active). "
        f"Average progress: {avg_progress}%. Average velocity: {avg_velocity}%/day. "
        f"{on_track_count} on track, {delayed_count} delayed or lagging."
    )

    return GoalAnalyticsDetail(
        total_goals=total_goals,
        completed_goals=completed_goals,
        active_goals=active_goals,
        average_progress=avg_progress,
        delayed_goals_count=delayed_count,
        on_track_goals_count=on_track_count,
        average_velocity_percent_per_day=avg_velocity,
        predictive_trajectories=predictive_trajectories,
        has_sufficient_data=total_goals >= 2,
        summary=summary,
    )
