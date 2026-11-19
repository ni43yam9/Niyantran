import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from backend.app.models.recommendation import Recommendation
from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.recommendation import RecommendationSummary

logger = logging.getLogger(__name__)

# Daily capacity threshold in minutes (6.0 hours default sustainable load)
MAX_DAILY_LOAD_MINUTES = 360
LIGHT_DAY_LOAD_MINUTES = 240

# ---------------------------------------------------------------------------
# Recommendation Generator Engine
# ---------------------------------------------------------------------------

def generate_recommendations(db: Session, tz_offset_mins: int = 0) -> List[Recommendation]:
    """
    Evaluates historical behaviour, current workload, deadlines, and habits
    to produce deterministic, explainable recommendations.
    Deduplicates against active PENDING recommendations.
    """
    today = date.today()
    new_recommendations: List[Recommendation] = []

    # Helper to check if a pending recommendation already exists
    def has_pending_rec(rec_type: str, entity_id: Optional[str] = None, title: Optional[str] = None) -> bool:
        query = db.query(Recommendation).filter(
            Recommendation.status == "PENDING",
            Recommendation.type == rec_type
        )
        if entity_id:
            query = query.filter(Recommendation.entity_id == entity_id)
        if title:
            query = query.filter(Recommendation.title == title)
        return query.first() is not None

    # Sync: Auto-complete recommendations for tasks or goals that have been completed
    auto_sync_completed_entities(db)

    # ---------------------------------------------------------
    # RULE SET 1: Intelligent Task Prioritization (PRIORITIZATION)
    # ---------------------------------------------------------
    pending_tasks = db.query(Task).filter(Task.status != "Completed").all()

    # Find critical tasks due within 48 hours or overdue
    urgent_tasks = []
    for t in pending_tasks:
        if t.due_date:
            days_left = (t.due_date - today).days
            if days_left <= 2:  # Due today, tomorrow, or overdue
                urgent_tasks.append((days_left, t))
    
    # Sort by urgency (overdue first, then High priority)
    urgent_tasks.sort(key=lambda x: (x[0], 0 if x[1].priority == "High" else 1))

    for days_left, task in urgent_tasks[:2]:  # Top 2 high priority items
        if not has_pending_rec("PRIORITIZATION", entity_id=task.id):
            if days_left < 0:
                rec_title = f"Immediate Focus: Overdue '{task.title}'"
                rec_desc = f"Task is {abs(days_left)} day(s) overdue. Prioritize completion in your morning focus block."
                rec_reason = f"Due date was {task.due_date}. Overdue deliverables disrupt weekly milestone completion."
                priority_lvl = "HIGH"
            elif days_left == 0:
                rec_title = f"Due Today: '{task.title}'"
                rec_desc = f"Task deadline expires today. Reserve deep-work capacity before afternoon commitments."
                rec_reason = f"Urgent deadline scheduled for today with priority '{task.priority}'."
                priority_lvl = "HIGH"
            else:
                rec_title = f"Due in 24-48h: '{task.title}'"
                rec_desc = f"Deadline approaching in {days_left} day(s). Finish now to avoid last-minute rush."
                rec_reason = f"Proximity to deadline ({task.due_date}) requires timely execution."
                priority_lvl = "MEDIUM"

            rec = Recommendation(
                id=f"rec_{uuid.uuid4().hex[:12]}",
                type="PRIORITIZATION",
                category="Task",
                title=rec_title,
                description=rec_desc,
                reason=rec_reason,
                priority=priority_lvl,
                status="PENDING",
                action_type="FOCUS_TASK",
                action_payload={"task_id": task.id, "suggested_window": "Morning (09:00 - 12:00)"},
                entity_id=task.id,
                target_date=today,
            )
            db.add(rec)
            new_recommendations.append(rec)

    # ---------------------------------------------------------
    # RULE SET 2: Workload Balancing (WORKLOAD_BALANCE)
    # ---------------------------------------------------------
    # Calculate daily workload over the next 7 days
    days_to_check = [today + timedelta(days=i) for i in range(7)]
    daily_loads: Dict[date, int] = {}
    daily_tasks_map: Dict[date, List[Task]] = {d: [] for d in days_to_check}

    # Sum up timeblocks
    for d in days_to_check:
        tb_duration = (
            db.query(func.coalesce(func.sum(DailyTimeblock.duration_minutes), 0))
            .filter(DailyTimeblock.block_date == d)
            .scalar()
            or 0
        )
        daily_loads[d] = int(tb_duration)

    # Map pending tasks by start_date or due_date
    for t in pending_tasks:
        t_date = t.start_date or t.due_date or today
        if t_date in daily_tasks_map:
            daily_tasks_map[t_date].append(t)
            # Estimate 60 mins if no timeblocks exist
            has_tb = db.query(DailyTimeblock).filter(DailyTimeblock.task_id == t.id).first() is not None
            if not has_tb:
                daily_loads[t_date] += 60

    # Detect overloaded days (> 360 mins)
    for d in days_to_check:
        if daily_loads[d] > MAX_DAILY_LOAD_MINUTES and daily_tasks_map[d]:
            # Find candidate task to move (lowest priority, non-urgent deadline)
            candidates = sorted(
                daily_tasks_map[d],
                key=lambda x: (
                    1 if x.priority == "High" else 2,
                    (x.due_date - today).days if x.due_date else 999
                ),
                reverse=True
            )
            
            task_to_move = None
            for cand in candidates:
                # Must not have deadline expiring on or before d
                if cand.due_date and cand.due_date <= d:
                    continue
                task_to_move = cand
                break

            if task_to_move:
                # Find the next lighter day
                lighter_day = None
                for future_day in days_to_check:
                    if future_day > d and daily_loads[future_day] < LIGHT_DAY_LOAD_MINUTES:
                        if not task_to_move.due_date or future_day <= task_to_move.due_date:
                            lighter_day = future_day
                            break

                if lighter_day and not has_pending_rec("WORKLOAD_BALANCE", entity_id=task_to_move.id):
                    hrs_over = daily_loads[d] / 60.0
                    hrs_light = daily_loads[lighter_day] / 60.0
                    rec = Recommendation(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        type="WORKLOAD_BALANCE",
                        category="Schedule",
                        title=f"Balance Workload: Reschedule '{task_to_move.title}'",
                        description=f"Move '{task_to_move.title}' from {d.strftime('%a, %b %d')} to {lighter_day.strftime('%a, %b %d')} to prevent overload.",
                        reason=(
                            f"{d.strftime('%a, %b %d')} has {hrs_over:.1f} hours of planned effort (threshold: 6.0 hrs). "
                            f"{lighter_day.strftime('%a, %b %d')} has available capacity ({hrs_light:.1f} hrs planned)."
                        ),
                        priority="MEDIUM",
                        status="PENDING",
                        action_type="RESCHEDULE_TASK",
                        action_payload={
                            "task_id": task_to_move.id,
                            "source_date": str(d),
                            "suggested_date": str(lighter_day),
                        },
                        entity_id=task_to_move.id,
                        target_date=d,
                    )
                    db.add(rec)
                    new_recommendations.append(rec)

    # ---------------------------------------------------------
    # RULE SET 3: Deadline Risk Detection (DEADLINE_RISK)
    # ---------------------------------------------------------
    # Check historical postponement count from ActivityLog
    postponement_counts = dict(
        db.query(ActivityLog.entity_id, func.count(ActivityLog.id))
        .filter(ActivityLog.event_type == "TASK_POSTPONED")
        .group_by(ActivityLog.entity_id)
        .all()
    )

    # Check estimation variance from DailyTimeblocks
    timeblocks_with_actuals = (
        db.query(DailyTimeblock)
        .filter(DailyTimeblock.status == "Completed", DailyTimeblock.actual_duration_minutes.isnot(None))
        .all()
    )
    bias_ratio = 1.0
    if len(timeblocks_with_actuals) >= 3:
        total_est = sum(tb.duration_minutes for tb in timeblocks_with_actuals if tb.duration_minutes > 0)
        total_act = sum(tb.actual_duration_minutes for tb in timeblocks_with_actuals if tb.actual_duration_minutes)
        if total_est > 0:
            bias_ratio = max(1.0, round(total_act / total_est, 2))

    for task in pending_tasks:
        if not task.due_date:
            continue
        days_remaining = (task.due_date - today).days
        if 0 <= days_remaining <= 5:
            postpone_times = postponement_counts.get(task.id, 0)
            
            # Find linked timeblock duration or default 60 mins
            tb = db.query(DailyTimeblock).filter(DailyTimeblock.task_id == task.id).first()
            est_time = tb.duration_minutes if tb else 60
            adjusted_effort = est_time * bias_ratio
            
            # Risk triggers:
            # 1. Postponed at least once and due within 3 days
            # 2. Or high effort (>180 mins) due within 2 days with bias
            is_high_risk = (postpone_times >= 1 and days_remaining <= 3) or (adjusted_effort >= 180 and days_remaining <= 2)
            
            if is_high_risk and not has_pending_rec("DEADLINE_RISK", entity_id=task.id):
                bias_pct = int((bias_ratio - 1.0) * 100)
                reason_parts = [f"Deadline is in {days_remaining} day(s) on {task.due_date}."]
                if postpone_times > 0:
                    reason_parts.append(f"Task has been postponed {postpone_times} time(s).")
                if bias_pct > 0:
                    reason_parts.append(f"Historical estimation bias (+{bias_pct}%) projects {int(adjusted_effort)} minutes required.")

                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="DEADLINE_RISK",
                    category="Task",
                    title=f"Deadline Alert: '{task.title}' at Risk",
                    description=f"High risk of deadline slippage. Allocate dedicated focus block before {task.due_date}.",
                    reason=" ".join(reason_parts),
                    priority="HIGH",
                    status="PENDING",
                    action_type="EXPEDITE_TASK",
                    action_payload={"task_id": task.id, "deadline": str(task.due_date), "urgency": "HIGH"},
                    entity_id=task.id,
                    target_date=task.due_date,
                )
                db.add(rec)
                new_recommendations.append(rec)

    # ---------------------------------------------------------
    # RULE SET 4: Goal Progress Intelligence (GOAL_PROGRESS)
    # ---------------------------------------------------------
    active_goals = db.query(Goal).filter(Goal.status == "In Progress").all()
    for goal in active_goals:
        goal_tasks = db.query(Task).filter(Task.goal_id == goal.id).all()
        completed_goal_tasks = [t for t in goal_tasks if t.status == "Completed"]
        
        # Check 1: Goal has 0 linked tasks
        if len(goal_tasks) == 0:
            if not has_pending_rec("GOAL_PROGRESS", entity_id=goal.id, title=f"Structure Goal: '{goal.title}'"):
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="GOAL_PROGRESS",
                    category="Goal",
                    title=f"Structure Goal: '{goal.title}'",
                    description="This active goal has no actionable deliverables assigned to it.",
                    reason="Goals with concrete subtasks have a 3.4x higher completion rate. Break this goal into 2-3 specific tasks.",
                    priority="MEDIUM",
                    status="PENDING",
                    action_type="ADD_GOAL_TASK",
                    action_payload={"goal_id": goal.id, "goal_title": goal.title},
                    entity_id=goal.id,
                    target_date=today,
                )
                db.add(rec)
                new_recommendations.append(rec)

        # Check 2: Goal progress lagging behind target deadline
        elif goal.target_date:
            days_to_target = (goal.target_date - today).days
            if days_to_target <= 14 and goal.progress < 50:
                if not has_pending_rec("GOAL_PROGRESS", entity_id=goal.id, title=f"Goal Lagging: '{goal.title}'"):
                    rec = Recommendation(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        type="GOAL_PROGRESS",
                        category="Goal",
                        title=f"Goal Lagging: '{goal.title}'",
                        description=f"Goal is at {goal.progress}% progress with deadline in {days_to_target} days.",
                        reason=(
                            f"Target deadline ({goal.target_date}) is approaching. "
                            f"{len(completed_goal_tasks)} of {len(goal_tasks)} deliverables completed."
                        ),
                        priority="HIGH",
                        status="PENDING",
                        action_type="FOCUS_GOAL",
                        action_payload={"goal_id": goal.id, "goal_title": goal.title},
                        entity_id=goal.id,
                        target_date=goal.target_date,
                    )
                    db.add(rec)
                    new_recommendations.append(rec)

        # Check 3: Stagnant goal with no task completions in the last 10 days
        elif len(goal_tasks) > 0 and len(completed_goal_tasks) > 0:
            ten_days_ago = today - timedelta(days=10)
            recent_task_completions = [
                t for t in completed_goal_tasks
                if t.updated_at and t.updated_at.date() >= ten_days_ago
            ]
            if len(recent_task_completions) == 0 and goal.progress < 90:
                if not has_pending_rec("GOAL_PROGRESS", entity_id=goal.id, title=f"Stagnant Goal: '{goal.title}'"):
                    rec = Recommendation(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        type="GOAL_PROGRESS",
                        category="Goal",
                        title=f"Stagnant Goal: '{goal.title}'",
                        description="No task activity recorded for this goal in over 10 days.",
                        reason="Momentum has stalled. Schedule a brief 30-minute focus session to advance progress.",
                        priority="LOW",
                        status="PENDING",
                        action_type="FOCUS_GOAL",
                        action_payload={"goal_id": goal.id, "goal_title": goal.title},
                        entity_id=goal.id,
                        target_date=today,
                    )
                    db.add(rec)
                    new_recommendations.append(rec)

    # ---------------------------------------------------------
    # RULE SET 5: Habit Improvement (HABIT_IMPROVEMENT)
    # ---------------------------------------------------------
    habits = db.query(Habit).filter(Habit.archived == False).all()
    for h in habits:
        # Check logs in last 4 days
        four_days_ago = today - timedelta(days=4)
        recent_logs = (
            db.query(HabitLog)
            .filter(HabitLog.habit_id == h.id, HabitLog.log_date >= four_days_ago)
            .all()
        )
        completed_days = {log.log_date for log in recent_logs if log.completed}
        
        # Check if completed today
        done_today = today in completed_days

        # Rule 5A: Streak Protection (active streak >= 3 and not logged today)
        if (h.base_streak or 0) >= 3 and not done_today:
            if not has_pending_rec("HABIT_IMPROVEMENT", entity_id=h.id, title=f"Protect Streak: '{h.name}'"):
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="HABIT_IMPROVEMENT",
                    category="Habit",
                    title=f"Protect Streak: '{h.name}'",
                    description=f"You have an active {h.base_streak}-day streak on '{h.name}'. Don't miss today's check-in!",
                    reason=f"Consistent streaks build automaticity. Completing today secures your {h.base_streak + 1}-day record.",
                    priority="HIGH",
                    status="PENDING",
                    action_type="TRACK_HABIT",
                    action_payload={"habit_id": h.id, "habit_title": h.name},
                    entity_id=h.id,
                    target_date=today,
                )
                db.add(rec)
                new_recommendations.append(rec)

        # Rule 5B: Habit Recovery (missed 2 or more of last 4 days)
        missed_count = 4 - len(completed_days)
        if missed_count >= 2 and not done_today and (h.base_streak or 0) < 3:
            if not has_pending_rec("HABIT_IMPROVEMENT", entity_id=h.id, title=f"Rebuild Momentum: '{h.name}'"):
                rec = Recommendation(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    type="HABIT_IMPROVEMENT",
                    category="Habit",
                    title=f"Rebuild Momentum: '{h.name}'",
                    description=f"Consistency on '{h.name}' dropped recently ({missed_count}/4 days missed). Re-anchor it today.",
                    reason="Habit adherence decays rapidly after successive missed days. Complete one easy session today to restart.",
                    priority="MEDIUM",
                    status="PENDING",
                    action_type="TRACK_HABIT",
                    action_payload={"habit_id": h.id, "habit_title": h.name},
                    entity_id=h.id,
                    target_date=today,
                )
                db.add(rec)
                new_recommendations.append(rec)

    db.commit()
    return new_recommendations

def auto_sync_completed_entities(db: Session):
    """
    If a task or goal associated with a pending recommendation is already completed,
    mark the recommendation as COMPLETED.
    """
    pending_recs = db.query(Recommendation).filter(Recommendation.status == "PENDING").all()
    for rec in pending_recs:
        if not rec.entity_id:
            continue
        if rec.category == "Task":
            task = db.query(Task).filter(Task.id == rec.entity_id).first()
            if task and task.status == "Completed":
                rec.status = "COMPLETED"
        elif rec.category == "Goal":
            goal = db.query(Goal).filter(Goal.id == rec.entity_id).first()
            if goal and (goal.status == "Completed" or goal.progress >= 100):
                rec.status = "COMPLETED"

    db.commit()

# ---------------------------------------------------------------------------
# CRUD & User Actions
# ---------------------------------------------------------------------------

def get_recommendations(
    db: Session,
    status: Optional[str] = "PENDING",
    category: Optional[str] = None,
    rec_type: Optional[str] = None,
    limit: int = 50,
) -> RecommendationSummary:
    """
    Retrieves filtered recommendations and summary counts.
    """
    # Ensure fresh analysis is available
    generate_recommendations(db)

    query = db.query(Recommendation)
    if status and status != "ALL":
        query = query.filter(Recommendation.status == status)
    if category:
        query = query.filter(Recommendation.category == category)
    if rec_type:
        query = query.filter(Recommendation.type == rec_type)

    priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    items = query.all()
    items.sort(key=lambda r: (priority_order.get(r.priority, 2), -r.created_at.timestamp()))

    items = items[:limit]

    all_active = db.query(Recommendation).filter(Recommendation.status == "PENDING").all()
    total_active = len(all_active)
    high_priority_count = sum(1 for r in all_active if r.priority == "HIGH")
    
    by_type: Dict[str, int] = {}
    for r in all_active:
        by_type[r.type] = by_type.get(r.type, 0) + 1

    return RecommendationSummary(
        total_active=total_active,
        high_priority_count=high_priority_count,
        by_type=by_type,
        items=items,
    )

def accept_recommendation(db: Session, rec_id: str) -> Optional[Recommendation]:
    """
    Accepts a recommendation. If it is an actionable recommendation (e.g. RESCHEDULE_TASK),
    safely executes the scheduling modification and logs an activity.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        return None

    if rec.action_type == "RESCHEDULE_TASK" and rec.action_payload:
        task_id = rec.action_payload.get("task_id")
        suggested_date_str = rec.action_payload.get("suggested_date")
        if task_id and suggested_date_str:
            target_d = date.fromisoformat(suggested_date_str)
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.start_date = target_d
                # Also move due_date forward if start_date exceeds due_date
                if task.due_date and task.due_date < target_d:
                    task.due_date = target_d

                source_date_str = rec.action_payload.get("source_date")
                if source_date_str:
                    src_d = date.fromisoformat(source_date_str)
                    tb = db.query(DailyTimeblock).filter(
                        DailyTimeblock.task_id == task_id,
                        DailyTimeblock.block_date == src_d
                    ).first()
                    if tb:
                        tb.block_date = target_d

                log_entry = ActivityLog(
                    event_type="TASK_RESCHEDULED",
                    entity_type="TASK",
                    entity_id=task.id,
                    details={
                        "from_date": source_date_str,
                        "to_date": suggested_date_str,
                        "recommendation_id": rec.id,
                        "reason": rec.reason,
                    }
                )
                db.add(log_entry)

    rec.status = "ACCEPTED"
    rec.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec

def dismiss_recommendation(db: Session, rec_id: str) -> Optional[Recommendation]:
    """
    Dismisses a recommendation.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        return None

    rec.status = "DISMISSED"
    rec.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec

def complete_recommendation(db: Session, rec_id: str) -> Optional[Recommendation]:
    """
    Marks a recommendation as COMPLETED.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        return None

    rec.status = "COMPLETED"
    rec.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec
