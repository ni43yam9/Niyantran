import logging
from typing import List
from sqlalchemy.orm import Session

from backend.app.models.recommendation import Recommendation
from backend.app.services.intelligence.context_analyzer import ProductivityContext
from backend.app.services.intelligence.priority_scorer import calculate_recommendation_priority

logger = logging.getLogger(__name__)

def enrich_legacy_recommendations(
    db: Session,
    recommendations: List[Recommendation],
    ctx: ProductivityContext,
) -> None:
    """
    Non-destructively populates priority_score, score_breakdown, and structured explanations
    for legacy recommendations that were generated prior to Phase 5.
    """
    modified = False
    for r in recommendations:
        payload = dict(r.action_payload or {})
        if "priority_score" in payload:
            continue

        if r.category == "Task" or r.type in ("PRIORITIZATION", "DEADLINE_RISK"):
            task = next((t for t in ctx.tasks if t.id == r.entity_id), None)
            if task:
                days_left = (task.due_date - ctx.today).days if task.due_date else 0
                postpones = ctx.task_postpones.get(task.id, 0)
                goal_pts = 15.0 if task.goal_id and task.goal_id in ctx.goal_map else 0.0
                score_res = calculate_recommendation_priority(
                    urgency_days=days_left,
                    importance_level=task.priority,
                    goal_relevance_pts=goal_pts,
                    postpone_count=postpones,
                    bias_factor=ctx.bias_factor,
                    historical_acceptance_rate=ctx.acceptance_by_type.get(r.type, 0.5),
                )
                r.priority = score_res.level
                payload["priority_score"] = score_res.score
                payload["score_breakdown"] = score_res.breakdown
                payload["explanation"] = {
                    "what_happened": f"Task '{task.title}' requires focus based on deadline proximity and priority.",
                    "why_generated": f"Deadline is {task.due_date or 'today'} with priority '{task.priority}'.",
                    "suggested_action": f"Allocate focus session to advance '{task.title}'.",
                    "why_prioritize": f"Urgency score: {score_res.breakdown['urgency']}, Importance score: {score_res.breakdown['importance']}.",
                }
                r.action_payload = payload
                modified = True

        elif r.category == "Goal" or r.type == "GOAL_PROGRESS":
            goal = ctx.goal_map.get(r.entity_id)
            if goal:
                days_left = (goal.target_date - ctx.today).days if goal.target_date else 14
                score_res = calculate_recommendation_priority(
                    urgency_days=days_left,
                    importance_level=goal.priority,
                    goal_relevance_pts=15.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("GOAL_PROGRESS", 0.5),
                )
                r.priority = score_res.level
                payload["priority_score"] = score_res.score
                payload["score_breakdown"] = score_res.breakdown
                payload["explanation"] = {
                    "what_happened": f"Goal '{goal.title}' is currently at {goal.progress}% progress.",
                    "why_generated": "Proactive milestone alignment to keep goals on track.",
                    "suggested_action": f"Break down deliverables or complete linked tasks for '{goal.title}'.",
                    "why_prioritize": f"Goal relevance weight: {score_res.breakdown['goal_relevance']} pts.",
                }
                r.action_payload = payload
                modified = True

        elif r.category == "Habit" or r.type == "HABIT_IMPROVEMENT":
            habit = next((h for h in ctx.habits if h.id == r.entity_id), None)
            if habit:
                streak = habit.base_streak or 0
                is_streak = streak >= 3
                score_res = calculate_recommendation_priority(
                    urgency_days=0,
                    importance_level="High" if is_streak else "Medium",
                    habit_impact_pts=15.0 if is_streak else 10.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("HABIT_IMPROVEMENT", 0.5),
                )
                r.priority = score_res.level
                payload["priority_score"] = score_res.score
                payload["score_breakdown"] = score_res.breakdown
                payload["explanation"] = {
                    "what_happened": f"Habit '{habit.name}' check-in is pending today.",
                    "why_generated": f"Active streak is {streak} days." if is_streak else "Adherence consistency needs reinforcement.",
                    "suggested_action": f"Log today's check-in for '{habit.name}'.",
                    "why_prioritize": f"Streak preservation score: {score_res.score}.",
                }
                r.action_payload = payload
                modified = True

    if modified:
        db.commit()
