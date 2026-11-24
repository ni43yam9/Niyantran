import logging
import math
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.recommendation import Recommendation
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.adaptive import RecommendationReceptivityPattern
from backend.app.services.adaptive.confidence_manager import (
    MIN_INTERACTIONS_REC_WEIGHTS,
    calculate_sample_confidence,
)

logger = logging.getLogger(__name__)

REC_TYPES = [
    "PRIORITIZATION",
    "DEADLINE_RISK",
    "WORKLOAD_BALANCE",
    "GOAL_PROGRESS",
    "HABIT_IMPROVEMENT",
]

def analyze_recommendation_interactions(
    db: Session,
    now_utc: Optional[datetime] = None,
) -> RecommendationReceptivityPattern:
    """
    Analyzes user interaction history across all recommendation types and categories.
    Calculates acceptance, dismissal, and execution rates, and produces adaptive
    weight multipliers with exponential time-decay on dismissal penalties.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()

    # Query all recommendations
    all_recs = db.query(Recommendation).all()
    total_recs = len(all_recs)

    # Activity log interactions
    interaction_logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.event_type.in_([
            "RECOMMENDATION_ACCEPTED",
            "RECOMMENDATION_DISMISSED",
            "RECOMMENDATION_COMPLETED",
        ]))
        .order_by(ActivityLog.timestamp.desc())
        .all()
    )

    # Count by type
    accepted_by_type: Dict[str, int] = {t: 0 for t in REC_TYPES}
    dismissed_by_type: Dict[str, int] = {t: 0 for t in REC_TYPES}
    completed_by_type: Dict[str, int] = {t: 0 for t in REC_TYPES}
    last_dismissal_by_type: Dict[str, Optional[datetime]] = {t: None for t in REC_TYPES}

    for rec in all_recs:
        rtype = rec.type
        if rtype in accepted_by_type:
            if rec.status == "ACCEPTED":
                accepted_by_type[rtype] += 1
            elif rec.status == "DISMISSED":
                dismissed_by_type[rtype] += 1
                if rec.updated_at:
                    if last_dismissal_by_type[rtype] is None or rec.updated_at > last_dismissal_by_type[rtype]:
                        last_dismissal_by_type[rtype] = rec.updated_at
            elif rec.status == "COMPLETED":
                completed_by_type[rtype] += 1

    # Ignored: PENDING and older than 3 days
    ignored_count = 0
    cutoff_ignored = now - timedelta(days=3)
    for rec in all_recs:
        if rec.status == "PENDING" and rec.created_at:
            cat = rec.created_at
            if cat.tzinfo is None:
                cat = cat.replace(tzinfo=timezone.utc)
            if cat < cutoff_ignored:
                ignored_count += 1

    total_accepted = sum(accepted_by_type.values())
    total_dismissed = sum(dismissed_by_type.values())
    total_completed = sum(completed_by_type.values())
    total_interactions = total_accepted + total_dismissed + total_completed

    overall_acceptance_rate = (
        round(((total_accepted + total_completed) / max(1, total_interactions)) * 100.0, 1)
        if total_interactions > 0
        else 0.0
    )
    overall_dismissal_rate = (
        round((total_dismissed / max(1, total_interactions)) * 100.0, 1)
        if total_interactions > 0
        else 0.0
    )
    overall_execution_rate = (
        round((total_completed / max(1, total_accepted + total_completed)) * 100.0, 1)
        if (total_accepted + total_completed) > 0
        else 0.0
    )

    # Compute per-type metrics and adaptive weights
    receptivity_by_type: Dict[str, Dict[str, Any]] = {}
    adaptive_type_weights: Dict[str, float] = {}
    type_receptivity_scores: Dict[str, float] = {}

    for rtype in REC_TYPES:
        acc = accepted_by_type[rtype]
        dis = dismissed_by_type[rtype]
        comp = completed_by_type[rtype]
        n_type = acc + dis + comp

        if n_type == 0:
            receptivity_by_type[rtype] = {
                "interactions": 0,
                "acceptance_rate": 0.0,
                "dismissal_rate": 0.0,
                "execution_rate": 0.0,
                "adaptive_weight": 1.0,
                "penalty_decay": 0.0,
                "status": "NEUTRAL",
            }
            adaptive_type_weights[rtype] = 1.0
            continue

        acc_rate = (acc + comp) / n_type
        dis_rate = dis / n_type
        exec_rate = comp / max(1, acc + comp)

        # Time-decay on dismissal penalty (half-life = 7 days)
        last_dis = last_dismissal_by_type[rtype]
        penalty_decay = 1.0
        if last_dis:
            if last_dis.tzinfo is None:
                last_dis = last_dis.replace(tzinfo=timezone.utc)
            delta_days = max(0.0, (now - last_dis).total_seconds() / 86400.0)
            penalty_decay = math.pow(2.0, -delta_days / 7.0)

        # Baseline weight = 1.0
        # If interactions >= MIN_INTERACTIONS_REC_WEIGHTS, modulate weight
        if n_type >= MIN_INTERACTIONS_REC_WEIGHTS:
            if dis_rate >= 0.60:
                # Dampen weight according to dismissal rate and decay
                dampening = (dis_rate - 0.50) * 0.8 * penalty_decay
                weight = max(0.40, round(1.0 - dampening, 2))
                status = "DAMPENED"
            elif acc_rate >= 0.60 and exec_rate >= 0.50:
                # Boost weight for proven helpful suggestions
                boost = (acc_rate - 0.50) * 0.5 + (exec_rate - 0.50) * 0.3
                weight = min(1.40, round(1.0 + boost, 2))
                status = "BOOSTED"
            else:
                weight = 1.0
                status = "BALANCED"
        else:
            weight = 1.0
            status = "INSUFFICIENT_DATA"

        receptivity_by_type[rtype] = {
            "interactions": n_type,
            "acceptance_rate": round(acc_rate * 100.0, 1),
            "dismissal_rate": round(dis_rate * 100.0, 1),
            "execution_rate": round(exec_rate * 100.0, 1),
            "adaptive_weight": weight,
            "penalty_decay": round(penalty_decay, 2),
            "status": status,
        }
        adaptive_type_weights[rtype] = weight
        type_receptivity_scores[rtype] = acc_rate * 0.6 + exec_rate * 0.4 - dis_rate * 0.3

    # Find favored and dismissed types
    favored = max(type_receptivity_scores.items(), key=lambda x: x[1]) if type_receptivity_scores else None
    dismissed = min(type_receptivity_scores.items(), key=lambda x: x[1]) if type_receptivity_scores else None

    most_favored_type = favored[0] if (favored and receptivity_by_type[favored[0]]["interactions"] >= 2) else None
    most_dismissed_type = dismissed[0] if (dismissed and receptivity_by_type[dismissed[0]]["interactions"] >= 2 and dismissed[1] < 0.2) else None

    has_data = total_interactions >= MIN_INTERACTIONS_REC_WEIGHTS
    confidence = calculate_sample_confidence(total_interactions, 10) if has_data else 0.15

    evidence: List[str] = [
        f"Interactions tracked: {total_interactions} total ({total_accepted} accepted, {total_completed} completed, {total_dismissed} dismissed).",
        f"Overall execution rate of accepted suggestions: {overall_execution_rate}%.",
    ]
    if ignored_count > 0:
        evidence.append(f"Passively ignored suggestions (>3d pending): {ignored_count}.")
    if most_favored_type:
        evidence.append(f"Highest receptivity category: '{most_favored_type}' (adaptive weight: {adaptive_type_weights[most_favored_type]}x).")
    if most_dismissed_type:
        evidence.append(
            f"Consistently resisted category: '{most_dismissed_type}' (dampened to {adaptive_type_weights[most_dismissed_type]}x with 7-day decay recovery)."
        )
    if not has_data:
        evidence.append("Insufficient recommendation feedback history to modulate adaptive weights.")

    return RecommendationReceptivityPattern(
        total_interactions=total_interactions,
        acceptance_rate=overall_acceptance_rate,
        dismissal_rate=overall_dismissal_rate,
        execution_rate=overall_execution_rate,
        ignored_count=ignored_count,
        receptivity_by_type=receptivity_by_type,
        adaptive_type_weights=adaptive_type_weights,
        most_favored_type=most_favored_type,
        most_dismissed_type=most_dismissed_type,
        confidence=confidence,
        sample_size=total_interactions,
        has_sufficient_data=has_data,
        evidence=evidence,
    )

def is_entity_action_suppressed(
    db: Session,
    entity_id: str,
    action_type: str,
    rejection_threshold: int = 3,
    cooldown_days: int = 7,
    now_utc: Optional[datetime] = None,
) -> bool:
    """
    Checks if a specific entity-action combination has been dismissed repeatedly
    (>= rejection_threshold times within cooldown_days).
    Guarantees that consistently rejected suggestions are suppressed,
    while allowing dismissal penalty decay after the cooldown expires.
    """
    if not entity_id or not action_type:
        return False

    now = now_utc or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cooldown_days)

    dismissals = (
        db.query(ActivityLog)
        .filter(
            ActivityLog.event_type == "RECOMMENDATION_DISMISSED",
            ActivityLog.timestamp >= cutoff,
        )
        .all()
    )

    matching_dismissals = 0
    for d in dismissals:
        det = d.details or {}
        if det.get("target_entity_id") == entity_id or det.get("entity_id") == entity_id:
            if det.get("action_type") == action_type or not action_type:
                matching_dismissals += 1

    return matching_dismissals >= rejection_threshold
