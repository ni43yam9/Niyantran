import 'fake-indexeddb/auto';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { db, NiyantraDatabase } from '../src/database';
import { taskRepository } from '../src/database/repositories/taskRepository';
import { goalRepository } from '../src/database/repositories/goalRepository';
import { habitRepository } from '../src/database/repositories/habitRepository';
import { timeblockRepository } from '../src/database/repositories/timeblockRepository';
import { dailyIntentRepository } from '../src/database/repositories/dailyIntentRepository';
import { activityRepository } from '../src/database/repositories/activityRepository';
import { recommendationRepository } from '../src/database/repositories/recommendationRepository';
import { migrateLocalStorageToIndexedDB, MIGRATION_FLAG_KEY, LOCALSTORAGE_BACKUP_KEY } from '../src/database/migrations';

describe('Phase 10D: IndexedDB Client Storage & Offline Repositories', () => {
  beforeEach(async () => {
    // Clear all tables before each test
    await Promise.all([
      db.tasks.clear(),
      db.goals.clear(),
      db.habits.clear(),
      db.habitLogs.clear(),
      db.dailyTimeblocks.clear(),
      db.dailyIntents.clear(),
      db.activityLogs.clear(),
      db.recommendations.clear(),
      db.syncMeta.clear(),
    ]);
  });

  describe('1. Database Initialization & Schema', () => {
    it('initializes db with proper table names and primary keys', () => {
      expect(db.name).toBe('niyantra_client_db');
      expect(db.tables.map((t) => t.name)).toEqual(
        expect.arrayContaining([
          'tasks',
          'goals',
          'habits',
          'habit_logs',
          'daily_timeblocks',
          'daily_intents',
          'activity_logs',
          'recommendations',
          'sync_meta',
        ])
      );
    });

    it('resolves fallback active user id as default_user when no auth token is set', () => {
      const activeUser = db.getActiveUserId();
      expect(activeUser).toBe('default_user');
    });

    it('resolves stable hardware device UUID', () => {
      const devUuid = db.getClientDeviceUUID();
      expect(devUuid).toBeDefined();
      expect(typeof devUuid).toBe('string');
      expect(devUuid.length).toBeGreaterThan(10);
    });
  });

  describe('2. User Isolation & Multi-Account Partitioning', () => {
    it('isolates tasks between different user accounts', async () => {
      await taskRepository.createTask(
        { title: 'User Alpha Task', priority: 'High', status: 'Pending' },
        'user_alpha'
      );
      await taskRepository.createTask(
        { title: 'User Beta Task', priority: 'Medium', status: 'Pending' },
        'user_beta'
      );

      const alphaTasks = await taskRepository.getAll({}, 'user_alpha');
      const betaTasks = await taskRepository.getAll({}, 'user_beta');

      expect(alphaTasks).toHaveLength(1);
      expect(alphaTasks[0].title).toBe('User Alpha Task');

      expect(betaTasks).toHaveLength(1);
      expect(betaTasks[0].title).toBe('User Beta Task');
    });

    it('isolates goals and habits between different accounts', async () => {
      await goalRepository.createGoal({ title: 'Goal 1' }, 'user_alpha');
      await goalRepository.createGoal({ title: 'Goal 2' }, 'user_beta');

      const alphaGoals = await goalRepository.getAll({}, 'user_alpha');
      const betaGoals = await goalRepository.getAll({}, 'user_beta');

      expect(alphaGoals).toHaveLength(1);
      expect(alphaGoals[0].title).toBe('Goal 1');
      expect(betaGoals).toHaveLength(1);
      expect(betaGoals[0].title).toBe('Goal 2');
    });
  });

  describe('3. Task Repository Offline CRUD & Filtering', () => {
    it('creates, retrieves, updates, toggles, and soft-deletes a task', async () => {
      // 1. Create
      const created = await taskRepository.createTask({
        title: 'Complete Phase 10D Tests',
        description: 'Verify all offline repository operations',
        priority: 'High',
        category: 'Coding',
        dueDate: '2026-11-22',
      });

      expect(created.id).toBeDefined();
      expect(created.version).toBe(1);
      expect(created.isDeleted).toBe(0);

      // 2. Retrieve by ID
      const fetched = await taskRepository.getById(created.id);
      expect(fetched).not.toBeNull();
      expect(fetched.title).toBe('Complete Phase 10D Tests');

      // 3. Update
      const updated = await taskRepository.updateTask(created.id, {
        title: 'Complete Phase 10D Tests Updated',
      });
      expect(updated.title).toBe('Complete Phase 10D Tests Updated');
      expect(updated.version).toBe(2);

      // 4. Toggle completion
      const toggled = await taskRepository.toggleCompletion(created.id);
      expect(toggled.status).toBe('Completed');
      expect(toggled.completionDate).toBeDefined();

      // 5. Soft Delete
      const deleted = await taskRepository.deleteTask(created.id);
      expect(deleted).toBe(true);

      const afterDelete = await taskRepository.getById(created.id);
      expect(afterDelete).toBeNull();

      const allActive = await taskRepository.getAll({});
      expect(allActive).toHaveLength(0);
    });

    it('filters tasks by status, priority, category, and search text', async () => {
      await taskRepository.bulkUpsert([
        { id: 't1', title: 'Write tests', priority: 'High', status: 'Pending', category: 'Coding' },
        { id: 't2', title: 'Review PR', priority: 'Medium', status: 'Completed', category: 'Work' },
        { id: 't3', title: 'Buy milk', priority: 'Low', status: 'Pending', category: 'Personal' },
      ]);

      const highTasks = await taskRepository.getAll({ priority: 'High' });
      expect(highTasks).toHaveLength(1);
      expect(highTasks[0].id).toBe('t1');

      const completed = await taskRepository.getAll({ status: 'Completed' });
      expect(completed).toHaveLength(1);
      expect(completed[0].id).toBe('t2');

      const searched = await taskRepository.getAll({ search: 'milk' });
      expect(searched).toHaveLength(1);
      expect(searched[0].id).toBe('t3');
    });
  });

  describe('4. Goal Repository & Cascading Task Unlinking', () => {
    it('creates goal and safely unlinks associated tasks upon soft deletion', async () => {
      const goal = await goalRepository.createGoal({
        title: 'Launch Niyantra Offline Engine',
        goalType: 'OUTCOME',
        progress: 40,
      });

      const task = await taskRepository.createTask({
        title: 'Task linked to goal',
        goalId: goal.id,
      });

      expect(task.goalId).toBe(goal.id);

      // Delete goal
      await goalRepository.deleteGoal(goal.id);

      // Verify goal is soft deleted
      const fetchedGoal = await goalRepository.getById(goal.id);
      expect(fetchedGoal).toBeNull();

      // Verify task's goalId was cleanly unlinked to prevent orphan reference
      const fetchedTask = await taskRepository.getById(task.id);
      expect(fetchedTask.goalId).toBeNull();
    });

    it('updates goal progress and status', async () => {
      const goal = await goalRepository.createGoal({
        title: 'Master Dexie',
        progress: 50,
      });

      const updated = await goalRepository.updateProgress(goal.id, 100, 'Completed');
      expect(updated.progress).toBe(100);
      expect(updated.status).toBe('Completed');
    });
  });

  describe('5. Habit Repository & Historical Log Aggregation', () => {
    it('creates habit and logs daily completions offline', async () => {
      const habit = await habitRepository.createHabit({
        name: 'Daily Meditation',
        target: '15 mins',
        frequency: 'DAILY',
        baseStreak: 3,
      });

      expect(habit.id).toBeDefined();

      // Toggle log for date 1
      const log1 = await habitRepository.toggleLog(habit.id, '2026-11-20', true);
      expect(log1.completedDates['2026-11-20']).toBe(true);

      // Toggle log for date 2
      const log2 = await habitRepository.toggleLog(habit.id, '2026-11-21', true);
      expect(log2.completedDates['2026-11-20']).toBe(true);
      expect(log2.completedDates['2026-11-21']).toBe(true);

      // Verify logs table in DB
      const logsInDb = await db.habitLogs.where('habitId').equals(habit.id).toArray();
      expect(logsInDb).toHaveLength(2);

      // Toggle off date 1
      const logOff = await habitRepository.toggleLog(habit.id, '2026-11-20', false);
      expect(logOff.completedDates['2026-11-20']).toBeFalsy();
      expect(logOff.completedDates['2026-11-21']).toBe(true);
    });
  });

  describe('6. Timeblock Repository', () => {
    it('manages daily timeblocks and queries by date', async () => {
      const blocksToday = [
        { id: 'b1', title: 'Deep Work Session', startTime: '09:00', endTime: '11:00', durationMinutes: 120 },
        { id: 'b2', title: 'Lunch Break', startTime: '12:00', endTime: '13:00', durationMinutes: 60, isBreak: 1 },
      ];

      await timeblockRepository.saveForDate('2026-11-22', blocksToday);

      const retrieved = await timeblockRepository.getByDate('2026-11-22');
      expect(retrieved).toHaveLength(2);
      expect(retrieved[0].title).toBe('Deep Work Session');
      expect(retrieved[1].isBreak).toBe(1);

      // Query different date returns empty
      const emptyTomorrow = await timeblockRepository.getByDate('2026-11-23');
      expect(emptyTomorrow).toHaveLength(0);
    });
  });

  describe('7. Daily Intent Repository', () => {
    it('saves and retrieves daily intent maps', async () => {
      await dailyIntentRepository.save('2026-11-22', 'Deliver Phase 10D Offline Client Storage');
      await dailyIntentRepository.save('2026-11-23', 'Optimize Dexie Indexes');

      const map = await dailyIntentRepository.getMap();
      expect(map['2026-11-22']).toBe('Deliver Phase 10D Offline Client Storage');
      expect(map['2026-11-23']).toBe('Optimize Dexie Indexes');

      const single = await dailyIntentRepository.getByDate('2026-11-22');
      expect(single.intentText).toBe('Deliver Phase 10D Offline Client Storage');
    });
  });

  describe('8. Activity Log Repository', () => {
    it('tracks audit trail of productivity events', async () => {
      await activityRepository.log({
        eventType: 'TASK_CREATED',
        entityType: 'task',
        entityId: 't-101',
        details: { title: 'Test Task' },
      });

      await activityRepository.log({
        eventType: 'TASK_COMPLETED',
        entityType: 'task',
        entityId: 't-101',
      });

      const recent = await activityRepository.getRecent({ limit: 10 });
      expect(recent).toHaveLength(2);
      expect(recent[0].eventType).toBe('TASK_COMPLETED');
      expect(recent[1].eventType).toBe('TASK_CREATED');
      expect(recent[0].deviceUuid).toBeDefined();
    });
  });

  describe('9. Recommendation Repository', () => {
    it('caches and updates recommendations offline', async () => {
      await recommendationRepository.bulkUpsert([
        {
          id: 'rec-1',
          title: 'Review Overdue Work',
          score: 0.95,
          priority: 'HIGH',
          status: 'PENDING',
        },
        {
          id: 'rec-2',
          title: 'Hydrate',
          score: 0.4,
          priority: 'LOW',
          status: 'PENDING',
        },
      ]);

      const recs = await recommendationRepository.getAll();
      expect(recs).toHaveLength(2);
      expect(recs[0].id).toBe('rec-1'); // Sorted by score descending

      // Accept recommendation
      const updated = await recommendationRepository.updateStatus('rec-1', 'ACCEPTED');
      expect(updated.status).toBe('ACCEPTED');

      const pendingOnly = await recommendationRepository.getAll({ status: 'PENDING' });
      expect(pendingOnly).toHaveLength(1);
      expect(pendingOnly[0].id).toBe('rec-2');
    });
  });

  describe('10. Safe Migration from Legacy LocalStorage to IndexedDB', () => {
    it('migrates legacy localStorage items into IndexedDB with zero loss and creates backup', async () => {
      // Setup mock legacy localStorage
      const legacyTasks = [
        { id: 'lt-1', title: 'Legacy Task 1', priority: 'High', status: 'Pending' },
        { id: 'lt-2', title: 'Legacy Task 2', priority: 'Low', status: 'Completed' },
      ];
      const legacyGoals = [
        { id: 'lg-1', title: 'Legacy Goal 1', progress: 50 },
      ];
      const legacyHabits = [
        { id: 'lh-1', name: 'Legacy Habit 1', completed_dates: ['2026-11-20', '2026-11-21'] },
      ];
      const legacyIntents = {
        '2026-11-22': 'Legacy Intent Today',
      };
      const legacyTimeblocks = {
        '2026-11-22': [{ id: 'tb-1', title: 'Legacy Block 1', durationMinutes: 60 }],
      };

      // Mock localStorage methods
      const store = {
        niyantra_tasks: JSON.stringify(legacyTasks),
        niyantra_goals: JSON.stringify(legacyGoals),
        niyantra_habits: JSON.stringify(legacyHabits),
        niyantra_daily_intents: JSON.stringify(legacyIntents),
        niyantra_daily_timeblocks: JSON.stringify(legacyTimeblocks),
      };

      globalThis.window = {
        localStorage: {
          getItem: (key) => store[key] || null,
          setItem: (key, val) => {
            store[key] = String(val);
          },
          removeItem: (key) => {
            delete store[key];
          },
        },
      };

      // Run migration
      const migrationResult = await migrateLocalStorageToIndexedDB(true);
      expect(migrationResult.success).toBe(true);
      expect(migrationResult.migratedCounts.tasks).toBe(2);
      expect(migrationResult.migratedCounts.goals).toBe(1);
      expect(migrationResult.migratedCounts.habits).toBe(1);
      expect(migrationResult.migratedCounts.habitLogs).toBe(2);
      expect(migrationResult.migratedCounts.intents).toBe(1);
      expect(migrationResult.migratedCounts.timeblocks).toBe(1);

      // Verify IndexedDB contents
      const idbTasks = await taskRepository.getAll();
      expect(idbTasks).toHaveLength(2);
      expect(idbTasks.map((t) => t.id)).toEqual(expect.arrayContaining(['lt-1', 'lt-2']));

      const idbGoals = await goalRepository.getAll();
      expect(idbGoals).toHaveLength(1);
      expect(idbGoals[0].id).toBe('lg-1');

      const idbHabits = await habitRepository.getAll();
      expect(idbHabits).toHaveLength(1);
      expect(idbHabits[0].completedDates['2026-11-20']).toBe(true);

      // Verify backup exists in localStorage
      expect(store[LOCALSTORAGE_BACKUP_KEY]).toBeDefined();
      const backupParsed = JSON.parse(store[LOCALSTORAGE_BACKUP_KEY]);
      expect(backupParsed.data.tasks).toHaveLength(2);

      // Verify migration flag is set
      expect(store[MIGRATION_FLAG_KEY]).toBe('true');

      // Verify idempotency: subsequent run skips without duplicating
      const secondRun = await migrateLocalStorageToIndexedDB(false);
      expect(secondRun.alreadyMigrated).toBe(true);
    });

    it('recovers gracefully from malformed or corrupt localStorage data', async () => {
      const corruptStore = {
        niyantra_tasks: '{{invalid json!///',
        niyantra_goals: 'not a list',
        niyantra_habits: null,
      };

      globalThis.window = {
        localStorage: {
          getItem: (key) => corruptStore[key] || null,
          setItem: (key, val) => {
            corruptStore[key] = String(val);
          },
          removeItem: (key) => {
            delete corruptStore[key];
          },
        },
      };

      const result = await migrateLocalStorageToIndexedDB(true);
      expect(result.success).toBe(true);
      expect(result.migratedCounts.tasks).toBe(0);
    });
  });

  describe('11. Robustness, Concurrency & Date Logic', () => {
    it('properly identifies today and overdue tasks offline', async () => {
      const todayStr = new Date().toISOString().slice(0, 10);
      const yesterdayStr = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      const tomorrowStr = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

      await taskRepository.createTask({
        id: 'task-today',
        title: 'Task Due Today',
        dueDate: todayStr,
        status: 'Pending',
      });

      await taskRepository.createTask({
        id: 'task-overdue',
        title: 'Task Overdue',
        dueDate: yesterdayStr,
        status: 'Pending',
      });

      await taskRepository.createTask({
        id: 'task-future',
        title: 'Task in Future',
        dueDate: tomorrowStr,
        status: 'Pending',
      });

      const todayTasks = await taskRepository.getAll({ isToday: true });
      expect(todayTasks.map((t) => t.id)).toContain('task-today');
      expect(todayTasks.map((t) => t.id)).not.toContain('task-future');

      const overdueTasks = await taskRepository.getAll({ isOverdue: true });
      expect(overdueTasks.map((t) => t.id)).toContain('task-overdue');
      expect(overdueTasks.map((t) => t.id)).not.toContain('task-today');
      expect(overdueTasks.map((t) => t.id)).not.toContain('task-future');
    });

    it('increments version number monotonically on subsequent updates', async () => {
      const task = await taskRepository.createTask({ title: 'Versioned Task' });
      expect(task.version).toBe(1);

      const v2 = await taskRepository.updateTask(task.id, { title: 'Versioned Task v2' });
      expect(v2.version).toBe(2);

      const v3 = await taskRepository.updateTask(task.id, { title: 'Versioned Task v3' });
      expect(v3.version).toBe(3);
    });

    it('supports hard deletion when requested via options', async () => {
      const task = await taskRepository.createTask({ title: 'Temporary Task' });
      const rawInDb = await db.tasks.get(task.id);
      expect(rawInDb).toBeDefined();

      // Hard delete
      await taskRepository.delete(task.id, null, { softDelete: false });

      const rawAfterHardDelete = await db.tasks.get(task.id);
      expect(rawAfterHardDelete).toBeUndefined();
    });
  });
});
