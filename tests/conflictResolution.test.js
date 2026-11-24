import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import 'fake-indexeddb/auto';

// Polyfill localStorage for node environment
const store = new Map();
const localStorageMock = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, val) => store.set(key, String(val)),
  removeItem: (key) => store.delete(key),
  clear: () => store.clear(),
};
globalThis.localStorage = localStorageMock;
if (typeof window !== 'undefined') {
  window.localStorage = localStorageMock;
} else {
  globalThis.window = { localStorage: localStorageMock };
}

import { db, NiyantraDatabase } from '../src/database/db';
import { taskRepository } from '../src/database/repositories/taskRepository';
import { goalRepository } from '../src/database/repositories/goalRepository';
import { habitRepository } from '../src/database/repositories/habitRepository';
import { syncManager } from '../src/sync/syncManager';
import { syncQueue } from '../src/sync/syncQueue';
import {
  conflictDetector,
  conflictResolver,
  entityMergeHelpers,
  CONFLICT_STATUS,
  RESOLUTION_STRATEGY,
  SYNC_OPERATIONS,
  SYNC_STATUS,
  SYNC_META_KEYS,
  ENTITY_TYPES,
} from '../src/sync';

describe('Phase 10H: Advanced Conflict Detection & Resolution Suite', () => {
  let dbCounter = 0;
  const createIsolatedDb = async (nameSuffix = '') => {
    dbCounter++;
    const testDb = new NiyantraDatabase({ name: `test_conflict_db_${Date.now()}_${dbCounter}_${nameSuffix}` });
    await testDb.open();
    return testDb;
  };

  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('niyantra_access_token', 'mock_token_phase10h');
    localStorage.setItem('niyantra_user', JSON.stringify({ id: 'user_conflict_1', name: 'Conflict User' }));

    if (!db.isOpen()) {
      await db.open();
    }
    await Promise.all([
      db.tasks.clear(),
      db.goals.clear(),
      db.habits.clear(),
      db.habitLogs.clear(),
      db.dailyTimeblocks.clear(),
      db.dailyIntents.clear(),
      db.recommendations.clear(),
      db.activityLogs.clear(),
      db.syncMeta.clear(),
      db.syncQueue.clear(),
      db.conflicts.clear(),
    ]);
  });

  afterEach(async () => {
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // SCENARIO 1: Two devices updating the same task (Concurrent Offline Edits)
  // -------------------------------------------------------------------------
  it('1. Detects concurrent offline modifications on the same task without losing either version', async () => {
    const testDb = await createIsolatedDb('scenario1');
    const taskId = 'task-concurrent-101';
    const userId = 'user_conflict_1';

    // Base task setup
    await testDb.tasks.put({
      id: taskId,
      userId,
      title: 'Original Title',
      priority: 'Low',
      version: 1,
      isDeleted: 0,
      updatedAt: '2026-11-22T10:00:00.000Z',
    });

    // Device A modifies task while offline
    await taskRepository.update(
      taskId,
      { title: 'Device A Title', priority: 'High', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    // Verify local pending operation exists in syncQueue
    const pending = await testDb.syncQueue
      .where('[userId+entityType+entityId]')
      .equals([userId, 'task', taskId])
      .toArray();
    expect(pending.length).toBe(1);
    expect(pending[0].payload.title).toBe('Device A Title');

    // Remote change arrives from Device B (v2, different title and priority)
    const remoteChange = {
      id: 201,
      operation_uuid: 'op-remote-device-b',
      device_uuid: 'device-b-uuid',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: {
        id: taskId,
        title: 'Device B Title',
        priority: 'Medium',
        version: 2,
      },
    };

    // Evaluate conflict
    const evalResult = await conflictDetector.detectConflict({
      change: remoteChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);
    expect(evalResult.reason).toBe('CONCURRENT_OFFLINE_EDITS');

    // Record conflict
    const conflictRecord = await conflictDetector.recordConflict({
      change: remoteChange,
      conflictEvaluation: evalResult,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(conflictRecord.status).toBe(CONFLICT_STATUS.PENDING_RESOLUTION);
    expect(conflictRecord.localData.title).toBe('Device A Title');
    expect(conflictRecord.remoteData.title).toBe('Device B Title');
    expect(conflictRecord.localVersion).toBe(2);
    expect(conflictRecord.remoteVersion).toBe(2);

    // Ensure local task was NOT silently overwritten
    const currentLocal = await testDb.tasks.get(taskId);
    expect(currentLocal.title).toBe('Device A Title');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 2: Local update versus remote deletion
  // -------------------------------------------------------------------------
  it('2. Detects local update versus remote deletion conflict and safeguards data', async () => {
    const testDb = await createIsolatedDb('scenario2');
    const taskId = 'task-upd-del-102';
    const userId = 'user_conflict_1';

    // Base setup
    await testDb.tasks.put({ id: taskId, userId, title: 'Original Task', version: 1, isDeleted: 0 });

    // Local device modified task
    await taskRepository.update(
      taskId,
      { title: 'Crucial Assignment', priority: 'Urgent', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    // Remote change arrives: DELETE operation
    const remoteChange = {
      id: 202,
      operation_uuid: 'op-remote-delete',
      device_uuid: 'device-remote-delete',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'DELETE',
      entity_version: 2,
      payload: { id: taskId },
    };

    const evalResult = await conflictDetector.detectConflict({
      change: remoteChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);
    expect(evalResult.reason).toBe('UPDATE_VS_DELETE');

    const conflict = await conflictDetector.recordConflict({
      change: remoteChange,
      conflictEvaluation: evalResult,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(conflict.remoteOperation).toBe('DELETE');
    expect(conflict.localOperation).toBe('UPDATE');

    // Verify task is still present locally
    const localTask = await testDb.tasks.get(taskId);
    expect(localTask.isDeleted).toBe(0);
    expect(localTask.title).toBe('Crucial Assignment');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 3: Local deletion versus remote update
  // -------------------------------------------------------------------------
  it('3. Detects local deletion versus remote update and preserves conflict record', async () => {
    const testDb = await createIsolatedDb('scenario3');
    const taskId = 'task-del-upd-103';
    const userId = 'user_conflict_1';

    // Local device soft-deleted the task
    await testDb.tasks.put({
      id: taskId,
      userId,
      title: 'Old Task',
      isDeleted: 1,
      version: 2,
    });
    await syncQueue.enqueue(
      {
        entityType: 'task',
        entityId: taskId,
        operation: SYNC_OPERATIONS.DELETE,
        entityVersion: 2,
        payload: { id: taskId, isDeleted: 1 },
        userId,
        deviceUuid: 'local-dev',
      },
      testDb
    );

    // Remote change arrives: UPDATE operation
    const remoteChange = {
      id: 203,
      operation_uuid: 'op-remote-update',
      device_uuid: 'device-remote-editor',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Updated Remotely', priority: 'High' },
    };

    const evalResult = await conflictDetector.detectConflict({
      change: remoteChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);
    expect(evalResult.reason).toBe('UPDATE_VS_DELETE');

    const conflict = await conflictDetector.recordConflict({
      change: remoteChange,
      conflictEvaluation: evalResult,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(conflict.localOperation).toBe('DELETE');
    expect(conflict.remoteOperation).toBe('UPDATE');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 4: Simultaneous goal modifications
  // -------------------------------------------------------------------------
  it('4. Detects simultaneous goal modifications across offline devices', async () => {
    const testDb = await createIsolatedDb('scenario4');
    const goalId = 'goal-concurrent-104';
    const userId = 'user_conflict_1';

    // Local device updates goal progress
    await goalRepository.save(
      { id: goalId, title: 'Master Machine Learning', progressPercentage: 80, version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    // Remote device also updated goal target date and title
    const remoteGoalChange = {
      id: 204,
      operation_uuid: 'op-goal-remote',
      device_uuid: 'device-b-goal',
      entity_type: 'goal',
      entity_id: goalId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: {
        id: goalId,
        title: 'Master ML & AI Systems',
        progressPercentage: 65,
        targetDate: '2026-12-31',
      },
    };

    const evalResult = await conflictDetector.detectConflict({
      change: remoteGoalChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);

    const conflict = await conflictDetector.recordConflict({
      change: remoteGoalChange,
      conflictEvaluation: evalResult,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(conflict.entityType).toBe('goal');
    expect(conflict.localData.progress || conflict.localData.progressPercentage).toBe(80);
    expect(conflict.remoteData.progress || conflict.remoteData.progressPercentage).toBe(65);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 5: Conflicting habit changes
  // -------------------------------------------------------------------------
  it('5. Detects conflicting habit changes and preserves both versions', async () => {
    const testDb = await createIsolatedDb('scenario5');
    const habitId = 'habit-conflict-105';
    const userId = 'user_conflict_1';

    await habitRepository.save(
      { id: habitId, name: 'Morning Meditation (20m)', baseStreak: 12, version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    const remoteHabitChange = {
      id: 205,
      operation_uuid: 'op-habit-remote',
      device_uuid: 'device-phone',
      entity_type: 'habit',
      entity_id: habitId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: habitId, name: 'Mindfulness Meditation', baseStreak: 15 },
    };

    const evalResult = await conflictDetector.detectConflict({
      change: remoteHabitChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);
    const conflict = await conflictDetector.recordConflict({
      change: remoteHabitChange,
      conflictEvaluation: evalResult,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(conflict.entityType).toBe('habit');
    expect(conflict.localData.name).toBe('Morning Meditation (20m)');
    expect(conflict.remoteData.name).toBe('Mindfulness Meditation');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 6: Duplicate operation delivery (Idempotency)
  // -------------------------------------------------------------------------
  it('6. Handles duplicate operation delivery idempotently without creating redundant conflicts', async () => {
    const testDb = await createIsolatedDb('scenario6');
    const taskId = 'task-idemp-106';
    const userId = 'user_conflict_1';

    await taskRepository.save(
      { id: taskId, title: 'Local Task', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    const remoteChange = {
      id: 206,
      operation_uuid: 'op-duplicate-uuid',
      device_uuid: 'device-b',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Remote Task' },
    };

    const eval1 = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const c1 = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: eval1, targetDb: testDb, activeUserId: userId });

    // Second delivery of identical change
    const eval2 = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const c2 = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: eval2, targetDb: testDb, activeUserId: userId });

    // Must reuse the exact same conflict ID and maintain count = 1
    expect(c2.id).toBe(c1.id);
    const allConflicts = await testDb.conflicts.where('userId').equals(userId).toArray();
    expect(allConflicts.length).toBe(1);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 7: Stale entity versions
  // -------------------------------------------------------------------------
  it('7. Detects stale remote entity versions arriving against locally upgraded entities', async () => {
    const testDb = await createIsolatedDb('scenario7');
    const taskId = 'task-stale-107';
    const userId = 'user_conflict_1';

    // Local entity is already at version 5
    await testDb.tasks.put({
      id: taskId,
      userId,
      title: 'Advanced v5 Task',
      version: 5,
      updatedAt: '2026-11-22T12:00:00.000Z',
    });

    // Stale change arrives with version 3
    const staleChange = {
      id: 207,
      operation_uuid: 'op-stale-v3',
      device_uuid: 'device-slow',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 3,
      payload: { id: taskId, title: 'Old v3 Title' },
    };

    const evalResult = await conflictDetector.detectConflict({
      change: staleChange,
      targetDb: testDb,
      activeUserId: userId,
    });

    expect(evalResult.hasConflict).toBe(true);
    expect(evalResult.reason).toBe('STALE_REMOTE_VERSION');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 8: Manual merge resolution strategy
  // -------------------------------------------------------------------------
  it('8. Successfully applies Manual Merge combining fields from local and remote', async () => {
    const testDb = await createIsolatedDb('scenario8');
    const taskId = 'task-merge-108';
    const userId = 'user_conflict_1';

    await taskRepository.save(
      { id: taskId, title: 'Complete ML Assignment', priority: 'High', dueDate: '2026-11-25', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    const remoteChange = {
      id: 208,
      operation_uuid: 'op-merge-remote',
      device_uuid: 'device-remote',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Complete ML Assignment', priority: 'Low', dueDate: '2026-11-27' },
    };

    const evalResult = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const conflict = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: evalResult, targetDb: testDb, activeUserId: userId });

    // User chooses local priority (High) and remote due date (2026-11-27)
    const mergedData = entityMergeHelpers.mergeTasks(conflict.localData, conflict.remoteData, {
      priority: 'High',
      dueDate: '2026-11-27',
    });

    const resolutionResult = await conflictResolver.resolveConflict({
      conflictId: conflict.id,
      strategy: RESOLUTION_STRATEGY.MANUAL_MERGE,
      mergedData,
      userId,
      targetDb: testDb,
    });

    expect(resolutionResult.success).toBe(true);
    expect(resolutionResult.status).toBe(CONFLICT_STATUS.RESOLVED_MERGED);
    expect(resolutionResult.winningVersion).toBe(3); // Math.max(2, 2) + 1

    // Verify local task state
    const savedTask = await testDb.tasks.get(taskId);
    expect(savedTask.priority).toBe('High');
    expect(savedTask.dueDate).toBe('2026-11-27');
    expect(savedTask.version).toBe(3);

    // Verify outgoing sync queue has the merged update with bumped version 3
    const queueItems = await testDb.syncQueue
      .where('[userId+entityType+entityId]')
      .equals([userId, 'task', taskId])
      .filter((item) => item.status === SYNC_STATUS.PENDING)
      .toArray();

    expect(queueItems.length).toBe(1);
    expect(queueItems[0].entityVersion).toBe(3);
    expect(queueItems[0].payload.dueDate).toBe('2026-11-27');
  });

  // -------------------------------------------------------------------------
  // SCENARIO 9: Keep Local resolution strategy
  // -------------------------------------------------------------------------
  it('9. Successfully applies Keep Local preserving local edits and queueing bumped version', async () => {
    const testDb = await createIsolatedDb('scenario9');
    const taskId = 'task-local-109';
    const userId = 'user_conflict_1';

    await taskRepository.save(
      { id: taskId, title: 'Local Winner Title', priority: 'Urgent', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    const remoteChange = {
      id: 209,
      operation_uuid: 'op-remote-loser',
      device_uuid: 'device-b',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Remote Loser Title', priority: 'Low' },
    };

    const evalResult = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const conflict = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: evalResult, targetDb: testDb, activeUserId: userId });

    const resolutionResult = await conflictResolver.resolveConflict({
      conflictId: conflict.id,
      strategy: RESOLUTION_STRATEGY.KEEP_LOCAL,
      userId,
      targetDb: testDb,
    });

    expect(resolutionResult.status).toBe(CONFLICT_STATUS.RESOLVED_LOCAL);
    expect(resolutionResult.winningVersion).toBe(3);

    const task = await testDb.tasks.get(taskId);
    expect(task.title).toBe('Local Winner Title');
    expect(task.version).toBe(3);

    // Pending operation was bumped to version 3 so remote devices adopt it
    const pending = await testDb.syncQueue
      .where('[userId+entityType+entityId]')
      .equals([userId, 'task', taskId])
      .filter((item) => item.status === SYNC_STATUS.PENDING)
      .toArray();

    expect(pending[0].entityVersion).toBe(3);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 10: Keep Remote resolution strategy
  // -------------------------------------------------------------------------
  it('10. Successfully applies Keep Remote adopting remote data and superseding local pending ops', async () => {
    const testDb = await createIsolatedDb('scenario10');
    const taskId = 'task-remote-110';
    const userId = 'user_conflict_1';

    await taskRepository.save(
      { id: taskId, title: 'Discarded Local Title', version: 2 },
      userId,
      { trackChange: true },
      testDb
    );

    const remoteChange = {
      id: 210,
      operation_uuid: 'op-remote-winner',
      device_uuid: 'device-b',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Accepted Remote Title', priority: 'High' },
    };

    const evalResult = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const conflict = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: evalResult, targetDb: testDb, activeUserId: userId });

    const resolutionResult = await conflictResolver.resolveConflict({
      conflictId: conflict.id,
      strategy: RESOLUTION_STRATEGY.KEEP_REMOTE,
      userId,
      targetDb: testDb,
    });

    expect(resolutionResult.status).toBe(CONFLICT_STATUS.RESOLVED_REMOTE);

    // Local record replaced with remote payload
    const task = await testDb.tasks.get(taskId);
    expect(task.title).toBe('Accepted Remote Title');
    expect(task.priority).toBe('High');

    // Local pending operations superseded so they will NOT push to overwrite server
    const pending = await testDb.syncQueue
      .where('[userId+entityType+entityId]')
      .equals([userId, 'task', taskId])
      .filter((item) => item.status === SYNC_STATUS.PENDING)
      .toArray();

    expect(pending.length).toBe(0);

    const superseded = await testDb.syncQueue
      .where('[userId+entityType+entityId]')
      .equals([userId, 'task', taskId])
      .filter((item) => item.status === SYNC_STATUS.SUPERSEDED)
      .toArray();

    expect(superseded.length).toBe(1);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 11: Account isolation enforcement
  // -------------------------------------------------------------------------
  it('11. Enforces strict account isolation preventing User B from resolving User A conflicts', async () => {
    const testDb = await createIsolatedDb('scenario11');
    const userA = 'user_alpha';
    const userB = 'user_bravo';

    // Conflict created by User A
    const conflict = {
      id: 'conflict-user-a-111',
      userId: userA,
      entityType: 'task',
      entityId: 't-111',
      status: CONFLICT_STATUS.PENDING_RESOLUTION,
      localVersion: 2,
      remoteVersion: 2,
      localData: { title: 'User A Task' },
      remoteData: { title: 'Remote Task' },
      detectedAt: new Date().toISOString(),
    };
    await testDb.conflicts.put(conflict);

    // User B attempts to resolve User A's conflict
    await expect(
      conflictResolver.resolveConflict({
        conflictId: conflict.id,
        strategy: RESOLUTION_STRATEGY.KEEP_LOCAL,
        userId: userB,
        targetDb: testDb,
      })
    ).rejects.toThrow(/Conflict does not belong to active user/);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 12: Device revocation handling
  // -------------------------------------------------------------------------
  it('12. Prevents synchronization operations when device is revoked', async () => {
    const mockRevokedService = {
      async pushSync() {
        const err = new Error('Device access has been revoked.');
        err.status = 403;
        throw err;
      },
    };

    const res = await syncManager.pushChanges({
      clientService: mockRevokedService,
      targetDb: db,
    });

    expect(res.status).toBe('completed');
    expect(res.pushed).toBe(0);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 13: Interrupted conflict resolution & recovery
  // -------------------------------------------------------------------------
  it('13. Preserves PENDING_RESOLUTION state if resolution is interrupted prior to commit', async () => {
    const testDb = await createIsolatedDb('scenario13');
    const conflictId = 'conflict-interrupted-113';
    const userId = 'user_conflict_1';

    await testDb.conflicts.put({
      id: conflictId,
      userId,
      entityType: 'task',
      entityId: 'task-113',
      status: CONFLICT_STATUS.PENDING_RESOLUTION,
      localVersion: 2,
      remoteVersion: 2,
      localData: { title: 'Local' },
      remoteData: { title: 'Remote' },
      detectedAt: new Date().toISOString(),
      resolvedAt: null,
    });

    // Incomplete resolution with invalid strategy throws and leaves conflict untouched
    await expect(
      conflictResolver.resolveConflict({
        conflictId,
        strategy: 'NON_EXISTENT_STRATEGY',
        userId,
        targetDb: testDb,
      })
    ).rejects.toThrow();

    const record = await testDb.conflicts.get(conflictId);
    expect(record.status).toBe(CONFLICT_STATUS.PENDING_RESOLUTION);
    expect(record.resolvedAt).toBeNull();
  });

  // -------------------------------------------------------------------------
  // SCENARIO 14: Conflict propagation to a third device
  // -------------------------------------------------------------------------
  it('14. Propagates resolved conflict winner cleanly to a third device', async () => {
    // Shared simulated cloud
    const cloud = {
      sequence: 0,
      operations: [],
    };

    const makeClient = (deviceUuid) => ({
      async pushSync(batch) {
        for (const item of batch) {
          cloud.sequence++;
          cloud.operations.push({
            id: cloud.sequence,
            operation_uuid: item.operationId,
            device_uuid: deviceUuid,
            entity_type: item.entityType,
            entity_id: item.entityId,
            operation_type: item.operation,
            entity_version: item.entityVersion,
            payload: item.payload,
          });
        }
        return {
          applied: batch.length,
          rejected: 0,
          results: batch.map((b) => ({ operation_uuid: b.operationId, status: 'APPLIED', server_version: b.entityVersion })),
        };
      },
      async pullSync(cursor, limit, excludeSelf) {
        let ops = cloud.operations.filter((op) => op.id > cursor);
        if (excludeSelf) ops = ops.filter((op) => op.device_uuid !== deviceUuid);
        const page = ops.slice(0, limit);
        return {
          changes: page,
          next_cursor: page.length ? page[page.length - 1].id : cursor,
          has_more: false,
        };
      },
      async acknowledgeSync() {
        return { acknowledged: true };
      },
    });

    const dbA = await createIsolatedDb('devA');
    const dbB = await createIsolatedDb('devB');
    const dbC = await createIsolatedDb('devC');

    const clientA = makeClient('devA');
    const clientB = makeClient('devB');
    const clientC = makeClient('devC');

    const taskId = 'task-propagate-114';
    const userId = 'user_conflict_1';

    // Device A resolves conflict using Manual Merge
    const mergedPayload = { id: taskId, title: 'Triple Device Consensus', priority: 'High', version: 3 };
    await dbA.tasks.put(mergedPayload);
    await syncQueue.enqueue({
      entityType: 'task',
      entityId: taskId,
      operation: SYNC_OPERATIONS.UPDATE,
      entityVersion: 3,
      payload: mergedPayload,
      userId,
      deviceUuid: 'devA',
    }, dbA);

    // Device A pushes resolved winner
    await syncManager.pushChanges({ clientService: clientA, targetDb: dbA });
    expect(cloud.operations.length).toBe(1);

    // Device C pulls updates from cloud
    const pullResC = await syncManager.pullChanges({ clientService: clientC, targetDb: dbC });
    expect(pullResC.pulled).toBe(1);

    // Device C has the clean consensus version without any local conflict
    const taskOnC = await dbC.tasks.get(taskId);
    expect(taskOnC.title).toBe('Triple Device Consensus');
    expect(taskOnC.version).toBe(3);

    const conflictsOnC = await dbC.conflicts.where('userId').equals(userId).toArray();
    expect(conflictsOnC.length).toBe(0);
  });

  // -------------------------------------------------------------------------
  // SCENARIO 15: Restart recovery
  // -------------------------------------------------------------------------
  it('15. Recovers conflict state and pending queues cleanly after database restart', async () => {
    const dbName = `test_restart_${Date.now()}`;
    const testDb1 = new NiyantraDatabase({ name: dbName });
    await testDb1.open();

    const userId = 'user_conflict_1';
    const conflictId = 'conflict-restart-115';

    await testDb1.conflicts.put({
      id: conflictId,
      userId,
      entityType: 'task',
      entityId: 'task-115',
      status: CONFLICT_STATUS.PENDING_RESOLUTION,
      localVersion: 2,
      remoteVersion: 2,
      localData: { title: 'Local Task' },
      remoteData: { title: 'Remote Task' },
      detectedAt: new Date().toISOString(),
    });

    testDb1.close();

    // Reopen database instance simulating app restart
    const testDb2 = new NiyantraDatabase({ name: dbName });
    await testDb2.open();

    const recovered = await testDb2.conflicts.get(conflictId);
    expect(recovered).toBeDefined();
    expect(recovered.status).toBe(CONFLICT_STATUS.PENDING_RESOLUTION);
    expect(recovered.localData.title).toBe('Local Task');

    testDb2.close();
  });

  // -------------------------------------------------------------------------
  // SCENARIO 16: Historical conflict preservation
  // -------------------------------------------------------------------------
  it('16. Preserves resolved conflict history with strategies, timestamps, and resolved data', async () => {
    const testDb = await createIsolatedDb('scenario16');
    const userId = 'user_conflict_1';
    const taskId = 'task-hist-116';

    await testDb.tasks.put({ id: taskId, userId, title: 'Title A', version: 2 });
    await syncQueue.enqueue({
      entityType: 'task',
      entityId: taskId,
      operation: SYNC_OPERATIONS.UPDATE,
      entityVersion: 2,
      payload: { id: taskId, title: 'Title A' },
      userId,
      deviceUuid: 'local-dev',
    }, testDb);

    const remoteChange = {
      id: 216,
      operation_uuid: 'op-hist-remote',
      device_uuid: 'remote-dev',
      entity_type: 'task',
      entity_id: taskId,
      operation_type: 'UPDATE',
      entity_version: 2,
      payload: { id: taskId, title: 'Title B' },
    };

    const evalRes = await conflictDetector.detectConflict({ change: remoteChange, targetDb: testDb, activeUserId: userId });
    const conflict = await conflictDetector.recordConflict({ change: remoteChange, conflictEvaluation: evalRes, targetDb: testDb, activeUserId: userId });

    await conflictResolver.resolveConflict({
      conflictId: conflict.id,
      strategy: RESOLUTION_STRATEGY.KEEP_LOCAL,
      userId,
      targetDb: testDb,
    });

    // Check conflict history query
    const history = await conflictDetector.getConflictHistory(userId, testDb);
    expect(history.length).toBe(1);
    expect(history[0].id).toBe(conflict.id);
    expect(history[0].status).toBe(CONFLICT_STATUS.RESOLVED_LOCAL);
    expect(history[0].resolutionStrategy).toBe(RESOLUTION_STRATEGY.KEEP_LOCAL);
    expect(history[0].resolvedAt).toBeDefined();
    expect(history[0].resolvedData.title).toBe('Title A');

    // Unresolved count must be 0
    const count = await conflictDetector.getUnresolvedConflictCount(userId, testDb);
    expect(count).toBe(0);
  });
});
