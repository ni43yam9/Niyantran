import { db } from './db';
import { v4 as uuidv4 } from '../utils/uuid';

export const MIGRATION_FLAG_KEY = 'niyantra_idb_migrated_v1';
export const LOCALSTORAGE_BACKUP_KEY = 'niyantra_localstorage_backup_pre_idb';

/**
 * Migrates legacy localStorage productivity data to IndexedDB.
 * Ensures zero data loss, id preservation, and data integrity verification.
 */
export async function migrateLocalStorageToIndexedDB(forced = false) {
  if (typeof window === 'undefined' || !window.localStorage) {
    return { success: true, message: 'No localStorage environment present.' };
  }

  // Idempotency check: don't re-run unless forced
  const alreadyMigrated = window.localStorage.getItem(MIGRATION_FLAG_KEY);
  if (alreadyMigrated === 'true' && !forced) {
    return {
      success: true,
      alreadyMigrated: true,
      message: 'IndexedDB migration already completed.',
    };
  }

  const userId = db.getActiveUserId();
  const now = new Date().toISOString();

  console.info(`[Niyantra Migration] Starting localStorage to IndexedDB migration for user: ${userId}`);

  // Step 1: Read and parse all legacy localStorage keys
  let rawTasks = [];
  let rawGoals = [];
  let rawHabits = [];
  let rawIntents = {};
  let rawTimeblocks = {};

  try {
    const tasksJson = window.localStorage.getItem('niyantra_tasks');
    if (tasksJson) rawTasks = JSON.parse(tasksJson) || [];
  } catch (e) {
    console.warn('[Niyantra Migration] Failed parsing niyantra_tasks:', e);
  }

  try {
    const goalsJson = window.localStorage.getItem('niyantra_goals');
    if (goalsJson) rawGoals = JSON.parse(goalsJson) || [];
  } catch (e) {
    console.warn('[Niyantra Migration] Failed parsing niyantra_goals:', e);
  }

  try {
    const habitsJson = window.localStorage.getItem('niyantra_habits');
    if (habitsJson) rawHabits = JSON.parse(habitsJson) || [];
  } catch (e) {
    console.warn('[Niyantra Migration] Failed parsing niyantra_habits:', e);
  }

  try {
    const intentsJson = window.localStorage.getItem('niyantra_daily_intents');
    if (intentsJson) rawIntents = JSON.parse(intentsJson) || {};
  } catch (e) {
    console.warn('[Niyantra Migration] Failed parsing niyantra_daily_intents:', e);
  }

  try {
    const timeblocksJson = window.localStorage.getItem('niyantra_daily_timeblocks');
    if (timeblocksJson) rawTimeblocks = JSON.parse(timeblocksJson) || {};
  } catch (e) {
    console.warn('[Niyantra Migration] Failed parsing niyantra_daily_timeblocks:', e);
  }

  // Step 2: Create a complete safe backup in localStorage
  const backupPayload = {
    timestamp: now,
    userId,
    data: {
      tasks: rawTasks,
      goals: rawGoals,
      habits: rawHabits,
      intents: rawIntents,
      timeblocks: rawTimeblocks,
    },
  };

  try {
    window.localStorage.setItem(LOCALSTORAGE_BACKUP_KEY, JSON.stringify(backupPayload));
    console.info('[Niyantra Migration] Pre-migration backup successfully stored in localStorage.');
  } catch (e) {
    console.error('[Niyantra Migration] Could not create pre-migration backup in localStorage:', e);
    // Continue even if backup fails due to quota, but warn
  }

  // Step 3: Transform records for IndexedDB
  const transformedTasks = rawTasks.map((t) => ({
    id: String(t.id || uuidv4()),
    userId,
    title: t.title || 'Untitled Task',
    description: t.description || '',
    category: t.category || 'WORK',
    priority: t.priority || 'MEDIUM',
    status: t.status || 'TODO',
    taskType: t.taskType || 'TASK',
    dueDate: t.dueDate || null,
    startDate: t.startDate || null,
    goalId: t.goalId ? String(t.goalId) : null,
    estimatedMinutes: t.estimatedMinutes || null,
    actualMinutes: t.actualMinutes || null,
    completionDate: t.completionDate || null,
    isDeleted: t.isDeleted ? 1 : 0,
    version: t.version || 1,
    createdAt: t.createdAt || now,
    updatedAt: t.updatedAt || now,
  }));

  const transformedGoals = rawGoals.map((g) => ({
    id: String(g.id || uuidv4()),
    userId,
    title: g.title || 'Untitled Goal',
    description: g.description || '',
    category: g.category || 'WORK',
    priority: g.priority || 'MEDIUM',
    status: g.status || 'IN_PROGRESS',
    goalType: g.goalType || 'TARGET',
    targetDate: g.targetDate || null,
    progress: g.progress != null ? Number(g.progress) : 0,
    metrics: g.metrics || {},
    isDeleted: g.isDeleted ? 1 : 0,
    version: g.version || 1,
    createdAt: g.createdAt || now,
    updatedAt: g.updatedAt || now,
  }));

  const transformedHabits = [];
  const transformedHabitLogs = [];

  for (const h of rawHabits) {
    const habitId = String(h.id || uuidv4());
    const completedDates = Array.isArray(h.completed_dates)
      ? h.completed_dates
      : Array.isArray(h.completedDates)
      ? h.completedDates
      : [];

    transformedHabits.push({
      id: habitId,
      userId,
      name: h.name || 'Untitled Habit',
      target: h.target || 'Daily',
      category: h.category || 'WORK',
      frequency: h.frequency || 'DAILY',
      baseStreak: h.baseStreak || 0,
      completedDates,
      archived: h.archived ? 1 : 0,
      isDeleted: h.isDeleted ? 1 : 0,
      version: h.version || 1,
      createdAt: h.createdAt || now,
      updatedAt: h.updatedAt || now,
    });

    for (const d of completedDates) {
      transformedHabitLogs.push({
        id: uuidv4(),
        habitId,
        userId,
        logDate: d,
        completed: 1,
        isDeleted: 0,
        createdAt: now,
        updatedAt: now,
      });
    }
  }

  const transformedIntents = Object.entries(rawIntents).map(([dateStr, text]) => ({
    id: uuidv4(),
    userId,
    intentDate: dateStr,
    intentText: String(text || '').trim(),
    version: 1,
    isDeleted: 0,
    createdAt: now,
    updatedAt: now,
  }));

  const transformedTimeblocks = [];
  for (const [dateStr, blocks] of Object.entries(rawTimeblocks)) {
    if (Array.isArray(blocks)) {
      for (const b of blocks) {
        transformedTimeblocks.push({
          id: String(b.id || uuidv4()),
          userId,
          blockDate: dateStr,
          title: b.title || 'Untitled Block',
          startTime: b.startTime || '09:00',
          endTime: b.endTime || '10:00',
          durationMinutes: b.durationMinutes || 60,
          status: b.status || 'PLANNED',
          isBreak: b.isBreak ? 1 : 0,
          taskId: b.taskId ? String(b.taskId) : null,
          isDeleted: b.isDeleted ? 1 : 0,
          version: b.version || 1,
          createdAt: b.createdAt || now,
          updatedAt: b.updatedAt || now,
        });
      }
    }
  }

  // Step 4: Write to IndexedDB via atomic transaction
  try {
    await db.transaction(
      'rw',
      [db.tasks, db.goals, db.habits, db.habitLogs, db.dailyIntents, db.dailyTimeblocks, db.syncMeta],
      async () => {
        if (transformedTasks.length > 0) {
          await db.tasks.bulkPut(transformedTasks);
        }
        if (transformedGoals.length > 0) {
          await db.goals.bulkPut(transformedGoals);
        }
        if (transformedHabits.length > 0) {
          await db.habits.bulkPut(transformedHabits);
        }
        if (transformedHabitLogs.length > 0) {
          await db.habitLogs.bulkPut(transformedHabitLogs);
        }
        if (transformedIntents.length > 0) {
          await db.dailyIntents.bulkPut(transformedIntents);
        }
        if (transformedTimeblocks.length > 0) {
          await db.dailyTimeblocks.bulkPut(transformedTimeblocks);
        }

        // Store sync migration metadata
        await db.syncMeta.put({
          key: 'last_localstorage_migration',
          value: {
            migratedAt: now,
            counts: {
              tasks: transformedTasks.length,
              goals: transformedGoals.length,
              habits: transformedHabits.length,
              habitLogs: transformedHabitLogs.length,
              intents: transformedIntents.length,
              timeblocks: transformedTimeblocks.length,
            },
          },
          updatedAt: now,
        });
      }
    );

    // Step 5: Verification check
    const taskCountInDb = await db.tasks.where('userId').equals(userId).count();
    const goalCountInDb = await db.goals.where('userId').equals(userId).count();
    const habitCountInDb = await db.habits.where('userId').equals(userId).count();

    if (
      taskCountInDb < transformedTasks.length ||
      goalCountInDb < transformedGoals.length ||
      habitCountInDb < transformedHabits.length
    ) {
      throw new Error(
        `Verification failed: counts in IndexedDB do not match migration inputs ` +
          `(Tasks: ${taskCountInDb}/${transformedTasks.length}, ` +
          `Goals: ${goalCountInDb}/${transformedGoals.length}, ` +
          `Habits: ${habitCountInDb}/${transformedHabits.length})`
      );
    }

    // Step 6: Mark migration flag in localStorage
    window.localStorage.setItem(MIGRATION_FLAG_KEY, 'true');

    const result = {
      success: true,
      migratedCounts: {
        tasks: transformedTasks.length,
        goals: transformedGoals.length,
        habits: transformedHabits.length,
        habitLogs: transformedHabitLogs.length,
        intents: transformedIntents.length,
        timeblocks: transformedTimeblocks.length,
      },
    };

    console.info('[Niyantra Migration] Migration successfully completed and verified:', result);
    return result;
  } catch (err) {
    console.error('[Niyantra Migration] Migration transaction failed:', err);
    return {
      success: false,
      error: err.message,
    };
  }
}
