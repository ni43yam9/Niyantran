import uuid
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from backend.app.models.activity_log import ActivityLog
from backend.app.models.task import Task
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.schemas.behaviour import (
    ActivityLogResponse,
    TaskCompletionAnalysis,
    PostponementAnalysis,
    RepeatedlyPostponedTask,
    TimeEstimationAnalysis,
    CategoryEstimationAccuracy,
    ProductivityHoursAnalysis,
    HabitConsistencyAnalysis,
    HabitSummary,
    DailyPlanningAnalysis,
    BehaviourSummaryResponse,
)

# ---------------------------------------------------------------------------
# Activity Logging Engine
# ---------------------------------------------------------------------------

def record_activity(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    original_date: Optional[date] = None,
    new_date: Optional[date] = None,
    duration_minutes: Optional[int] = None,
    actual_duration_minutes: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    deduplicate_window_seconds: int = 5,
) -> ActivityLog:
    """
    Records an activity event with duplicate prevention.
    If an identical event for the same entity was recorded within the deduplicate window,
    the existing record is returned without inserting a duplicate.
    """
    event_time = timestamp or datetime.now(timezone.utc)

    # 1. Duplicate check within short sliding window
    if entity_id:
        window_start = event_time - timedelta(seconds=deduplicate_window_seconds)
        dup_query = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.event_type == event_type,
                ActivityLog.entity_type == entity_type,
                ActivityLog.entity_id == entity_id,
                ActivityLog.timestamp >= window_start,
            )
        )
        if new_date:
            dup_query = dup_query.filter(ActivityLog.new_date == new_date)
        existing = dup_query.first()
        if existing:
            return existing

    # 2. Duplicate check for daily habit completion (prevent multiple completions for same day)
    if event_type == "HABIT_COMPLETED" and entity_id and new_date:
        existing_habit_log = (
            db.query(ActivityLog)
            .filter(
                ActivityLog.event_type == "HABIT_COMPLETED",
                ActivityLog.entity_type == "habit",
                ActivityLog.entity_id == entity_id,
                ActivityLog.new_date == new_date,
            )
            .first()
        )
        if existing_habit_log:
            return existing_habit_log

    act_id = f"act_{int(event_time.timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
    activity = ActivityLog(
        id=act_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=event_time,
        original_date=original_date,
        new_date=new_date,
        duration_minutes=duration_minutes,
        actual_duration_minutes=actual_duration_minutes,
        details=details or {},
        created_at=event_time,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity

def get_activities(
    db: Session,
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> List[ActivityLogResponse]:
    query = db.query(ActivityLog)
    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)
    if entity_type:
        query = query.filter(ActivityLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(ActivityLog.entity_id == entity_id)

    records = query.order_by(ActivityLog.timestamp.desc()).offset(skip).limit(limit).all()
    return [ActivityLogResponse.model_validate(r) for r in records]

# ---------------------------------------------------------------------------
# Module A: Task Completion Monitoring
# ---------------------------------------------------------------------------

def get_task_completion_analysis(db: Session, tz_offset_mins: int = 0) -> TaskCompletionAnalysis:
    tasks = db.query(Task).all()
    total_created = len(tasks)
    if total_created == 0:
        return TaskCompletionAnalysis(
            has_sufficient_data=False,
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    completed_tasks = [t for t in tasks if t.status == "Completed"]
    pending_tasks = [t for t in tasks if t.status != "Completed"]
    total_completed = len(completed_tasks)
    total_pending = len(pending_tasks)
    completion_rate = round((total_completed / total_created) * 100, 1)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Daily completion rate
    today_completed = sum(1 for t in completed_tasks if t.completed_at and t.completed_at.date() == today)
    today_due = sum(1 for t in tasks if t.due_date == today or (t.completed_at and t.completed_at.date() == today))
    daily_rate = round((today_completed / today_due) * 100, 1) if today_due > 0 else (100.0 if today_completed > 0 else 0.0)

    # Weekly completion rate
    week_completed = sum(1 for t in completed_tasks if t.completed_at and t.completed_at.date() >= week_start)
    week_due = sum(1 for t in tasks if (t.due_date and t.due_date >= week_start) or (t.completed_at and t.completed_at.date() >= week_start))
    weekly_rate = round((week_completed / week_due) * 100, 1) if week_due > 0 else (100.0 if week_completed > 0 else 0.0)

    # Average task completion resolution time
    resolution_hours: List[float] = []
    for t in completed_tasks:
        if t.completed_at and t.created_at and t.completed_at >= t.created_at:
            delta = (t.completed_at - t.created_at).total_seconds() / 3600.0
            resolution_hours.append(delta)
    avg_resolution = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None

    # Completions by day of week
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = {name: 0 for name in day_names}
    for t in completed_tasks:
        if t.completed_at:
            local_time = t.completed_at + timedelta(minutes=tz_offset_mins)
            day_name = day_names[local_time.weekday()]
            day_counts[day_name] += 1

    most_prod_day = max(day_counts.items(), key=lambda x: x[1])[0] if total_completed >= 2 else None

    has_data = total_completed >= 2
    return TaskCompletionAnalysis(
        total_created=total_created,
        total_completed=total_completed,
        total_pending=total_pending,
        completion_rate=completion_rate,
        daily_completion_percentage=daily_rate,
        weekly_completion_percentage=weekly_rate,
        average_completion_time_hours=avg_resolution,
        completions_by_day_of_week=day_counts,
        most_productive_day=most_prod_day,
        has_sufficient_data=has_data,
        message=None if has_data else "Not enough activity data to identify your productivity pattern yet.",
    )

# ---------------------------------------------------------------------------
# Module B: Procrastination & Postponement Monitoring
# ---------------------------------------------------------------------------

def get_postponement_analysis(db: Session) -> PostponementAnalysis:
    postpone_events = (
        db.query(ActivityLog)
        .filter(ActivityLog.event_type == "TASK_POSTPONED")
        .all()
    )
    total_postponements = len(postpone_events)

    # Group postponements by task_id
    task_postpone_map: Dict[str, List[ActivityLog]] = {}
    for evt in postpone_events:
        if evt.entity_id:
            task_postpone_map.setdefault(evt.entity_id, []).append(evt)

    repeated_tasks: List[RepeatedlyPostponedTask] = []
    for task_id, evts in task_postpone_map.items():
        if len(evts) >= 2:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                orig_date = evts[0].original_date or (evts[0].details or {}).get("old_due_date")
                curr_date = task.due_date
                repeated_tasks.append(
                    RepeatedlyPostponedTask(
                        task_id=task.id,
                        title=task.title,
                        category=task.category or "General",
                        postpone_count=len(evts),
                        original_date=orig_date,
                        current_date=curr_date,
                        status=task.status,
                    )
                )

    # Check tasks completed past their deadline
    completed_tasks = db.query(Task).filter(Task.status == "Completed").all()
    completed_after_deadline = 0
    for t in completed_tasks:
        if t.due_date and t.completed_at and t.completed_at.date() > t.due_date:
            completed_after_deadline += 1

    overdue_rate = (
        round((completed_after_deadline / len(completed_tasks)) * 100, 1)
        if completed_tasks
        else 0.0
    )

    total_tasks = db.query(func.count(Task.id)).scalar() or 0
    if total_tasks < 3 and total_postponements == 0:
        return PostponementAnalysis(
            total_postponements=0,
            postponed_task_count=0,
            repeatedly_postponed_tasks=[],
            completed_after_deadline_count=0,
            overdue_completion_rate=0.0,
            procrastination_level="Insufficient Data",
            has_sufficient_data=False,
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    # Determine qualitative procrastination level
    if len(repeated_tasks) == 0 and overdue_rate <= 15.0:
        procrastination_level = "Low"
    elif len(repeated_tasks) <= 2 and overdue_rate <= 40.0:
        procrastination_level = "Moderate"
    else:
        procrastination_level = "High"

    return PostponementAnalysis(
        total_postponements=total_postponements,
        postponed_task_count=len(task_postpone_map),
        repeatedly_postponed_tasks=repeated_tasks,
        completed_after_deadline_count=completed_after_deadline,
        overdue_completion_rate=overdue_rate,
        procrastination_level=procrastination_level,
        has_sufficient_data=True,
        message=None,
    )

# ---------------------------------------------------------------------------
# Module C: Time Estimation Monitoring
# ---------------------------------------------------------------------------

def get_time_estimation_analysis(db: Session) -> TimeEstimationAnalysis:
    # Query timeblocks that have both planned duration and recorded actual duration
    blocks = (
        db.query(DailyTimeblock)
        .filter(
            DailyTimeblock.duration_minutes.isnot(None),
            DailyTimeblock.actual_duration_minutes.isnot(None),
        )
        .all()
    )

    if len(blocks) < 2:
        return TimeEstimationAnalysis(
            has_sufficient_data=False,
            estimation_bias="Insufficient Data",
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    total_planned = sum(b.duration_minutes for b in blocks)
    total_actual = sum(b.actual_duration_minutes for b in blocks)
    errors = [abs(b.actual_duration_minutes - b.duration_minutes) for b in blocks]
    avg_error = round(sum(errors) / len(errors), 1) if errors else 0.0

    underestimated = sum(1 for b in blocks if b.actual_duration_minutes > b.duration_minutes)
    overestimated = sum(1 for b in blocks if b.actual_duration_minutes < b.duration_minutes)
    accurate = sum(1 for b in blocks if b.actual_duration_minutes == b.duration_minutes)

    underestimated_pct = round((underestimated / len(blocks)) * 100, 1)

    # Determine bias
    if underestimated_pct >= 50.0 and total_actual > total_planned:
        bias = "Underestimation"
    elif (overestimated / len(blocks)) >= 50.0 and total_actual < total_planned:
        bias = "Overestimation"
    else:
        bias = "Balanced"

    # Category breakdown
    cat_map: Dict[str, Dict[str, int]] = {}
    for b in blocks:
        cat = b.category or "General"
        if cat not in cat_map:
            cat_map[cat] = {"planned": 0, "actual": 0, "count": 0}
        cat_map[cat]["planned"] += b.duration_minutes
        cat_map[cat]["actual"] += b.actual_duration_minutes
        cat_map[cat]["count"] += 1

    category_breakdown = [
        CategoryEstimationAccuracy(
            category=cat,
            planned_minutes=vals["planned"],
            actual_minutes=vals["actual"],
            variance_minutes=vals["actual"] - vals["planned"],
            count=vals["count"],
            is_underestimated=vals["actual"] > vals["planned"],
        )
        for cat, vals in cat_map.items()
    ]

    return TimeEstimationAnalysis(
        total_tracked_tasks=len(blocks),
        total_planned_minutes=total_planned,
        total_actual_minutes=total_actual,
        average_error_minutes=avg_error,
        underestimated_count=underestimated,
        overestimated_count=overestimated,
        accurate_count=accurate,
        underestimation_percentage=underestimated_pct,
        estimation_bias=bias,
        category_breakdown=category_breakdown,
        has_sufficient_data=True,
        message=None,
    )

# ---------------------------------------------------------------------------
# Module D: Productivity Time Analysis
# ---------------------------------------------------------------------------

def get_productivity_hours_analysis(db: Session, tz_offset_mins: int = 0) -> ProductivityHoursAnalysis:
    # Look at both completed task timestamps and PLANNED_TASK_FINISHED activity logs
    completion_times: List[datetime] = []

    tasks = db.query(Task.completed_at).filter(Task.status == "Completed", Task.completed_at.isnot(None)).all()
    for t in tasks:
        completion_times.append(t[0])

    logs = (
        db.query(ActivityLog.timestamp)
        .filter(ActivityLog.event_type.in_(["TASK_COMPLETED", "PLANNED_TASK_FINISHED"]))
        .all()
    )
    for l in logs:
        completion_times.append(l[0])

    if len(completion_times) < 3:
        return ProductivityHoursAnalysis(
            has_sufficient_data=False,
            peak_period="Insufficient Data",
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    hourly_dist = {h: 0 for h in range(24)}
    morning = 0    # 05:00 - 12:00
    afternoon = 0  # 12:00 - 17:00
    evening = 0    # 17:00 - 22:00
    night = 0      # 22:00 - 05:00

    for dt in completion_times:
        local_dt = dt + timedelta(minutes=tz_offset_mins)
        hour = local_dt.hour
        hourly_dist[hour] += 1

        if 5 <= hour < 12:
            morning += 1
        elif 12 <= hour < 17:
            afternoon += 1
        elif 17 <= hour < 22:
            evening += 1
        else:
            night += 1

    quadrants = {
        "Morning": morning,
        "Afternoon": afternoon,
        "Evening": evening,
        "Night": night,
    }
    peak_period = max(quadrants.items(), key=lambda x: x[1])[0]

    # Find highest density 3-hour continuous window
    best_window_count = -1
    best_start_hour = 9
    for start in range(24):
        count = sum(hourly_dist[(start + offset) % 24] for offset in range(3))
        if count > best_window_count:
            best_window_count = count
            best_start_hour = start

    end_hour = (best_start_hour + 3) % 24
    start_meridiem = "AM" if best_start_hour < 12 else "PM"
    end_meridiem = "AM" if end_hour < 12 else "PM"
    start_12 = best_start_hour % 12 or 12
    end_12 = end_hour % 12 or 12
    peak_window_str = f"{start_12:02d}:00 {start_meridiem} – {end_12:02d}:00 {end_meridiem}"

    return ProductivityHoursAnalysis(
        total_recorded_completions=len(completion_times),
        morning_completions=morning,
        afternoon_completions=afternoon,
        evening_completions=evening,
        night_completions=night,
        peak_period=peak_period,
        peak_window=peak_window_str,
        hourly_distribution=hourly_dist,
        has_sufficient_data=True,
        message=None,
    )

# ---------------------------------------------------------------------------
# Module E: Habit Consistency Monitoring
# ---------------------------------------------------------------------------

def get_habit_consistency_analysis(db: Session) -> HabitConsistencyAnalysis:
    habits = db.query(Habit).filter(Habit.archived == False).all()
    if not habits:
        return HabitConsistencyAnalysis(
            has_sufficient_data=False,
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    habit_summaries: List[HabitSummary] = []
    total_checks_30d = 0
    all_active_dates = set()

    for h in habits:
        logs = db.query(HabitLog).filter(HabitLog.habit_id == h.id, HabitLog.completed == True).all()
        log_dates = {l.log_date for l in logs}
        all_active_dates.update(log_dates)

        # 30-day checks
        checks_30d = sum(1 for d in log_dates if d >= thirty_days_ago)
        total_checks_30d += checks_30d
        rate_30d = round((checks_30d / 30.0) * 100, 1)

        # Dynamic streak calculation
        curr_streak = 0
        check_date = today
        if check_date in log_dates:
            curr_streak += 1
            check_date -= timedelta(days=1)
        else:
            check_date -= timedelta(days=1)

        while check_date in log_dates:
            curr_streak += 1
            check_date -= timedelta(days=1)

        curr_streak = max(curr_streak, h.base_streak or 0)
        longest = max(curr_streak, len(log_dates))

        habit_summaries.append(
            HabitSummary(
                habit_id=h.id,
                name=h.name,
                category=h.category or "General",
                current_streak=curr_streak,
                longest_streak=longest,
                completion_rate_30d=rate_30d,
            )
        )

    # Missed days in past 30 days
    missed_days = 0
    for day_offset in range(30):
        d = thirty_days_ago + timedelta(days=day_offset)
        if d not in all_active_dates:
            missed_days += 1

    total_possible_checks = len(habits) * 30
    overall_consistency = round((total_checks_30d / total_possible_checks) * 100, 1) if total_possible_checks > 0 else 0.0
    avg_streak = round(sum(s.current_streak for s in habit_summaries) / len(habit_summaries), 1) if habit_summaries else 0.0
    longest_rec = max((s.longest_streak for s in habit_summaries), default=0)
    most_consistent = max(habit_summaries, key=lambda s: s.completion_rate_30d).name if habit_summaries else None

    return HabitConsistencyAnalysis(
        total_active_habits=len(habits),
        overall_consistency_percentage=overall_consistency,
        average_current_streak=avg_streak,
        longest_streak_recorded=longest_rec,
        missed_days_last_30_days=missed_days,
        most_consistent_habit=most_consistent,
        habit_summaries=habit_summaries,
        has_sufficient_data=True,
        message=None,
    )

# ---------------------------------------------------------------------------
# Module F: Daily Planning Behaviour
# ---------------------------------------------------------------------------

def get_daily_planning_analysis(db: Session) -> DailyPlanningAnalysis:
    blocks = db.query(DailyTimeblock).all()
    if len(blocks) < 2:
        return DailyPlanningAnalysis(
            has_sufficient_data=False,
            capacity_discipline="Insufficient Data",
            message="Not enough activity data to identify your productivity pattern yet.",
        )

    total_planned = len(blocks)
    completed_planned = sum(1 for b in blocks if b.status == "Completed")
    accuracy_rate = round((completed_planned / total_planned) * 100, 1) if total_planned > 0 else 0.0

    # Group by date to check average daily planned hours
    date_duration_map: Dict[date, int] = {}
    for b in blocks:
        if not b.is_break:
            date_duration_map[b.block_date] = date_duration_map.get(b.block_date, 0) + (b.duration_minutes or 60)

    avg_planned_mins = (
        sum(date_duration_map.values()) / len(date_duration_map) if date_duration_map else 0
    )
    avg_planned_hours = round(avg_planned_mins / 60.0, 1)

    today = date.today()
    unfinished = sum(
        1 for b in blocks if b.block_date < today and b.status != "Completed" and not b.is_break
    )

    # Shifted events
    shifted_count = (
        db.query(func.count(ActivityLog.id))
        .filter(ActivityLog.event_type.in_(["TIMEBLOCK_SHIFTED", "TASK_POSTPONED"]))
        .scalar()
        or 0
    )

    if avg_planned_hours > 6.0:
        discipline = "Overbooked (> 6.0 hrs/day)"
    elif avg_planned_hours > 0:
        discipline = "Healthy (< 6.0 hrs/day)"
    else:
        discipline = "Insufficient Data"

    return DailyPlanningAnalysis(
        total_planned_blocks=total_planned,
        completed_planned_blocks=completed_planned,
        planning_accuracy_rate=accuracy_rate,
        average_daily_planned_hours=avg_planned_hours,
        frequently_shifted_count=shifted_count,
        unfinished_planned_tasks=unfinished,
        capacity_discipline=discipline,
        has_sufficient_data=True,
        message=None,
    )

# ---------------------------------------------------------------------------
# Overall Behaviour Summary Aggregator
# ---------------------------------------------------------------------------

def get_behaviour_summary(db: Session, tz_offset_mins: int = 0) -> BehaviourSummaryResponse:
    task_comp = get_task_completion_analysis(db, tz_offset_mins)
    postpone = get_postponement_analysis(db)
    time_est = get_time_estimation_analysis(db)
    prod_hrs = get_productivity_hours_analysis(db, tz_offset_mins)
    habit_cons = get_habit_consistency_analysis(db)
    planning = get_daily_planning_analysis(db)

    # Synthesize qualitative assessment
    assessments = []
    if task_comp.has_sufficient_data:
        assessments.append(f"{task_comp.completion_rate}% Task Completion Rate")
    if time_est.has_sufficient_data:
        assessments.append(f"{time_est.estimation_bias} Time Bias")
    if prod_hrs.has_sufficient_data:
        assessments.append(f"Peak: {prod_hrs.peak_period}")
    if habit_cons.has_sufficient_data and habit_cons.overall_consistency_percentage > 50:
        assessments.append("Consistent Ritual Execution")

    overall = " • ".join(assessments) if assessments else "Building Productivity Profile"

    return BehaviourSummaryResponse(
        task_completion=task_comp,
        procrastination=postpone,
        time_estimation=time_est,
        productivity_hours=prod_hrs,
        habit_consistency=habit_cons,
        daily_planning=planning,
        overall_assessment=overall,
        evaluated_at=datetime.now(timezone.utc),
    )
