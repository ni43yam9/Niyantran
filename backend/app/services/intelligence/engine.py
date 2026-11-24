import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Callable, Optional

from backend.app.models.recommendation import Recommendation
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.timeblock import DailyTimeblock
from backend.app.services.intelligence.context_analyzer import ProductivityContext
from backend.app.services.intelligence.priority_scorer import calculate_recommendation_priority
from backend.app.services.intelligence.explainability import StructuredExplanation

logger = logging.getLogger(__name__)

MAX_DAILY_LOAD_MINUTES = 360
LIGHT_DAY_LOAD_MINUTES = 240

def generate_intelligent_recommendations(
    ctx: ProductivityContext,
    is_suppressed_fn: Callable[[str, str, Optional[str], str], bool],
    now_utc: datetime,
) -> List[Recommendation]:
    """
    Executes context-aware, multi-source analysis and produces scored, explainable
    recommendations while strictly respecting deduplication and suppression rules.
    """
    new_recs: List[Recommendation] = []
    today = ctx.today

    # =========================================================================
    # 1. INTELLIGENT TASK PRIORITIZATION & DEADLINE ALERTS (PRIORITIZATION)
    # =========================================================================
    candidate_urgent_tasks = []
    for t in ctx.pending_tasks:
        if t.due_date:
            days_left = (t.due_date - today).days
            if days_left <= 2:
                candidate_urgent_tasks.append((days_left, t))

    candidate_urgent_tasks.sort(key=lambda x: (x[0], 0 if x[1].priority == "High" else 1))

    prio_count = 0
    for days_left, task in candidate_urgent_tasks:
        if prio_count >= 5:
            break
        if is_suppressed_fn("PRIORITIZATION", "Task", task.id, "default"):
            continue

        linked_goal = ctx.goal_map.get(task.goal_id) if task.goal_id else None
        goal_pts = 15.0 if linked_goal else 0.0
        postpones = ctx.task_postpones.get(task.id, 0)

        # Calculate Priority Score
        score_res = calculate_recommendation_priority(
            urgency_days=days_left,
            importance_level=task.priority,
            goal_relevance_pts=goal_pts,
            postpone_count=postpones,
            bias_factor=ctx.bias_factor,
            historical_acceptance_rate=ctx.acceptance_by_type.get("PRIORITIZATION", 0.5),
        )

        if days_left < 0:
            rec_title = f"Immediate Focus: Overdue '{task.title}'"
            rec_desc = f"Task is {abs(days_left)} day(s) overdue. Prioritize completion in your morning focus block."
            expl = StructuredExplanation(
                what_happened=f"Task '{task.title}' passed its due date ({task.due_date}) by {abs(days_left)} day(s).",
                why_generated=f"Overdue deliverables with priority '{task.priority}' degrade momentum and block progress.",
                suggested_action="Reserve an uninterrupted 60-minute focus block this morning to resolve this deliverable.",
                why_prioritize="Clearing overdue debt immediately restores execution velocity and unblocks dependent milestones."
            )
        elif days_left == 0:
            rec_title = f"Due Today: '{task.title}'"
            rec_desc = f"Task deadline expires today. Reserve deep-work capacity before afternoon commitments."
            expl = StructuredExplanation(
                what_happened=f"Task '{task.title}' is scheduled with an active deadline today ({today}).",
                why_generated=f"High urgency deliverable with priority '{task.priority}'.",
                suggested_action="Lock in a dedicated morning timeblock (09:00 - 12:00) before meeting obligations.",
                why_prioritize="Ensures on-time delivery and avoids late-night reactive context switching."
            )
        else:
            rec_title = f"Due in 24-48h: '{task.title}'"
            rec_desc = f"Deadline approaching in {days_left} day(s). Finish now to avoid last-minute rush."
            expl = StructuredExplanation(
                what_happened=f"Deadline approaching in {days_left} day(s) on {task.due_date}.",
                why_generated="Proximity to deadline requires proactive effort allocation.",
                suggested_action="Complete early draft or core requirements today to maintain buffer.",
                why_prioritize="Eliminates last-minute rush and accommodates unexpected project blockers."
            )

        payload = {
            "task_id": task.id,
            "suggested_window": f"{ctx.peak_time_window} ({'09:00 - 12:00' if ctx.peak_time_window == 'Morning' else '14:00 - 17:00'})",
            "sub_key": "default",
            "priority_score": score_res.score,
            "score_breakdown": score_res.breakdown,
            "explanation": expl.to_dict(),
        }

        rec = Recommendation(
            id=f"rec_{uuid.uuid4().hex[:12]}",
            type="PRIORITIZATION",
            category="Task",
            title=rec_title,
            description=rec_desc,
            reason=expl.to_reason_text(),
            priority=score_res.level,
            status="PENDING",
            action_type="FOCUS_TASK",
            action_payload=payload,
            entity_id=task.id,
            target_date=today,
            created_at=now_utc,
            updated_at=now_utc,
        )
        new_recs.append(rec)
        prio_count += 1

    # =========================================================================
    # 2. WORKLOAD BALANCING (WORKLOAD_BALANCE)
    # =========================================================================
    for d in ctx.days_to_check:
        load = ctx.daily_load_minutes[d]
        if load > MAX_DAILY_LOAD_MINUTES and ctx.daily_tasks[d]:
            candidates = sorted(
                ctx.daily_tasks[d],
                key=lambda x: (
                    1 if x.priority == "High" else 2,
                    (x.due_date - today).days if x.due_date else 999
                ),
                reverse=True
            )

            task_to_move = None
            for cand in candidates:
                if cand.due_date and cand.due_date <= d:
                    continue
                task_to_move = cand
                break

            if task_to_move:
                lighter_day = None
                for future_day in ctx.days_to_check:
                    if future_day > d and ctx.daily_load_minutes[future_day] < LIGHT_DAY_LOAD_MINUTES:
                        if not task_to_move.due_date or future_day <= task_to_move.due_date:
                            lighter_day = future_day
                            break

                if lighter_day and not is_suppressed_fn("WORKLOAD_BALANCE", "Schedule", task_to_move.id, "default"):
                    hrs_over = round(load / 60.0, 1)
                    hrs_light = round(ctx.daily_load_minutes[lighter_day] / 60.0, 1)

                    expl = StructuredExplanation(
                        what_happened=f"{d.strftime('%a, %b %d')} is scheduled with {hrs_over}h of effort (exceeds 6.0h max capacity).",
                        why_generated="Clustered deliverables threaten execution quality and increase likelihood of burnout.",
                        suggested_action=f"Reschedule '{task_to_move.title}' to {lighter_day.strftime('%a, %b %d')} (currently only {hrs_light}h planned).",
                        why_prioritize="Smooths daily load into sustainable blocks without risking deliverable deadlines."
                    )

                    score_res = calculate_recommendation_priority(
                        urgency_days=(d - today).days,
                        importance_level="Medium",
                        goal_relevance_pts=5.0,
                        historical_acceptance_rate=ctx.acceptance_by_type.get("WORKLOAD_BALANCE", 0.5),
                    )

                    payload = {
                        "task_id": task_to_move.id,
                        "source_date": str(d),
                        "suggested_date": str(lighter_day),
                        "sub_key": "default",
                        "priority_score": score_res.score,
                        "score_breakdown": score_res.breakdown,
                        "explanation": expl.to_dict(),
                    }

                    rec = Recommendation(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        type="WORKLOAD_BALANCE",
                        category="Schedule",
                        title=f"Balance Workload: Reschedule '{task_to_move.title}'",
                        description=f"Move '{task_to_move.title}' from {d.strftime('%a, %b %d')} to {lighter_day.strftime('%a, %b %d')} to prevent overload.",
                        reason=expl.to_reason_text(),
                        priority=score_res.level,
                        status="PENDING",
                        action_type="RESCHEDULE_TASK",
                        action_payload=payload,
                        entity_id=task_to_move.id,
                        target_date=d,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    new_recs.append(rec)

    # =========================================================================
    # 3. DEADLINE RISK DETECTION (DEADLINE_RISK)
    # =========================================================================
    for task in ctx.pending_tasks:
        if not task.due_date:
            continue
        days_rem = (task.due_date - today).days
        if 0 <= days_rem <= 5:
            postpone_times = ctx.task_postpones.get(task.id, 0)
            est_time = 60
            for tb in ctx.timeblocks:
                if tb.task_id == task.id and tb.duration_minutes:
                    est_time = tb.duration_minutes
                    break
            adjusted_effort = est_time * ctx.bias_factor
            is_high_risk = (postpone_times >= 1 and days_rem <= 3) or (adjusted_effort >= 180 and days_rem <= 2)

            if is_high_risk and not is_suppressed_fn("DEADLINE_RISK", "Task", task.id, "default"):
                bias_pct = int((ctx.bias_factor - 1.0) * 100)
                expl = StructuredExplanation(
                    what_happened=f"Task '{task.title}' has only {days_rem} day(s) remaining before due date ({task.due_date}).",
                    why_generated=(
                        f"Postponed {postpone_times} time(s). "
                        + (f"Historical duration bias projects {int(adjusted_effort)}m required effort (+{bias_pct}%)." if bias_pct > 0 else "")
                    ),
                    suggested_action=f"Allocate a dedicated {int(adjusted_effort)}m focus session before {task.due_date}.",
                    why_prioritize="Protects project delivery timeline and prevents last-minute scramble."
                )

                score_res = calculate_recommendation_priority(
                    urgency_days=days_rem,
                    importance_level=task.priority,
                    postpone_count=postpone_times,
                    bias_factor=ctx.bias_factor,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("DEADLINE_RISK", 0.5),
                )

                payload = {
                    "task_id": task.id,
                    "deadline": str(task.due_date),
                    "sub_key": "default",
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                }

                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="DEADLINE_RISK",
                    category="Task",
                    title=f"Deadline Alert: '{task.title}' at Risk",
                    description=f"High risk of deadline slippage. Allocate dedicated focus block before {task.due_date}.",
                    reason=expl.to_reason_text(),
                    priority="HIGH",
                    status="PENDING",
                    action_type="EXPEDITE_TASK",
                    action_payload=payload,
                    entity_id=task.id,
                    target_date=task.due_date,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                new_recs.append(rec)

    # =========================================================================
    # 4. GOAL PROGRESS INTELLIGENCE (GOAL_PROGRESS)
    # =========================================================================
    for goal in ctx.goals:
        if goal.status != "In Progress":
            continue

        goal_tasks = ctx.tasks_by_goal.get(goal.id, [])
        completed_goal_tasks = [t for t in goal_tasks if t.status == "Completed"]
        curr_progress = float(goal.progress or 0)

        # Check 4A: Goal has 0 linked tasks
        if len(goal_tasks) == 0:
            if not is_suppressed_fn("GOAL_PROGRESS", "Goal", goal.id, "STRUCTURE"):
                expl = StructuredExplanation(
                    what_happened=f"Goal '{goal.title}' has 0 active or scheduled tasks assigned to it.",
                    why_generated="Abstract goals without actionable deliverable tasks have an 85% higher stagnation rate.",
                    suggested_action="Decompose this goal into 2 to 3 discrete milestones or action items.",
                    why_prioritize="Transforms high-level aspirations into daily executable focus blocks."
                )
                score_res = calculate_recommendation_priority(
                    urgency_days=(goal.target_date - today).days if goal.target_date else None,
                    importance_level=goal.priority,
                    goal_relevance_pts=15.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("GOAL_PROGRESS", 0.5),
                )
                payload = {
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "sub_key": "STRUCTURE",
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                }
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="GOAL_PROGRESS",
                    category="Goal",
                    title=f"Structure Goal: '{goal.title}'",
                    description="This active goal has no actionable deliverables assigned to it.",
                    reason=expl.to_reason_text(),
                    priority=score_res.level,
                    status="PENDING",
                    action_type="ADD_GOAL_TASK",
                    action_payload=payload,
                    entity_id=goal.id,
                    target_date=today,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                new_recs.append(rec)

        # Check 4B: Goal progress lagging behind timeline
        elif goal.target_date and goal.start_date:
            total_duration_days = max(1, (goal.target_date - goal.start_date).days)
            elapsed_days = max(0, (today - goal.start_date).days)
            days_to_target = (goal.target_date - today).days

            # Calculate mathematically expected progress %
            expected_progress = min(100.0, round((elapsed_days / total_duration_days) * 100.0, 1))
            progress_deficit = expected_progress - curr_progress

            # Safety Rule: Do not panic if target date is far away (> 30 days) and elapsed time is small (< 20%)
            is_far_away = days_to_target > 30 and (elapsed_days / total_duration_days) < 0.20
            is_lagging = (
                not is_far_away and (
                    (days_to_target <= 14 and curr_progress < 50.0) or
                    (elapsed_days / total_duration_days >= 0.35 and progress_deficit >= 25.0)
                )
            )

            if is_lagging and not is_suppressed_fn("GOAL_PROGRESS", "Goal", goal.id, "LAGGING"):
                expl = StructuredExplanation(
                    what_happened=f"Goal '{goal.title}' is at {int(curr_progress)}% progress vs {int(expected_progress)}% expected pacing.",
                    why_generated=f"Timeline is {int((elapsed_days/total_duration_days)*100)}% elapsed with {days_to_target} days remaining.",
                    suggested_action=f"Focus on the remaining {len(goal_tasks) - len(completed_goal_tasks)} pending deliverable(s) this week.",
                    why_prioritize="Catches up on milestone trajectory before target deadline becomes unachievable."
                )
                score_res = calculate_recommendation_priority(
                    urgency_days=days_to_target,
                    importance_level=goal.priority,
                    goal_relevance_pts=20.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("GOAL_PROGRESS", 0.5),
                )
                payload = {
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "sub_key": "LAGGING",
                    "expected_progress": expected_progress,
                    "actual_progress": curr_progress,
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                }
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="GOAL_PROGRESS",
                    category="Goal",
                    title=f"Goal Lagging: '{goal.title}'",
                    description=f"Goal is at {int(curr_progress)}% progress (expected {int(expected_progress)}%) with {days_to_target} days left.",
                    reason=expl.to_reason_text(),
                    priority="HIGH",
                    status="PENDING",
                    action_type="FOCUS_GOAL",
                    action_payload=payload,
                    entity_id=goal.id,
                    target_date=goal.target_date,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                new_recs.append(rec)

        # Check 4C: Stagnant goal with no recent completions
        elif len(goal_tasks) > 0 and len(completed_goal_tasks) > 0:
            ten_days_ago = today - timedelta(days=10)
            recent_completions = [
                t for t in completed_goal_tasks
                if t.updated_at and t.updated_at.date() >= ten_days_ago
            ]
            if len(recent_completions) == 0 and curr_progress < 90.0:
                if not is_suppressed_fn("GOAL_PROGRESS", "Goal", goal.id, "STAGNANT"):
                    expl = StructuredExplanation(
                        what_happened=f"Zero deliverables completed for goal '{goal.title}' over the last 10 days.",
                        why_generated="Execution inertia often causes multi-week goal abandonment.",
                        suggested_action="Schedule one small 30-minute task to re-establish execution momentum.",
                        why_prioritize="Restarts forward progress before the milestone loses relevance."
                    )
                    score_res = calculate_recommendation_priority(
                        urgency_days=(goal.target_date - today).days if goal.target_date else None,
                        importance_level=goal.priority,
                        goal_relevance_pts=10.0,
                        historical_acceptance_rate=ctx.acceptance_by_type.get("GOAL_PROGRESS", 0.5),
                    )
                    payload = {
                        "goal_id": goal.id,
                        "goal_title": goal.title,
                        "sub_key": "STAGNANT",
                        "priority_score": score_res.score,
                        "score_breakdown": score_res.breakdown,
                        "explanation": expl.to_dict(),
                    }
                    rec = Recommendation(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        type="GOAL_PROGRESS",
                        category="Goal",
                        title=f"Stagnant Goal: '{goal.title}'",
                        description="No task activity recorded for this goal in over 10 days.",
                        reason=expl.to_reason_text(),
                        priority="LOW",
                        status="PENDING",
                        action_type="FOCUS_GOAL",
                        action_payload=payload,
                        entity_id=goal.id,
                        target_date=today,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    new_recs.append(rec)

    # =========================================================================
    # 5. HABIT BEHAVIOUR ANALYSIS (HABIT_IMPROVEMENT)
    # =========================================================================
    for h in ctx.habits:
        if (h.frequency or "Daily").lower() != "daily":
            continue

        streak = h.base_streak or 0
        h_logs = [hl for hl in ctx.habit_logs if hl.habit_id == h.id and hl.completed]
        done_today = any(hl.log_date == today for hl in h_logs)

        # Check 5A: Streak Protection (Active streak >= 2, not logged today)
        if streak >= 2 and not done_today:
            if not is_suppressed_fn("HABIT_IMPROVEMENT", "Habit", h.id, "STREAK_PROTECTION"):
                expl = StructuredExplanation(
                    what_happened=f"Habit '{h.name}' has an active {streak}-day streak but has not been logged today.",
                    why_generated="Daily streaks reset to zero if missed, forfeiting compound habit inertia.",
                    suggested_action=f"Complete a short session for '{h.name}' today to defend your streak.",
                    why_prioritize=f"Preserving a {streak}-day streak builds automaticity and long-term self-discipline."
                )
                score_res = calculate_recommendation_priority(
                    urgency_days=0,
                    importance_level="High" if streak >= 3 else "Medium",
                    habit_impact_pts=15.0 if streak >= 3 else 10.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("HABIT_IMPROVEMENT", 0.5),
                )
                payload = {
                    "habit_id": h.id,
                    "habit_title": h.name,
                    "sub_key": "STREAK_PROTECTION",
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                }
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="HABIT_IMPROVEMENT",
                    category="Habit",
                    title=f"Protect Streak: '{h.name}'",
                    description=f"You have an active {streak}-day streak on '{h.name}'. Complete today's session to keep it alive.",
                    reason=expl.to_reason_text(),
                    priority=score_res.level,
                    status="PENDING",
                    action_type="TRACK_HABIT",
                    action_payload=payload,
                    entity_id=h.id,
                    target_date=today,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                new_recs.append(rec)

        # Check 5B: Habit Recovery (Declining consistency, 2+ days missed in last 4 days)
        last_4_days = [today - timedelta(days=i) for i in range(1, 5)]
        logged_dates = {hl.log_date for hl in h_logs}
        completed_days = [d for d in last_4_days if d in logged_dates]
        missed_count = 4 - len(completed_days)

        if missed_count >= 2 and not done_today and streak < 3:
            if not is_suppressed_fn("HABIT_IMPROVEMENT", "Habit", h.id, "HABIT_RECOVERY"):
                expl = StructuredExplanation(
                    what_happened=f"Habit '{h.name}' was missed on {missed_count} of the last 4 days.",
                    why_generated="Adherence decay accelerates rapidly after successive skips.",
                    suggested_action="Perform an easy 5-minute micro-session today to restart positive consistency.",
                    why_prioritize="Overcomes resumption resistance and re-anchors the daily habit loop."
                )
                score_res = calculate_recommendation_priority(
                    urgency_days=0,
                    importance_level="Medium",
                    habit_impact_pts=8.0,
                    historical_acceptance_rate=ctx.acceptance_by_type.get("HABIT_IMPROVEMENT", 0.5),
                )
                payload = {
                    "habit_id": h.id,
                    "habit_title": h.name,
                    "sub_key": "HABIT_RECOVERY",
                    "priority_score": score_res.score,
                    "score_breakdown": score_res.breakdown,
                    "explanation": expl.to_dict(),
                }
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="HABIT_IMPROVEMENT",
                    category="Habit",
                    title=f"Rebuild Momentum: '{h.name}'",
                    description=f"Consistency on '{h.name}' dropped recently ({missed_count}/4 days missed). Re-anchor it today.",
                    reason=expl.to_reason_text(),
                    priority=score_res.level,
                    status="PENDING",
                    action_type="TRACK_HABIT",
                    action_payload=payload,
                    entity_id=h.id,
                    target_date=today,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                new_recs.append(rec)

    return new_recs
