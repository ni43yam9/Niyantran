import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from backend.app.models.task import Task
from backend.app.models.goal import Goal
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.models.activity_log import ActivityLog
from backend.app.schemas.adaptive import (
    WorkingPeriodsPattern,
    TaskTendenciesPattern,
    PostponementPattern,
    EstimationBiasPattern,
    HabitConsistencyPattern,
    GoalProgressPattern,
    WorkloadTolerancePattern,
)
from backend.app.services.adaptive.confidence_manager import (
    MIN_EVENTS_TIME_OF_DAY,
    MIN_EVENTS_DAY_OF_WEEK,
    MIN_BLOCKS_ESTIMATION_BIAS,
    get_time_window_bucket,
    calculate_sample_confidence,
    compute_recency_weights,
)

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def learn_working_periods(
    timeblocks: List[DailyTimeblock],
    activity_logs: List[ActivityLog],
    tasks: List[Task],
    now_utc: Optional[datetime] = None,
) -> WorkingPeriodsPattern:
    """
    Identifies preferred working periods and peak productivity days
    based on actual execution history, strictly enforcing minimum-data guards.
    """
    now = now_utc or datetime.now(timezone.utc)
    time_window_counts: Counter = Counter()
    day_of_week_counts: Counter = Counter()
    durations: List[int] = []
    event_timestamps: List[datetime] = []

    # 1. Inspect completed timeblocks
    for tb in timeblocks:
        if tb.status == "Completed":
            window = get_time_window_bucket(tb.time)
            time_window_counts[window] += 1
            if tb.block_date:
                day_name = DAY_NAMES[tb.block_date.weekday()]
                day_of_week_counts[day_name] += 1
            if tb.actual_duration_minutes and tb.actual_duration_minutes > 0:
                durations.append(tb.actual_duration_minutes)
            elif tb.duration_minutes and tb.duration_minutes > 0:
                durations.append(tb.duration_minutes)
            if tb.updated_at:
                event_timestamps.append(tb.updated_at)

    # 2. Inspect task completions from activity logs and tasks
    for act in activity_logs:
        if act.event_type in ("TASK_COMPLETED", "TIMEBLOCK_COMPLETED"):
            if act.timestamp:
                window = get_time_window_bucket(act.timestamp)
                time_window_counts[window] += 1
                day_name = DAY_NAMES[act.timestamp.weekday()]
                day_of_week_counts[day_name] += 1
                event_timestamps.append(act.timestamp)

    for t in tasks:
        if t.status == "Completed" and t.completed_at:
            window = get_time_window_bucket(t.completed_at)
            time_window_counts[window] += 1
            day_name = DAY_NAMES[t.completed_at.weekday()]
            day_of_week_counts[day_name] += 1
            event_timestamps.append(t.completed_at)

    total_time_events = sum(time_window_counts.values())
    total_day_events = sum(day_of_week_counts.values())

    evidence: List[str] = []
    evidence.append(f"Analyzed {total_time_events} completed activity events across time windows.")

    # Apply recency weights if sufficient events
    if len(event_timestamps) >= MIN_EVENTS_TIME_OF_DAY:
        weights = compute_recency_weights(event_timestamps, half_life_days=14.0, reference_time=now)
        avg_recency = round(sum(weights) / len(weights), 2)
        evidence.append(f"Recency weighting active (average recency score: {avg_recency}).")

    # Evaluate minimum-data requirement for time-of-day
    if total_time_events < MIN_EVENTS_TIME_OF_DAY:
        confidence = calculate_sample_confidence(total_time_events, MIN_EVENTS_TIME_OF_DAY)
        evidence.append(
            f"Insufficient data for working periods: {total_time_events}/{MIN_EVENTS_TIME_OF_DAY} required events."
        )
        return WorkingPeriodsPattern(
            peak_time_window="INSUFFICIENT_DATA",
            peak_days=[],
            time_window_distribution=dict(time_window_counts),
            day_of_week_distribution=dict(day_of_week_counts),
            preferred_session_duration_minutes=60,
            confidence=confidence,
            sample_size=total_time_events,
            has_sufficient_data=False,
            evidence=evidence,
        )

    # Determine peak window
    peak_window, peak_count = time_window_counts.most_common(1)[0]
    window_consistency = peak_count / total_time_events
    confidence = calculate_sample_confidence(total_time_events, 15, consistency_ratio=window_consistency)
    evidence.append(
        f"Peak productivity window identified: {peak_window} ({peak_count}/{total_time_events} events, {round(window_consistency*100, 1)}%)."
    )

    # Determine peak days
    peak_days: List[str] = []
    if total_day_events >= MIN_EVENTS_DAY_OF_WEEK:
        # Find top 2 days
        top_days = day_of_week_counts.most_common(2)
        peak_days = [d[0] for d in top_days if d[1] >= 2]
        if peak_days:
            evidence.append(f"Peak execution days: {', '.join(peak_days)}.")

    pref_duration = int(sum(durations) / len(durations)) if durations else 60
    pref_duration = max(25, min(120, pref_duration))

    return WorkingPeriodsPattern(
        peak_time_window=peak_window,
        peak_days=peak_days,
        time_window_distribution=dict(time_window_counts),
        day_of_week_distribution=dict(day_of_week_counts),
        preferred_session_duration_minutes=pref_duration,
        confidence=confidence,
        sample_size=total_time_events,
        has_sufficient_data=True,
        evidence=evidence,
    )

def learn_task_tendencies(
    tasks: List[Task],
    activity_logs: List[ActivityLog],
) -> TaskTendenciesPattern:
    """
    Analyzes task completion tendencies and category execution success rates.
    """
    total_created = len(tasks)
    completed_tasks = [t for t in tasks if t.status == "Completed"]
    total_completed = len(completed_tasks)

    completion_rate = round((total_completed / max(1, total_created)) * 100.0, 1) if total_created > 0 else 0.0

    # Category breakdown
    cat_created: Counter = Counter()
    cat_completed: Counter = Counter()

    for t in tasks:
        cat = t.category or "General"
        cat_created[cat] += 1
        if t.status == "Completed":
            cat_completed[cat] += 1

    category_completion_rates: Dict[str, float] = {}
    for cat, count in cat_created.items():
        comp = cat_completed[cat]
        category_completion_rates[cat] = round((comp / count) * 100.0, 1)

    most_completed_category = cat_completed.most_common(1)[0][0] if cat_completed else None

    # Calculate average daily completed tasks across active completion dates
    completion_dates = set()
    for t in completed_tasks:
        if t.completed_at:
            completion_dates.add(t.completed_at.date())

    active_days = max(1, len(completion_dates))
    avg_daily_completed = round(total_completed / active_days, 2)

    has_data = total_created >= 3
    confidence = calculate_sample_confidence(total_completed, 10) if has_data else 0.10

    evidence: List[str] = [
        f"Total deliverables tracked: {total_created} created, {total_completed} completed ({completion_rate}%).",
    ]
    if most_completed_category:
        comp_count = cat_completed[most_completed_category]
        evidence.append(f"Primary category focus: '{most_completed_category}' ({comp_count} completions).")
    if not has_data:
        evidence.append("Insufficient deliverable history to establish stable completion tendency.")

    return TaskTendenciesPattern(
        total_created=total_created,
        total_completed=total_completed,
        completion_rate=completion_rate,
        avg_daily_completed_tasks=avg_daily_completed,
        most_completed_category=most_completed_category,
        category_completion_rates=category_completion_rates,
        confidence=confidence,
        sample_size=total_created,
        has_sufficient_data=has_data,
        evidence=evidence,
    )

def learn_postponements(
    tasks: List[Task],
    activity_logs: List[ActivityLog],
) -> PostponementPattern:
    """
    Monitors postponement frequencies, repeated procrastination triggers,
    and assigns qualitative procrastination levels.
    """
    postpone_events = [a for a in activity_logs if a.event_type == "TASK_POSTPONED"]
    total_postponements = len(postpone_events)

    task_map = {t.id: t for t in tasks}
    task_postpone_counts: Counter = Counter()
    cat_postpone_counts: Counter = Counter()

    for p in postpone_events:
        if p.entity_id:
            task_postpone_counts[p.entity_id] += 1
            task = task_map.get(p.entity_id)
            if task and task.category:
                cat_postpone_counts[task.category] += 1

    postponed_task_count = len(task_postpone_counts)
    repeatedly_postponed_count = sum(1 for c in task_postpone_counts.values() if c >= 2)
    most_postponed_category = cat_postpone_counts.most_common(1)[0][0] if cat_postpone_counts else None

    total_tasks = len(tasks)
    postponement_rate = round((postponed_task_count / max(1, total_tasks)) * 100.0, 1) if total_tasks > 0 else 0.0

    has_data = total_tasks >= 3 or total_postponements >= 2
    if not has_data:
        procrastination_level = "Insufficient Data"
        confidence = 0.10
    elif postponement_rate >= 40.0 or repeatedly_postponed_count >= 3:
        procrastination_level = "High"
        confidence = calculate_sample_confidence(total_postponements, 5)
    elif postponement_rate >= 15.0 or repeatedly_postponed_count >= 1:
        procrastination_level = "Moderate"
        confidence = calculate_sample_confidence(total_postponements, 5)
    else:
        procrastination_level = "Low"
        confidence = calculate_sample_confidence(total_tasks, 5)

    evidence: List[str] = [
        f"Postponement volume: {total_postponements} total postponements across {postponed_task_count} tasks ({postponement_rate}% of tasks).",
        f"Repeatedly postponed deliverables (2+ times): {repeatedly_postponed_count}.",
    ]
    if most_postponed_category:
        evidence.append(f"Primary postponement category: '{most_postponed_category}' ({cat_postpone_counts[most_postponed_category]} events).")
    if not has_data:
        evidence.append("Insufficient task lifecycle history to classify procrastination tendencies.")

    return PostponementPattern(
        total_postponements=total_postponements,
        postponed_task_count=postponed_task_count,
        postponement_rate=postponement_rate,
        most_postponed_category=most_postponed_category,
        repeatedly_postponed_count=repeatedly_postponed_count,
        procrastination_level=procrastination_level,
        confidence=confidence,
        sample_size=total_postponements,
        has_sufficient_data=has_data,
        evidence=evidence,
    )

def learn_estimation_bias(
    timeblocks: List[DailyTimeblock],
) -> EstimationBiasPattern:
    """
    Computes empirical time estimation accuracy and per-category bias factors.
    """
    actual_vs_planned: List[float] = []
    cat_ratios: Dict[str, List[float]] = {}

    for tb in timeblocks:
        if (
            tb.status == "Completed"
            and tb.duration_minutes
            and tb.duration_minutes > 0
            and tb.actual_duration_minutes
            and tb.actual_duration_minutes > 0
        ):
            ratio = float(tb.actual_duration_minutes) / float(tb.duration_minutes)
            actual_vs_planned.append(ratio)
            cat = tb.category or "General"
            cat_ratios.setdefault(cat, []).append(ratio)

    sample_size = len(actual_vs_planned)
    evidence: List[str] = []

    if sample_size < MIN_BLOCKS_ESTIMATION_BIAS:
        evidence.append(
            f"Insufficient completed timeblocks ({sample_size}/{MIN_BLOCKS_ESTIMATION_BIAS}). Using heuristic 1.25x baseline."
        )
        return EstimationBiasPattern(
            duration_bias_factor=1.25,
            is_empirical=False,
            variance=0.0,
            category_biases={},
            confidence=0.20,
            sample_size=sample_size,
            has_sufficient_data=False,
            evidence=evidence,
        )

    mean_bias = round(sum(actual_vs_planned) / sample_size, 2)
    # Variance
    variance = round(sum((r - mean_bias) ** 2 for r in actual_vs_planned) / sample_size, 3)

    category_biases: Dict[str, float] = {}
    for cat, ratios in cat_ratios.items():
        if len(ratios) >= 1:
            category_biases[cat] = round(sum(ratios) / len(ratios), 2)

    confidence = calculate_sample_confidence(sample_size, 8)
    evidence.append(f"Empirical duration bias factor: {mean_bias}x across {sample_size} completed focus blocks (variance: {variance}).")
    if mean_bias > 1.15:
        evidence.append(f"Consistent underestimation observed: Tasks take {round((mean_bias - 1.0)*100)}% longer than planned.")
    elif mean_bias < 0.90:
        evidence.append(f"Conservative estimation observed: Tasks complete {round((1.0 - mean_bias)*100)}% faster than budgeted.")
    else:
        evidence.append("Highly calibrated effort estimates: Actual duration closely matches planned duration.")

    return EstimationBiasPattern(
        duration_bias_factor=mean_bias,
        is_empirical=True,
        variance=variance,
        category_biases=category_biases,
        confidence=confidence,
        sample_size=sample_size,
        has_sufficient_data=True,
        evidence=evidence,
    )

def learn_habit_consistency(
    habits: List[Habit],
    habit_logs: List[HabitLog],
    now_utc: Optional[datetime] = None,
) -> HabitConsistencyPattern:
    """
    Evaluates habit adherence across trailing windows, identifying stability and streaks.
    """
    now = now_utc or datetime.now(timezone.utc)
    today = now.date() if isinstance(now, datetime) else date.today()
    total_habits = len(habits)

    if total_habits == 0:
        return HabitConsistencyPattern(
            average_adherence_rate=0.0,
            active_streaks_count=0,
            strongest_habit=None,
            habit_stability="Insufficient Data",
            confidence=0.0,
            sample_size=0,
            has_sufficient_data=False,
            evidence=["No active habits configured."],
        )

    # 14-day window logs
    start_14d = today - timedelta(days=14)
    logs_14d = [l for l in habit_logs if l.log_date and l.log_date >= start_14d and l.completed]
    total_possible_14d = total_habits * 14

    adherence_14d = round((len(logs_14d) / max(1, total_possible_14d)) * 100.0, 1)

    # Check streaks
    active_streaks = 0
    strongest_habit_title: Optional[str] = None
    max_streak = 0

    for h in habits:
        streak = getattr(h, "streak_count", 0) or 0
        if streak > 0:
            active_streaks += 1
        if streak > max_streak:
            max_streak = streak
            strongest_habit_title = h.title

    has_data = len(habit_logs) >= 3
    if not has_data:
        habit_stability = "Insufficient Data"
        confidence = 0.15
    elif adherence_14d >= 75.0 or max_streak >= 7:
        habit_stability = "High"
        confidence = calculate_sample_confidence(len(habit_logs), 10)
    elif adherence_14d >= 40.0 or active_streaks >= 1:
        habit_stability = "Moderate"
        confidence = calculate_sample_confidence(len(habit_logs), 10)
    else:
        habit_stability = "Fragile"
        confidence = calculate_sample_confidence(len(habit_logs), 10)

    evidence: List[str] = [
        f"Habit fleet: {total_habits} active habits with {adherence_14d}% average 14-day adherence.",
        f"Active unbroken streaks: {active_streaks}/{total_habits}.",
    ]
    if strongest_habit_title and max_streak > 0:
        evidence.append(f"Leading habit: '{strongest_habit_title}' with {max_streak}-day streak.")
    if not has_data:
        evidence.append("Insufficient habit check-in history to establish consistency baseline.")

    return HabitConsistencyPattern(
        average_adherence_rate=adherence_14d,
        active_streaks_count=active_streaks,
        strongest_habit=strongest_habit_title,
        habit_stability=habit_stability,
        confidence=confidence,
        sample_size=len(habit_logs),
        has_sufficient_data=has_data,
        evidence=evidence,
    )

def learn_goal_progress(
    goals: List[Goal],
    tasks: List[Task],
) -> GoalProgressPattern:
    """
    Models goal achievement velocity and flags stalled milestones.
    """
    total_goals = len(goals)
    if total_goals == 0:
        return GoalProgressPattern(
            active_goals_count=0,
            avg_velocity_percent_per_day=0.0,
            stalled_goals_count=0,
            on_track_goals_count=0,
            confidence=0.0,
            sample_size=0,
            has_sufficient_data=False,
            evidence=["No goals tracked in system."],
        )

    active_goals = [g for g in goals if g.status != "Completed"]
    velocities: List[float] = []
    stalled_count = 0
    on_track_count = 0

    today = date.today()
    for g in active_goals:
        progress = g.progress or 0.0
        created_dt = g.created_at.date() if g.created_at else today
        days_elapsed = max(1, (today - created_dt).days)
        velocity = progress / days_elapsed
        velocities.append(velocity)

        if progress < 10.0 and days_elapsed >= 7:
            stalled_count += 1
        elif progress >= 50.0 or velocity >= 2.0:
            on_track_count += 1

    avg_velocity = round(sum(velocities) / max(1, len(velocities)), 2)
    has_data = total_goals >= 2
    confidence = calculate_sample_confidence(total_goals, 5) if has_data else 0.20

    evidence: List[str] = [
        f"Goal milestone status: {len(active_goals)} active, {total_goals - len(active_goals)} completed.",
        f"Average progress velocity: {avg_velocity}% per day across active goals.",
    ]
    if stalled_count > 0:
        evidence.append(f"Identified {stalled_count} stalled milestone(s) requiring intervention.")
    if on_track_count > 0:
        evidence.append(f"Identified {on_track_count} milestone(s) actively progressing on track.")

    return GoalProgressPattern(
        active_goals_count=len(active_goals),
        avg_velocity_percent_per_day=avg_velocity,
        stalled_goals_count=stalled_count,
        on_track_goals_count=on_track_count,
        confidence=confidence,
        sample_size=total_goals,
        has_sufficient_data=has_data,
        evidence=evidence,
    )

def learn_workload_tolerance(
    timeblocks: List[DailyTimeblock],
    tasks: List[Task],
    activity_logs: List[ActivityLog],
) -> WorkloadTolerancePattern:
    """
    Analyzes historical load vs execution success to determine comfortable daily capacity.
    """
    day_load: Dict[date, int] = {}
    day_completed_load: Dict[date, int] = {}

    for tb in timeblocks:
        d = tb.block_date
        dur = tb.duration_minutes or 60
        day_load[d] = day_load.get(d, 0) + dur
        if tb.status == "Completed":
            actual_dur = tb.actual_duration_minutes or dur
            day_completed_load[d] = day_completed_load.get(d, 0) + actual_dur

    days_observed = len(day_load)
    evidence: List[str] = []

    if days_observed < 3:
        evidence.append("Insufficient daily schedule history. Using default 300m (5.0h) optimal workload capacity.")
        return WorkloadTolerancePattern(
            optimal_daily_load_minutes=300,
            max_observed_sustainable_minutes=360,
            heavy_day_completion_rate=0.0,
            confidence=0.20,
            has_sufficient_data=False,
            evidence=evidence,
        )

    # Find highest load day with at least 80% completion
    high_sustainable = 300
    heavy_days_count = 0
    heavy_days_success = 0

    for d, planned in day_load.items():
        done = day_completed_load.get(d, 0)
        ratio = done / max(1, planned)
        if planned >= 300:
            heavy_days_count += 1
            if ratio >= 0.75:
                heavy_days_success += 1
                if planned > high_sustainable:
                    high_sustainable = planned

    heavy_completion_rate = round((heavy_days_success / max(1, heavy_days_count)) * 100.0, 1) if heavy_days_count > 0 else 0.0

    optimal_load = min(360, max(240, high_sustainable if heavy_completion_rate >= 60.0 else 270))
    max_sustainable = max(optimal_load + 60, high_sustainable)

    confidence = calculate_sample_confidence(days_observed, 7)
    evidence.append(
        f"Workload tolerance calibrated over {days_observed} scheduled days: {optimal_load}m optimal capacity ({round(optimal_load/60, 1)}h)."
    )
    evidence.append(f"Heavy-day execution reliability (>= 300m): {heavy_completion_rate}% ({heavy_days_success}/{heavy_days_count} days).")

    return WorkloadTolerancePattern(
        optimal_daily_load_minutes=optimal_load,
        max_observed_sustainable_minutes=max_sustainable,
        heavy_day_completion_rate=heavy_completion_rate,
        confidence=confidence,
        has_sufficient_data=True,
        evidence=evidence,
    )
