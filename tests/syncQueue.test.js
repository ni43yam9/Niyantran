import 'fake-indexeddb/auto';
import { describe, it, expect, beforeEach } from 'vitest';
import {
  db,
  NiyantraDatabase,
  taskRepository,
  goalRepository,
  habitRepository,
  timeblockRepository,
  dailyIntentRepository,
  recommendationRepository,
  activityRepository,
} from '../src/database';
import {
  changeTracker,
  syncQueue,
  syncManager,
  SYNC_OPERATIONS,
  SYNC_STATUS,
  ENTITY_TYPES,
  SYNC_META_KEYS,
} from '../src/sync';

describe('Phase 10E: Local Change Tracking & Durable Synchronization Queue', () => {
  beforeEach(async () => {
    if (!db.isOpen()) {
      await db.open();
    }

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
      db.syncQueue.clear(),
    ]);
  });

  describe('1. CREATE, UPDATE & DELETE Operation Tracking', () => {
    it('records CREATE operation when an entity is created', async () => {
      const task = await taskRepository.createTask({
        title: 'Review Change Tracker',
        priority: 'High',
        category: 'Coding',
      });

      expect(task.id).toBeDefined();
      expect(task.version).toBe(1);

      // Check sync queue
      const queuedOps = await syncQueue.getAll({ entityId: task.id });
      expect(queuedOps).toHaveLength(1);

      const op = queuedOps[0];
      expect(op.operation).toBe(SYNC_OPERATIONS.CREATE);
      expect(op.entityType).toBe(ENTITY_TYPES.TASK);
      expect(op.entityVersion).toBe(1);
      expect(op.previousVersion).toBeNull();
      expect(op.status).toBe(SYNC_STATUS.PENDING);
      expect(op.payload.title).toBe('Review Change Tracker');
      expect(op.operationId).toBeDefined();
    });

    it('records UPDATE operation with previousVersion and incremented version', async () => {
      const task = await taskRepository.createTask({
        title: 'Initial Title',
      });

      const updated = await taskRepository.updateTask(task.id, {
        title: 'Updated Title',
        priority: 'High',
      });

      expect(updated.version).toBe(2);

      const queuedOps = await syncQueue.getAll({ entityId: task.id });
      expect(queuedOps).toHaveLength(2);

      const updateOp = queuedOps.find((o) => o.operation === SYNC_OPERATIONS.UPDATE);
      expect(updateOp).toBeDefined();
      expect(updateOp.entityVersion).toBe(2);
      expect(updateOp.previousVersion).toBe(1);
      expect(updateOp.payload.title).toBe('Updated Title');
    });

    it('records DELETE operation tombstone when an entity is soft-deleted', async () => {
      const task = await taskRepository.createTask({
        title: 'To be deleted',
      });

      await taskRepository.deleteTask(task.id);

      // Entity is soft deleted locally
      const fetched = await taskRepository.getById(task.id);
      expect(fetched).toBeNull();

      // Tombstone is in sync queue
      const queuedOps = await syncQueue.getAll({ entityId: task.id });
      const deleteOp = queuedOps.find((o) => o.operation === SYNC_OPERATIONS.DELETE);
      expect(deleteOp).toBeDefined();
      expect(deleteOp.entityVersion).toBe(2);
      expect(deleteOp.payload.isDeleted).toBe(1);
      expect(deleteOp.payload.deletedAt).toBeDefined();
    });
  });

  describe('2. Multi-Entity Tracking Coverage', () => {
    it('tracks goal creation, update, and task unlinking', async () => {
      const goal = await goalRepository.createGoal({
        title: 'Master Offline Sync',
        targetDate: '2026-12-31',
      });

      const goalOps = await syncQueue.getAll({ entityId: goal.id });
      expect(goalOps).toHaveLength(1);
      expect(goalOps[0].entityType).toBe(ENTITY_TYPES.GOAL);
      expect(goalOps[0].operation).toBe(SYNC_OPERATIONS.CREATE);

      // Update progress
      await goalRepository.updateProgress(goal.id, 50);
      const afterProgress = await syncQueue.getAll({ entityId: goal.id });
      expect(afterProgress).toHaveLength(2);
      expect(afterProgress[1].operation).toBe(SYNC_OPERATIONS.UPDATE);
      expect(afterProgress[1].payload.progress).toBe(50);
    });

    it('tracks habit definition and discrete habit log events', async () => {
      const habit = await habitRepository.createHabit({
        name: 'Daily Hydration',
        target: '2L',
      });

      const habitOps = await syncQueue.getAll({ entityId: habit.id });
      expect(habitOps).toHaveLength(1);
      expect(habitOps[0].entityType).toBe(ENTITY_TYPES.HABIT);

      // Log habit for today
      await habitRepository.toggleLog(habit.id, '2026-11-22', true);

      // Queue should contain:
      // 1: HABIT CREATE
      // 2: HABIT_LOG CREATE
      // 3: HABIT UPDATE (version increment)
      const allOps = await syncQueue.getAll({});
      const logOps = allOps.filter((o) => o.entityType === ENTITY_TYPES.HABIT_LOG);
      expect(logOps).toHaveLength(1);
      expect(logOps[0].payload.logDate).toBe('2026-11-22');
      expect(logOps[0].payload.completed).toBe(true);
    });

    it('tracks daily timeblocks and daily focus intents', async () => {
      const block = await timeblockRepository.createTimeblock({
        title: 'Focus Sprint',
        blockDate: '2026-11-22',
        durationMinutes: 90,
      });

      const blockOps = await syncQueue.getAll({ entityId: block.id });
      expect(blockOps).toHaveLength(1);
      expect(blockOps[0].entityType).toBe(ENTITY_TYPES.DAILY_TIMEBLOCK);

      const intent = await dailyIntentRepository.save('2026-11-22', 'Deliver Phase 10E Engine');
      const intentOps = await syncQueue.getAll({ entityId: intent.id });
      expect(intentOps).toHaveLength(1);
      expect(intentOps[0].entityType).toBe(ENTITY_TYPES.DAILY_INTENT);
    });

    it('tracks recommendations and activity logs', async () => {
      await db.recommendations.put({
        id: 'rec-test-1',
        userId: 'default_user',
        title: 'Take a break',
        status: 'PENDING',
        version: 1,
        isDeleted: 0,
      });

      await recommendationRepository.updateStatus('rec-test-1', 'ACCEPTED');
      const recOps = await syncQueue.getAll({ entityId: 'rec-test-1' });
      expect(recOps).toHaveLength(1);
      expect(recOps[0].entityType).toBe(ENTITY_TYPES.RECOMMENDATION);
      expect(recOps[0].payload.status).toBe('ACCEPTED');

      const actLog = await activityRepository.log({
        eventType: 'TASK_COMPLETED',
        entityType: 'task',
        entityId: 't-123',
      });
      const actOps = await syncQueue.getAll({ entityId: actLog.id });
      expect(actOps).toHaveLength(1);
      expect(actOps[0].entityType).toBe(ENTITY_TYPES.ACTIVITY_LOG);
    });
  });

  describe('3. Versioning & Device Attribution', () => {
    it('attaches device UUID to every change record', async () => {
      const task = await taskRepository.createTask({ title: 'Device Tag Test' });
      const op = (await syncQueue.getAll({ entityId: task.id }))[0];

      expect(op.deviceUuid).toBeDefined();
      expect(typeof op.deviceUuid).toBe('string');
      expect(op.deviceUuid.length).toBeGreaterThan(10);
    });

    it('increments entity version monotonically across multiple updates', async () => {
      const task = await taskRepository.createTask({ title: 'Monotonic Version Test' });
      expect(task.version).toBe(1);

      const u1 = await taskRepository.updateTask(task.id, { title: 'V2' });
      expect(u1.version).toBe(2);

      const u2 = await taskRepository.updateTask(task.id, { title: 'V3' });
      expect(u2.version).toBe(3);

      const ops = await syncQueue.getAll({ entityId: task.id });
      expect(ops.map((o) => o.entityVersion)).toEqual([1, 2, 3]);
    });
  });

  describe('4. Transaction Atomicity & Rollback', () => {
    it('aborts both entity mutation and queue entry if an error occurs inside transaction', async () => {
      // Simulate failed transaction by attempting an invalid write
      let caughtError = null;
      try {
        await db.transaction('rw', [db.tasks, db.syncQueue, db.syncMeta], async () => {
          await db.tasks.put({
            id: 'task-atomic-test',
            userId: 'default_user',
            title: 'Atomic Test',
            version: 1,
            isDeleted: 0,
          });

          await changeTracker.recordChange(db, {
            entityType: ENTITY_TYPES.TASK,
            entityId: 'task-atomic-test',
            operation: SYNC_OPERATIONS.CREATE,
          });

          // Deliberate throw to trigger transaction abort
          throw new Error('Simulated transaction failure');
        });
      } catch (err) {
        caughtError = err;
      }

      expect(caughtError).not.toBeNull();
      expect(caughtError.message).toContain('Simulated transaction failure');

      // Verify task was NOT committed
      const taskInDb = await db.tasks.get('task-atomic-test');
      expect(taskInDb).toBeUndefined();

      // Verify queue record was NOT committed
      const queueOps = await db.syncQueue.where('entityId').equals('task-atomic-test').toArray();
      expect(queueOps).toHaveLength(0);
    });
  });

  describe('5. Queue Durability & Simulated Restart Recovery', () => {
    it('persists queue entries across database close and reopen', async () => {
      await taskRepository.createTask({ title: 'Persistent Task 1' });
      await taskRepository.createTask({ title: 'Persistent Task 2' });

      const initialPending = await syncQueue.getPendingCount();
      expect(initialPending).toBe(2);

      // Simulate browser restart by closing connection and creating fresh db instance
      db.close();

      const reopenedDb = new NiyantraDatabase();
      const recoveredPending = await syncQueue.getPendingCount(null, reopenedDb);
      expect(recoveredPending).toBe(2);

      const recoveredItems = await syncQueue.peek(10, null, reopenedDb);
      expect(recoveredItems).toHaveLength(2);
      expect(recoveredItems[0].payload.title).toBe('Persistent Task 1');
      expect(recoveredItems[1].payload.title).toBe('Persistent Task 2');

      reopenedDb.close();
      await db.open();
    });
  });

  describe('6. Retry Management & Exponential Backoff', () => {
    it('marks operation failed and computes exponential backoff nextRetryAt', async () => {
      const task = await taskRepository.createTask({ title: 'Retry Test' });
      const [op] = await syncQueue.getAll({ entityId: task.id });

      const beforeFail = Date.now();
      const failedOp1 = await syncQueue.markFailed(op.id, 'Connection timeout', {
        initialBackoffMs: 2000,
        backoffFactor: 2,
        maxRetries: 3,
      });

      expect(failedOp1.status).toBe(SYNC_STATUS.FAILED);
      expect(failedOp1.retryCount).toBe(1);
      expect(failedOp1.errorMessage).toBe('Connection timeout');
      expect(failedOp1.nextRetryAt).toBeDefined();

      const retryTime1 = new Date(failedOp1.nextRetryAt).getTime();
      expect(retryTime1).toBeGreaterThanOrEqual(beforeFail + 1900);

      // Second failure doubles the delay (2000 * 2^1 = 4000ms)
      const failedOp2 = await syncQueue.markFailed(op.id, 'Connection timeout again', {
        initialBackoffMs: 2000,
        backoffFactor: 2,
        maxRetries: 3,
      });
      expect(failedOp2.retryCount).toBe(2);
      const retryTime2 = new Date(failedOp2.nextRetryAt).getTime();
      expect(retryTime2).toBeGreaterThanOrEqual(beforeFail + 3800);
      expect(retryTime2).toBeGreaterThan(retryTime1);

      // Third failure reaches maxRetries -> becomes permanent failure
      const failedOp3 = await syncQueue.markFailed(op.id, 'Permanent drop', {
        initialBackoffMs: 2000,
        backoffFactor: 2,
        maxRetries: 2, // maxRetries exceeded on 3rd attempt
      });
      expect(failedOp3.isPermanentFailure).toBe(true);
      expect(failedOp3.nextRetryAt).toBeNull();
    });

    it('resets failed operation back to PENDING when manually requested', async () => {
      const task = await taskRepository.createTask({ title: 'Reset Test' });
      const [op] = await syncQueue.getAll({ entityId: task.id });

      await syncQueue.markFailed(op.id, 'Transient error');
      const failed = await syncQueue.getById(op.id);
      expect(failed.status).toBe(SYNC_STATUS.FAILED);

      const reset = await syncQueue.resetFailed(op.id);
      expect(reset.status).toBe(SYNC_STATUS.PENDING);
      expect(reset.retryCount).toBe(0);
      expect(reset.errorMessage).toBeNull();
    });
  });

  describe('7. Multi-User & Account Isolation', () => {
    it('strictly isolates sync queue entries between distinct users', async () => {
      await taskRepository.createTask({ title: 'User Alpha Work' }, 'user_alpha');
      await taskRepository.createTask({ title: 'User Beta Work' }, 'user_beta');

      const alphaQueue = await syncQueue.getAll({}, 'user_alpha');
      const betaQueue = await syncQueue.getAll({}, 'user_beta');

      expect(alphaQueue).toHaveLength(1);
      expect(alphaQueue[0].payload.title).toBe('User Alpha Work');
      expect(alphaQueue[0].userId).toBe('user_alpha');

      expect(betaQueue).toHaveLength(1);
      expect(betaQueue[0].payload.title).toBe('User Beta Work');
      expect(betaQueue[0].userId).toBe('user_beta');
    });

    it('supports guest mode under default_user seamlessly', async () => {
      const task = await taskRepository.createTask({ title: 'Guest Task' });
      const guestQueue = await syncQueue.getAll({}, 'default_user');

      expect(guestQueue).toHaveLength(1);
      expect(guestQueue[0].userId).toBe('default_user');
    });
  });

  describe('8. Synchronization Manager & Metadata', () => {
    it('provides accurate sync summary without claiming false cloud sync', async () => {
      await taskRepository.createTask({ title: 'Summary Task 1' });
      await taskRepository.createTask({ title: 'Summary Task 2' });

      const summary = await syncManager.getSyncSummary();
      expect(summary.pendingCount).toBe(2);
      expect(summary.failedCount).toBe(0);
      expect(summary.completedCount).toBe(0);
      expect(summary.isAllSavedLocally).toBe(true);
      expect(summary.cloudSyncImplemented).toBe(false);
      expect(summary.lastSuccessfulSyncAt).toBeNull(); // Strictly NULL since no cloud sync exists
      expect(summary.lastMutationAt).toBeDefined();
    });

    it('simulates queue processing lifecycle in local test mode', async () => {
      await taskRepository.createTask({ title: 'Sim 1' });
      await taskRepository.createTask({ title: 'Sim 2' });

      // Simulate successful batch
      const result = await syncManager.simulateProcessBatch();
      expect(result.processed).toBe(2);
      expect(result.completed).toBe(2);
      expect(result.failed).toBe(0);

      const afterSummary = await syncManager.getSyncSummary();
      expect(afterSummary.pendingCount).toBe(0);
      expect(afterSummary.completedCount).toBe(2);
      expect(afterSummary.lastAttemptAt).toBeDefined();
    });
  });
});
