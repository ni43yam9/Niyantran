import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.models.recommendation import Recommendation
from backend.app.schemas.analytics import ProductivityInsight, InsightsResponse

logger = logging.getLogger(__name__)

def generate_actionable_analytics_insights(
    db: Session,
    tz_offset_mins: int = 0,
    reference_date: Optional[date] = None,
) -> InsightsResponse:
    """
    Synthesizes data-backed actionable analytical insights across timing, habit momentum,
    goal velocities, and postponement patterns.
    CRITICAL INVARIANT: Deduplicates against existing active recommendations in the Recommendation
    table to avoid presenting redundant alerts to the user.
    """
    today = reference_date or date.today()
    insights: List[ProductivityInsight] = []

    tasks = db.query(Task).all()
    completed_tasks = [t for t in tasks if t.status == "Completed"]
    pending_tasks = [t for t in tasks if t.status != "Completed"]
    total_tasks = len(tasks)

    # Query existing active recommendations to prevent duplicate insights
    active_recs = db.query(Recommendation).filter(Recommendation.status == "PENDING").all()
    active_rec_titles = {r.title.lower() for r in active_recs}

    # 1. Timing Insight: Morning vs Evening Velocity
    if len(completed_tasks) >= 3:
        morning_count = 0
        afternoon_count = 0
        evening_count = 0
        for t in completed_tasks:
            if t.completed_at:
                local_dt = t.completed_at + timedelta(minutes=tz_offset_mins)
                h = local_dt.hour
                if 6 <= h < 12:
                    morning_count += 1
                elif 12 <= h < 18:
                    afternoon_count += 1
                elif 18 <= h < 23:
                    evening_count += 1

        if morning_count >= 2 and morning_count > evening_count and morning_count > afternoon_count:
            insights.append(
                ProductivityInsight(
                    id="ins-timing-morning-peak",
                    type="positive",
                    category="Timing",
                    title="Higher Morning Output",
                    description=(
                        f"Your completion velocity is highest during morning hours ({morning_count} completions). "
                        "Frontload high-cognitive coding and academic deliverables before noon."
                    ),
                    impact="High",
                )
            )
        elif evening_count >= 2 and evening_count > morning_count:
            insights.append(
                ProductivityInsight(
                    id="ins-timing-evening-peak",
                    type="neutral",
                    category="Timing",
                    title="Peak Evening Concentration",
                    description=(
                        f"You resolve the majority of deliverables between 6:00 PM and 11:00 PM ({evening_count} completions). "
                        "Protect this focused evening window from interruptions."
                    ),
                    impact="Medium",
                )
            )

    # 2. Habit Consistency Momentum or Risk
    habits = db.query(Habit).filter(Habit.archived == False).all()
    if habits:
        start_7d = today - timedelta(days=7)
        start_14d = today - timedelta(days=14)

        logs_7d = db.query(func.count(HabitLog.id)).filter(HabitLog.completed == True, HabitLog.log_date >= start_7d).scalar() or 0
        logs_14d = db.query(func.count(HabitLog.id)).filter(HabitLog.completed == True, HabitLog.log_date >= start_14d).scalar() or 0

        poss_7 = len(habits) * 7
        poss_14 = len(habits) * 14
        adh_7 = (logs_7d / max(1, poss_7)) * 100.0
        adh_14 = (logs_14d / max(1, poss_14)) * 100.0

        if adh_7 >= 70.0:
            insights.append(
                ProductivityInsight(
                    id="ins-habit-high-consistency",
                    type="positive",
                    category="Habit",
                    title="Habit Consistency Compounding",
                    description=f"Your trailing 7-day habit adherence reached {round(adh_7)}%. Ritual regularity builds automated momentum.",
                    impact="Medium",
                )
            )
        elif adh_7 < adh_14 - 15.0 and adh_14 > 40.0:
            insights.append(
                ProductivityInsight(
                    id="ins-habit-dip-warning",
                    type="warning",
                    category="Habit",
                    title="Habit Consistency Dip Detected",
                    description=f"7-day habit adherence ({round(adh_7)}%) dropped below your 14-day baseline ({round(adh_14)}%). Complete a micro check-in today to rebuild rhythm.",
                    impact="High",
                )
            )

    # 3. Goal Progress Trajectory Insight
    goals = db.query(Goal).all()
    active_goals = [g for g in goals if g.status != "Completed"]
    if active_goals:
        stalled_goals = []
        for g in active_goals:
            c_date = g.created_at.date() if g.created_at else today
            days_elapsed = (today - c_date).days
            if (g.progress or 0) < 10.0 and days_elapsed >= 7:
                stalled_goals.append(g.title)

        if stalled_goals and not any("structure" in title for title in active_rec_titles):
            insights.append(
                ProductivityInsight(
                    id="ins-goal-stalled-velocity",
                    type="warning",
                    category="Goal",
                    title="Goal Progress Below Expected Trajectory",
                    description=f"{len(stalled_goals)} milestone(s) ('{stalled_goals[0]}') have made < 10% progress over 7+ days. Break them into smaller 30-minute daily subtasks.",
                    impact="High",
                )
            )

    # 4. Postponement Pattern Insight
    postpone_events = db.query(ActivityLog).filter(ActivityLog.event_type == "TASK_POSTPONED").all()
    if len(postpone_events) >= 2:
        postpone_map: Dict[str, int] = {}
        for evt in postpone_events:
            if evt.entity_id:
                postpone_map[evt.entity_id] = postpone_map.get(evt.entity_id, 0) + 1

        multi_postponed = sum(1 for c in postpone_map.values() if c >= 2)
        if multi_postponed > 0 and not any("immediate focus" in title for title in active_rec_titles):
            insights.append(
                ProductivityInsight(
                    id="ins-postpone-repeated-cycle",
                    type="warning",
                    category="Postponement",
                    title="Repeated Postponement Cycle",
                    description=f"{multi_postponed} deliverable(s) have been rescheduled 2 or more times. Consider decomposing them into bite-sized 25-minute milestones.",
                    impact="High",
                )
            )

    # 5. Planning & Duration Estimation Insight
    blocks = db.query(DailyTimeblock).filter(
        DailyTimeblock.duration_minutes.isnot(None),
        DailyTimeblock.actual_duration_minutes.isnot(None),
    ).all()
    if len(blocks) >= 2:
        under = [b for b in blocks if b.actual_duration_minutes > b.duration_minutes]
        if len(under) >= len(blocks) / 2:
            avg_over = round(sum(b.actual_duration_minutes - b.duration_minutes for b in under) / len(under))
            insights.append(
                ProductivityInsight(
                    id="ins-estimation-bias-detected",
                    type="warning",
                    category="Estimation",
                    title="Underestimation Pattern Detected",
                    description=f"You consistently underestimate task durations by an average of +{avg_over} minutes. Add buffer margins to daily blocks.",
                    impact="High",
                )
            )

    has_data = len(insights) > 0 or total_tasks >= 3
    sufficiency_msg = None if has_data else "Not enough activity data to identify your productivity pattern yet."

    return InsightsResponse(
        insights=insights,
        total_insights=len(insights),
        has_sufficient_data=has_data,
        data_sufficiency_message=sufficiency_msg,
    )
