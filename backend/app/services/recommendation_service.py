import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any, Set
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

# Default dismissal cooldown window in hours
DEFAULT_COOLDOWN_HOURS = 48

# State machine: Allowed transitions
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "PENDING": {"ACCEPTED", "DISMISSED", "COMPLETED"},
    "ACCEPTED": {"COMPLETED", "DISMISSED"},
    "DISMISSED": {"COMPLETED"},
    "COMPLETED": set(),   # Terminal state: Cannot transition from COMPLETED
}

def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime object is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def get_recommendation_identity(
    rec_type: str,
    category: str,
    entity_id: Optional[str],
    sub_key: Optional[str] = "default"
) -> str:
    """
    Computes a canonical identity string for deduplication and cooldown tracking.
    Format: {rec_type}:{category}:{entity_id}:{sub_key}
    """
    ent = entity_id or "global"
    sub = sub_key or "default"
    return f"{rec_type}:{category}:{ent}:{sub}"

def validate_transition(current_status: str, target_status: str) -> None:
    """
    Validates lifecycle status transitions.
    Raises ValueError on invalid transitions.
    """
    if current_status == target_status:
        return  # Idempotent transition is permitted
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ValueError(
            f"Invalid recommendation status transition from '{current_status}' to '{target_status}'"
        )

# ---------------------------------------------------------------------------
# Recommendation Generator Engine
# ---------------------------------------------------------------------------

def generate_recommendations(
    db: Session,
    tz_offset_mins: int = 0,
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    current_time: Optional[datetime] = None,
) -> List[Recommendation]:
    """
    Evaluates historical behaviour, current workload, deadlines, and habits
    to produce deterministic, explainable recommendations.

    Features robust deduplication, 48-hour dismissal cooldown, and active
    acceptance suppression.
    """
    now = current_time or datetime.now(timezone.utc)
    now_utc = _ensure_utc(now)
    today = now_utc.date() if now_utc else date.today()
    cutoff_time = now_utc - timedelta(hours=cooldown_hours)

    new_recommendations: List[Recommendation] = []

    # 1. Sync: Auto-complete recommendations for tasks, goals, or habits that have been completed
    auto_sync_completed_entities(db, current_time=now_utc)

    # 2. Build In-Memory Suppression & Cooldown Index (Single Database Fetch)
    # Query all active (PENDING/ACCEPTED) and recently updated/dismissed recommendations
    existing_records = db.query(Recommendation).filter(
        or_(
            Recommendation.status.in_(["PENDING", "ACCEPTED"]),
            and_(
                Recommendation.status == "DISMISSED",
                Recommendation.updated_at >= cutoff_time
            )
        )
    ).all()

    # Map canonical identity -> most relevant Recommendation record
    suppression_map: Dict[str, Recommendation] = {}
    for r in existing_records:
        sub_k = (r.action_payload or {}).get("sub_key")
        if not sub_k:
            if r.type == "GOAL_PROGRESS":
                if "Structure" in r.title:
                    sub_k = "STRUCTURE"
                elif "Lagging" in r.title:
                    sub_k = "LAGGING"
                elif "Stagnant" in r.title:
                    sub_k = "STAGNANT"
                else:
                    sub_k = "default"
            elif r.type == "HABIT_IMPROVEMENT":
                if "Streak" in r.title:
                    sub_k = "STREAK_PROTECTION"
                elif "Momentum" in r.title or "Recovery" in r.title:
                    sub_k = "HABIT_RECOVERY"
                else:
                    sub_k = "default"
            else:
                sub_k = "default"

        ident = get_recommendation_identity(r.type, r.category, r.entity_id, sub_k)
        
        # Precedence: PENDING (1) > ACCEPTED (2) > DISMISSED (3)
        status_priority = {"PENDING": 1, "ACCEPTED": 2, "DISMISSED": 3}
        if ident not in suppression_map:
            suppression_map[ident] = r
        else:
            existing = suppression_map[ident]
            if status_priority.get(r.status, 9) < status_priority.get(existing.status, 9):
                suppression_map[ident] = r
            elif r.status == "DISMISSED" and existing.status == "DISMISSED":
                # Keep the most recently dismissed record
                r_updated = _ensure_utc(r.updated_at)
                ex_updated = _ensure_utc(existing.updated_at)
                if r_updated and ex_updated and r_updated > ex_updated:
                    suppression_map[ident] = r

    def is_suppressed(rec_type: str, category: str, entity_id: Optional[str], sub_key: str = "default") -> bool:
        """
        Determines whether recommendation generation is suppressed due to:
        - Active PENDING recommendation
        - Active ACCEPTED recommendation
        - Unexpired DISMISSED cooldown (within cooldown_hours)
        """
        ident = get_recommendation_identity(rec_type, category, entity_id, sub_key)
        if ident in suppression_map:
            rec = suppression_map[ident]
            if rec.status == "PENDING":
                return True
            if rec.status == "ACCEPTED":
                return True
            if rec.status == "DISMISSED":
                rec_updated = _ensure_utc(rec.updated_at)
                if rec_updated and (now_utc - rec_updated) < timedelta(hours=cooldown_hours):
                    return True
        return False

    # ---------------------------------------------------------
    # Phase 5: Dynamic Intelligent Recommendation Engine
    # ---------------------------------------------------------
    from backend.app.services.intelligence import (
        build_productivity_context,
        generate_intelligent_recommendations,
    )

    ctx = build_productivity_context(db, reference_date=today)
    intelligent_recs = generate_intelligent_recommendations(
        ctx=ctx,
        is_suppressed_fn=is_suppressed,
        now_utc=now_utc,
    )

    for rec in intelligent_recs:
        db.add(rec)
        new_recommendations.append(rec)
        sub_k = (rec.action_payload or {}).get("sub_key", "default")
        suppression_map[get_recommendation_identity(rec.type, rec.category, rec.entity_id, sub_k)] = rec

    db.commit()
    return new_recommendations

def auto_sync_completed_entities(db: Session, current_time: Optional[datetime] = None):
    """
    Synchronizes recommendations with entity status changes.
    1. If a task or goal is completed or deleted, any PENDING or ACCEPTED recommendation transitions to COMPLETED.
    2. If a habit was logged today, archived, or deleted, any PENDING or ACCEPTED habit recommendation transitions to COMPLETED.
    3. If a goal recommendation was for lack of structure (0 tasks) and tasks are now linked, it transitions to COMPLETED.
    4. If a goal recommendation was for lagging progress (<50%) and progress reaches >= 50%, it transitions to COMPLETED.
    """
    now = current_time or datetime.now(timezone.utc)
    now_utc = _ensure_utc(now)
    today = now_utc.date() if now_utc else date.today()

    active_recs = db.query(Recommendation).filter(
        Recommendation.status.in_(["PENDING", "ACCEPTED"])
    ).all()

    for rec in active_recs:
        if not rec.entity_id:
            continue
        
        if rec.category == "Task":
            task = db.query(Task).filter(Task.id == rec.entity_id).first()
            if task is None or task.status == "Completed":
                rec.status = "COMPLETED"
                rec.updated_at = now_utc
        elif rec.category == "Goal":
            goal = db.query(Goal).filter(Goal.id == rec.entity_id).first()
            if goal is None or goal.status == "Completed" or (goal.progress or 0) >= 100:
                rec.status = "COMPLETED"
                rec.updated_at = now_utc
            else:
                sub_key = (rec.action_payload or {}).get("sub_key", "")
                if sub_key == "STRUCTURE":
                    linked_count = db.query(Task).filter(Task.goal_id == goal.id).count()
                    if linked_count > 0:
                        rec.status = "COMPLETED"
                        rec.updated_at = now_utc
                elif sub_key == "LAGGING":
                    if (goal.progress or 0) >= 50:
                        rec.status = "COMPLETED"
                        rec.updated_at = now_utc
        elif rec.category == "Habit":
            habit = db.query(Habit).filter(Habit.id == rec.entity_id).first()
            if habit is None or habit.archived:
                rec.status = "COMPLETED"
                rec.updated_at = now_utc
            else:
                today_log = db.query(HabitLog).filter(
                    HabitLog.habit_id == rec.entity_id,
                    HabitLog.log_date == today,
                    HabitLog.completed == True
                ).first()
                if today_log:
                    rec.status = "COMPLETED"
                    rec.updated_at = now_utc

    db.commit()

# ---------------------------------------------------------------------------
# CRUD & User Actions with Lifecycle Validation
# ---------------------------------------------------------------------------

def get_recommendations(
    db: Session,
    status: Optional[str] = "PENDING",
    category: Optional[str] = None,
    rec_type: Optional[str] = None,
    limit: int = 50,
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    current_time: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> RecommendationSummary:
    """
    Retrieves filtered recommendations and summary metrics.
    Triggers generation respecting configured cooldown and deduplication.
    Applies sensible multi-tier prioritization.
    """
    now = current_time or datetime.now(timezone.utc)
    now_utc = _ensure_utc(now)
    today = now_utc.date() if now_utc else date.today()

    generate_recommendations(
        db=db,
        tz_offset_mins=0,
        cooldown_hours=cooldown_hours,
        current_time=current_time,
    )

    query = db.query(Recommendation).filter(Recommendation.is_deleted == False)
    if user_id:
        query = query.filter(Recommendation.user_id == user_id)
    if status and status != "ALL":
        query = query.filter(Recommendation.status == status)
    if category:
        query = query.filter(Recommendation.category == category)
    if rec_type:
        query = query.filter(Recommendation.type == rec_type)

    priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    items = query.all()

    # Enrich legacy recommendations only if any recommendation in the result lacks priority_score
    needs_enrichment = any(
        not isinstance(r.action_payload, dict) or "priority_score" not in r.action_payload
        for r in items
    )
    if needs_enrichment:
        from backend.app.services.intelligence import build_productivity_context, enrich_legacy_recommendations
        ctx = build_productivity_context(db, reference_date=today)
        enrich_legacy_recommendations(db, items, ctx)

    def _rec_sort_key(r: Recommendation):
        score = None
        if isinstance(r.action_payload, dict):
            score = r.action_payload.get("priority_score")
        score_val = -float(score) if score is not None else 0.0
        has_score = 0 if score is not None else 1

        p_val = priority_order.get(r.priority, 2)
        if r.target_date:
            diff = (r.target_date - today).days
            if diff <= 0:
                d_val = 0  # Overdue or due today
            elif diff <= 2:
                d_val = 1  # Approaching within 48h
            else:
                d_val = 2
        else:
            d_val = 3
        ts = r.created_at.timestamp() if r.created_at else 0
        return (has_score, score_val, p_val, d_val, -ts)

    items.sort(key=_rec_sort_key)
    items = items[:limit]

    active_query = db.query(Recommendation).filter(Recommendation.status == "PENDING", Recommendation.is_deleted == False)
    if user_id:
        active_query = active_query.filter(Recommendation.user_id == user_id)
    all_active = active_query.all()
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

def accept_recommendation(
    db: Session,
    rec_id: str,
    current_time: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> Optional[Recommendation]:
    """
    Accepts a recommendation. Validates status transition (PENDING -> ACCEPTED).
    If actionable (e.g. RESCHEDULE_TASK), executes modifications safely.
    Logs interaction in ActivityLog.
    """
    query = db.query(Recommendation).filter(Recommendation.id == rec_id, Recommendation.is_deleted == False)
    if user_id:
        query = query.filter(Recommendation.user_id == user_id)
    rec = query.first()
    if not rec:
        return None

    if rec.status == "ACCEPTED":
        return rec  # Idempotent

    validate_transition(rec.status, "ACCEPTED")

    now_utc = _ensure_utc(current_time) or datetime.now(timezone.utc)

    if rec.action_type == "RESCHEDULE_TASK" and rec.action_payload:
        task_id = rec.action_payload.get("task_id")
        suggested_date_str = rec.action_payload.get("suggested_date")
        if task_id and suggested_date_str:
            target_d = date.fromisoformat(suggested_date_str)
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.start_date = target_d
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
                    id=f"act_{uuid.uuid4().hex[:12]}",
                    event_type="TASK_RESCHEDULED",
                    entity_type="TASK",
                    entity_id=task.id,
                    timestamp=now_utc,
                    details={
                        "from_date": source_date_str,
                        "to_date": suggested_date_str,
                        "recommendation_id": rec.id,
                        "reason": rec.reason,
                    },
                    created_at=now_utc,
                )
                db.add(log_entry)

    # Log recommendation acceptance interaction
    act_accept = ActivityLog(
        id=f"act_{uuid.uuid4().hex[:12]}",
        event_type="RECOMMENDATION_ACCEPTED",
        entity_type="recommendation",
        entity_id=rec.id,
        timestamp=now_utc,
        details={
            "recommendation_id": rec.id,
            "type": rec.type,
            "category": rec.category,
            "target_entity_id": rec.entity_id,
            "title": rec.title,
            "action_type": rec.action_type,
        },
        created_at=now_utc,
    )
    db.add(act_accept)

    rec.status = "ACCEPTED"
    rec.version = (rec.version or 1) + 1
    rec.updated_at = now_utc
    db.commit()
    db.refresh(rec)
    return rec

def dismiss_recommendation(
    db: Session,
    rec_id: str,
    current_time: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> Optional[Recommendation]:
    """
    Dismisses a recommendation. Validates status transition (PENDING -> DISMISSED).
    Sets updated_at to enforce cooldown suppression.
    Logs interaction in ActivityLog.
    """
    query = db.query(Recommendation).filter(Recommendation.id == rec_id, Recommendation.is_deleted == False)
    if user_id:
        query = query.filter(Recommendation.user_id == user_id)
    rec = query.first()
    if not rec:
        return None

    if rec.status == "DISMISSED":
        return rec  # Idempotent

    validate_transition(rec.status, "DISMISSED")

    now_utc = _ensure_utc(current_time) or datetime.now(timezone.utc)

    # Log recommendation dismissal interaction
    act_dismiss = ActivityLog(
        id=f"act_{uuid.uuid4().hex[:12]}",
        event_type="RECOMMENDATION_DISMISSED",
        entity_type="recommendation",
        entity_id=rec.id,
        timestamp=now_utc,
        details={
            "recommendation_id": rec.id,
            "type": rec.type,
            "category": rec.category,
            "target_entity_id": rec.entity_id,
            "title": rec.title,
        },
        created_at=now_utc,
    )
    db.add(act_dismiss)

    rec.status = "DISMISSED"
    rec.version = (rec.version or 1) + 1
    rec.updated_at = now_utc
    db.commit()
    db.refresh(rec)
    return rec

def complete_recommendation(
    db: Session,
    rec_id: str,
    current_time: Optional[datetime] = None,
    user_id: Optional[str] = None,
) -> Optional[Recommendation]:
    """
    Marks a recommendation as COMPLETED.
    Validates status transition (PENDING/ACCEPTED -> COMPLETED).
    Logs interaction in ActivityLog.
    """
    query = db.query(Recommendation).filter(Recommendation.id == rec_id, Recommendation.is_deleted == False)
    if user_id:
        query = query.filter(Recommendation.user_id == user_id)
    rec = query.first()
    if not rec:
        return None

    if rec.status == "COMPLETED":
        return rec  # Idempotent

    validate_transition(rec.status, "COMPLETED")

    now_utc = _ensure_utc(current_time) or datetime.now(timezone.utc)

    # Log recommendation completion interaction
    act_complete = ActivityLog(
        id=f"act_{uuid.uuid4().hex[:12]}",
        event_type="RECOMMENDATION_COMPLETED",
        entity_type="recommendation",
        entity_id=rec.id,
        timestamp=now_utc,
        details={
            "recommendation_id": rec.id,
            "type": rec.type,
            "category": rec.category,
            "target_entity_id": rec.entity_id,
            "title": rec.title,
        },
        created_at=now_utc,
    )
    db.add(act_complete)

    rec.status = "COMPLETED"
    rec.version = (rec.version or 1) + 1
    rec.updated_at = now_utc
    db.commit()
    db.refresh(rec)
    return rec
