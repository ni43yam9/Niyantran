import logging
import uuid
from datetime import date, datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.goal import Goal
from backend.app.models.task import Task
from backend.app.models.habit import Habit
from backend.app.models.habit_log import HabitLog
from backend.app.models.timeblock import DailyTimeblock
from backend.app.schemas.migration import MigrationImportResponse, MigrationStatusResponse

logger = logging.getLogger(__name__)

def parse_date(date_val: Any, default_val: date) -> date:
    if not date_val:
        return default_val
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    try:
        # Expected format YYYY-MM-DD
        return datetime.strptime(str(date_val).split("T")[0], "%Y-%m-%d").date()
    except Exception:
        return default_val

def import_records(
    db: Session,
    tasks_data: List[Dict[str, Any]],
    goals_data: List[Dict[str, Any]],
    habits_data: Optional[List[Dict[str, Any]]] = None,
    timeblocks_data: Optional[Any] = None,
    overwrite: bool = False,
) -> MigrationImportResponse:
    tasks_imported = 0
    tasks_updated = 0
    tasks_skipped = 0
    goals_imported = 0
    goals_updated = 0
    goals_skipped = 0
    habits_imported = 0
    habits_updated = 0
    habits_skipped = 0
    habit_logs_imported = 0
    timeblocks_imported = 0
    timeblocks_updated = 0
    timeblocks_skipped = 0
    errors: List[str] = []

    now = datetime.now(timezone.utc)
    today = date.today()

    try:
        # STEP 1: Process Goals First
        for g_data in (goals_data or []):
            try:
                g_id = str(g_data.get("id", "")).strip()
                if not g_id:
                    errors.append(f"Goal skipped: missing ID in payload '{g_data.get('title', 'Unknown')}'")
                    goals_skipped += 1
                    continue

                title = str(g_data.get("title", "")).strip()
                if not title:
                    errors.append(f"Goal {g_id} skipped: missing title")
                    goals_skipped += 1
                    continue

                goal_type = str(g_data.get("goal_type") or g_data.get("type") or "Short-Term").strip()
                if goal_type not in ("Short-Term", "Long-Term"):
                    goal_type = "Short-Term"

                category = str(g_data.get("category", "Coding")).strip()
                priority = str(g_data.get("priority", "Medium")).strip()
                if priority not in ("High", "Medium", "Low"):
                    priority = "Medium"

                status = str(g_data.get("status", "In Progress")).strip()
                if status not in ("In Progress", "On Track", "Behind", "Completed"):
                    status = "In Progress"

                start_date = parse_date(g_data.get("start_date") or g_data.get("startDate"), today)
                target_date = parse_date(g_data.get("target_date") or g_data.get("targetDate"), today)
                if target_date < start_date:
                    target_date = start_date

                try:
                    progress = int(g_data.get("progress", 0))
                    progress = max(0, min(100, progress))
                except (ValueError, TypeError):
                    progress = 0

                key_milestone = str(g_data.get("key_milestone") or g_data.get("keyMilestone") or "").strip()
                description = str(g_data.get("description", "")).strip()

                existing_goal = db.query(Goal).filter(Goal.id == g_id).first()
                if existing_goal:
                    if overwrite:
                        existing_goal.title = title
                        existing_goal.description = description
                        existing_goal.goal_type = goal_type
                        existing_goal.category = category
                        existing_goal.priority = priority
                        existing_goal.status = status
                        existing_goal.start_date = start_date
                        existing_goal.target_date = target_date
                        existing_goal.progress = progress
                        existing_goal.key_milestone = key_milestone
                        existing_goal.updated_at = now
                        goals_updated += 1
                    else:
                        goals_skipped += 1
                else:
                    new_goal = Goal(
                        id=g_id,
                        title=title,
                        description=description,
                        goal_type=goal_type,
                        category=category,
                        priority=priority,
                        status=status,
                        start_date=start_date,
                        target_date=target_date,
                        progress=progress,
                        key_milestone=key_milestone,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_goal)
                    goals_imported += 1

            except Exception as ge:
                logger.error(f"Error processing goal {g_data}: {ge}")
                errors.append(f"Goal error on '{g_data.get('id', 'Unknown')}': {str(ge)}")
                goals_skipped += 1

        db.flush()

        # STEP 2: Process Tasks Second
        valid_goal_ids = {g[0] for g in db.query(Goal.id).all()}

        for t_data in (tasks_data or []):
            try:
                t_id = str(t_data.get("id", "")).strip()
                if not t_id:
                    errors.append(f"Task skipped: missing ID in payload '{t_data.get('title', 'Unknown')}'")
                    tasks_skipped += 1
                    continue

                title = str(t_data.get("title", "")).strip()
                if not title:
                    errors.append(f"Task {t_id} skipped: missing title")
                    tasks_skipped += 1
                    continue

                task_type = str(t_data.get("task_type") or t_data.get("taskType") or "Daily").strip()
                if task_type not in ("Daily", "Short-Term", "Long-Term", "One-Time", "Occasional"):
                    task_type = "Daily"

                category = str(t_data.get("category", "Coding")).strip()
                if category not in ("Academic", "Coding", "Career", "Reading", "Health", "Personal"):
                    category = "Coding"

                priority = str(t_data.get("priority", "Medium")).strip()
                if priority not in ("High", "Medium", "Low"):
                    priority = "Medium"

                status = str(t_data.get("status", "Pending")).strip()
                if status not in ("Pending", "In Progress", "Completed"):
                    status = "Pending"

                start_date = parse_date(t_data.get("start_date") or t_data.get("startDate"), today)
                due_date = parse_date(t_data.get("due_date") or t_data.get("dueDate"), today)
                if due_date < start_date:
                    due_date = start_date

                goal_id = t_data.get("goal_id") or t_data.get("associatedGoalId")
                if goal_id and str(goal_id).strip() in valid_goal_ids:
                    goal_id = str(goal_id).strip()
                else:
                    goal_id = None

                completed_at = None
                if status == "Completed":
                    completed_at = now

                description = str(t_data.get("description", "")).strip()

                existing_task = db.query(Task).filter(Task.id == t_id).first()
                if existing_task:
                    if overwrite:
                        existing_task.title = title
                        existing_task.description = description
                        existing_task.task_type = task_type
                        existing_task.category = category
                        existing_task.priority = priority
                        existing_task.status = status
                        existing_task.start_date = start_date
                        existing_task.due_date = due_date
                        existing_task.goal_id = goal_id
                        if status == "Completed" and not existing_task.completed_at:
                            existing_task.completed_at = completed_at
                        elif status != "Completed":
                            existing_task.completed_at = None
                        existing_task.updated_at = now
                        tasks_updated += 1
                    else:
                        tasks_skipped += 1
                else:
                    new_task = Task(
                        id=t_id,
                        title=title,
                        description=description,
                        task_type=task_type,
                        category=category,
                        priority=priority,
                        status=status,
                        start_date=start_date,
                        due_date=due_date,
                        goal_id=goal_id,
                        completed_at=completed_at,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_task)
                    tasks_imported += 1

            except Exception as te:
                logger.error(f"Error processing task {t_data}: {te}")
                errors.append(f"Task error on '{t_data.get('id', 'Unknown')}': {str(te)}")
                tasks_skipped += 1

        db.flush()

        # STEP 3: Process Habits and Habit Logs
        if habits_data:
            for h_data in habits_data:
                try:
                    h_id = str(h_data.get("id", "")).strip()
                    if not h_id:
                        h_id = f"h-{uuid.uuid4().hex[:8]}"

                    name = str(h_data.get("name", "")).strip()
                    if not name:
                        habits_skipped += 1
                        continue

                    target = str(h_data.get("target", "")).strip() or None
                    category = str(h_data.get("category", "General")).strip()
                    frequency = str(h_data.get("frequency", "Daily")).strip()
                    base_streak = int(h_data.get("baseStreak") or h_data.get("streak") or 0)

                    existing_habit = db.query(Habit).filter(Habit.id == h_id).first()
                    if existing_habit:
                        if overwrite:
                            existing_habit.name = name
                            existing_habit.target = target
                            existing_habit.category = category
                            existing_habit.frequency = frequency
                            existing_habit.base_streak = base_streak
                            existing_habit.updated_at = now
                            habits_updated += 1
                        else:
                            habits_skipped += 1
                    else:
                        new_habit = Habit(
                            id=h_id,
                            name=name,
                            target=target,
                            category=category,
                            frequency=frequency,
                            base_streak=base_streak,
                            archived=False,
                            created_at=now,
                            updated_at=now,
                        )
                        db.add(new_habit)
                        habits_imported += 1

                    # Process completedDates dictionary if present
                    completed_dates = h_data.get("completedDates") or {}
                    if isinstance(completed_dates, dict):
                        for date_str, is_done in completed_dates.items():
                            if is_done:
                                try:
                                    d = date.fromisoformat(str(date_str).strip())
                                    existing_log = db.query(HabitLog).filter(
                                        HabitLog.habit_id == h_id,
                                        HabitLog.log_date == d,
                                    ).first()
                                    if not existing_log:
                                        log_obj = HabitLog(
                                            id=f"hl-{uuid.uuid4().hex[:12]}",
                                            habit_id=h_id,
                                            log_date=d,
                                            completed=True,
                                            created_at=now,
                                        )
                                        db.add(log_obj)
                                        habit_logs_imported += 1
                                except ValueError:
                                    continue
                except Exception as he:
                    logger.error(f"Error processing habit {h_data}: {he}")
                    errors.append(f"Habit error: {str(he)}")
                    habits_skipped += 1

        db.flush()

        # STEP 4: Process Daily Timeblocks
        if timeblocks_data:
            # Flatten timeblocks whether provided as dict { [date]: [blocks] } or list of blocks
            blocks_to_process = []
            if isinstance(timeblocks_data, dict):
                for date_key, b_list in timeblocks_data.items():
                    if isinstance(b_list, list):
                        for b in b_list:
                            if isinstance(b, dict):
                                b_copy = dict(b)
                                if "block_date" not in b_copy and "date" not in b_copy:
                                    b_copy["block_date"] = date_key
                                blocks_to_process.append(b_copy)
            elif isinstance(timeblocks_data, list):
                blocks_to_process = timeblocks_data

            valid_task_ids = {t[0] for t in db.query(Task.id).all()}

            for b_data in blocks_to_process:
                try:
                    b_id = str(b_data.get("id", "")).strip()
                    if not b_id:
                        b_id = f"blk_{uuid.uuid4().hex[:12]}"

                    title = str(b_data.get("title", "")).strip()
                    if not title:
                        timeblocks_skipped += 1
                        continue

                    raw_date = b_data.get("block_date") or b_data.get("date")
                    block_date = parse_date(raw_date, today)
                    time_str = str(b_data.get("time", "09:00 AM")).strip()
                    duration_minutes = int(b_data.get("durationMinutes") or b_data.get("duration_minutes") or 60)
                    actual_duration_minutes = b_data.get("actualDurationMinutes") or b_data.get("actual_duration_minutes")
                    if actual_duration_minutes is not None:
                        actual_duration_minutes = int(actual_duration_minutes)

                    category = str(b_data.get("category", "General")).strip()
                    status = str(b_data.get("status", "Pending")).strip()
                    if status not in ("Pending", "In Progress", "Completed"):
                        status = "Pending"

                    is_break = bool(b_data.get("isBreak") or b_data.get("is_break") or False)
                    task_id = b_data.get("taskId") or b_data.get("task_id")
                    if task_id and str(task_id).strip() in valid_task_ids:
                        task_id = str(task_id).strip()
                    else:
                        task_id = None

                    existing_block = db.query(DailyTimeblock).filter(DailyTimeblock.id == b_id).first()
                    if existing_block:
                        if overwrite:
                            existing_block.block_date = block_date
                            existing_block.title = title
                            existing_block.time = time_str
                            existing_block.duration_minutes = duration_minutes
                            existing_block.actual_duration_minutes = actual_duration_minutes
                            existing_block.category = category
                            existing_block.status = status
                            existing_block.is_break = is_break
                            existing_block.task_id = task_id
                            existing_block.updated_at = now
                            timeblocks_updated += 1
                        else:
                            timeblocks_skipped += 1
                    else:
                        new_block = DailyTimeblock(
                            id=b_id,
                            block_date=block_date,
                            title=title,
                            time=time_str,
                            duration_minutes=duration_minutes,
                            actual_duration_minutes=actual_duration_minutes,
                            category=category,
                            status=status,
                            is_break=is_break,
                            task_id=task_id,
                            created_at=now,
                            updated_at=now,
                        )
                        db.add(new_block)
                        timeblocks_imported += 1
                except Exception as be:
                    logger.error(f"Error processing timeblock {b_data}: {be}")
                    errors.append(f"Timeblock error: {str(be)}")
                    timeblocks_skipped += 1

        db.commit()

        total_imported = tasks_imported + goals_imported + habits_imported + timeblocks_imported
        status_str = "success"
        if errors and total_imported > 0:
            status_str = "partial"
        elif errors and total_imported == 0:
            status_str = "error"

        msg = (
            f"Migration completed. Tasks: {tasks_imported} imp, {tasks_updated} upd. "
            f"Goals: {goals_imported} imp, {goals_updated} upd. "
            f"Habits: {habits_imported} imp, {habits_updated} upd ({habit_logs_imported} logs). "
            f"Timeblocks: {timeblocks_imported} imp, {timeblocks_updated} upd."
        )

        return MigrationImportResponse(
            status=status_str,
            tasks_imported=tasks_imported,
            tasks_updated=tasks_updated,
            tasks_skipped=tasks_skipped,
            goals_imported=goals_imported,
            goals_updated=goals_updated,
            goals_skipped=goals_skipped,
            habits_imported=habits_imported,
            habits_updated=habits_updated,
            habits_skipped=habits_skipped,
            habit_logs_imported=habit_logs_imported,
            timeblocks_imported=timeblocks_imported,
            timeblocks_updated=timeblocks_updated,
            timeblocks_skipped=timeblocks_skipped,
            message=msg,
            errors=errors,
        )

    except Exception as e:
        db.rollback()
        logger.exception("Critical error during migration import")
        return MigrationImportResponse(
            status="error",
            tasks_imported=0,
            tasks_updated=0,
            tasks_skipped=len(tasks_data or []),
            goals_imported=0,
            goals_updated=0,
            goals_skipped=len(goals_data or []),
            habits_imported=0,
            habits_updated=0,
            habits_skipped=len(habits_data or []),
            habit_logs_imported=0,
            timeblocks_imported=0,
            timeblocks_updated=0,
            timeblocks_skipped=0,
            message=f"Migration failed and was rolled back cleanly: {str(e)}",
            errors=[str(e)],
        )

def get_migration_status(db: Session) -> MigrationStatusResponse:
    total_tasks = db.query(Task).count()
    total_goals = db.query(Goal).count()
    total_habits = db.query(Habit).count()
    total_habit_logs = db.query(HabitLog).count()
    total_timeblocks = db.query(DailyTimeblock).count()
    last_task = db.query(Task.created_at).order_by(Task.created_at.desc()).first()
    last_goal = db.query(Goal.created_at).order_by(Goal.created_at.desc()).first()

    return MigrationStatusResponse(
        total_tasks_in_db=total_tasks,
        total_goals_in_db=total_goals,
        total_habits_in_db=total_habits,
        total_habit_logs_in_db=total_habit_logs,
        total_timeblocks_in_db=total_timeblocks,
        last_task_created=last_task[0] if last_task else None,
        last_goal_created=last_goal[0] if last_goal else None,
    )
