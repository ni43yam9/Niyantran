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
import { timeblockRepository } from '../src/database/repositories/timeblockRepository';
import { dailyIntentRepository } from '../src/database/repositories/dailyIntentRepository';
import { syncManager } from '../src/sync/syncManager';
import { syncQueue } from '../src/sync/syncQueue';
import {
  SYNC_OPERATIONS,
  SYNC_STATUS,
  SYNC_META_KEYS,
  ENTITY_TYPES,
} from '../src/sync/syncConstants';

describe('Phase 10G: Multi-Device Push/Pull Synchronization Engine', () => {
  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('niyantra_access_token', 'mock_valid_jwt_token_device_test');
    localStorage.setItem('niyantra_user', JSON.stringify({ id: 'user_sync_test', name: 'Sync User' }));

    if (!db.isOpen()) {
      await db.open();
    }
    await db.tasks.clear();
    await db.goals.clear();
    await db.habits.clear();
    await db.habitLogs.clear();
    await db.dailyTimeblocks.clear();
    await db.dailyIntents.clear();
    await db.recommendations.clear();
    await db.activityLogs.clear();
    await db.syncMeta.clear();
    await db.syncQueue.clear();
  });

  afterEach(async () => {
    vi.restoreAllMocks();
  });

  // -------------------------------------------------------------------------
  // 1. PUSH SYNCHRONIZATION TESTS
  // -------------------------------------------------------------------------
  describe('1. Push Synchronization', () => {
    it('pushes a single newly created task to the cloud backend', async () => {
      // 1. Create a task locally (enqueues CREATE in syncQueue)
      const task = await taskRepository.createTask({
        title: 'Push Task 1',
        category: 'Coding',
        priority: 'High',
      });

      const pendingBefore = await syncQueue.getPendingCount();
      expect(pendingBefore).toBe(1);

      // 2. Mock cloud service
      let pushedPayload = null;
      const mockService = {
        async pushSync(batch, deviceUuid) {
          pushedPayload = { batch, deviceUuid };
          return {
            applied: 1,
            rejected: 0,
            results: [
              {
                operation_uuid: batch[0].operationId,
                status: 'APPLIED',
                entity_type: 'task',
                entity_id: batch[0].entityId,
                server_version: 1,
                message: 'Applied successfully',
              },
            ],
            server_timestamp: new Date().toISOString(),
          };
        },
      };

      // 3. Execute pushChanges
      const pushRes = await syncManager.pushChanges({ clientService: mockService });
      expect(pushRes.pushed).toBe(1);
      expect(pushRes.rejected).toBe(0);
      expect(pushRes.status).toBe('completed');

      // Verify payload sent
      expect(pushedPayload.batch).toHaveLength(1);
      expect(pushedPayload.batch[0].entityType).toBe('task');
      expect(pushedPayload.batch[0].entityId).toBe(task.id);
      expect(pushedPayload.batch[0].operation).toBe(SYNC_OPERATIONS.CREATE);

      // Verify local queue item marked COMPLETED (never removed prematurely)
      const queueItem = await syncQueue.getByOperationId(pushedPayload.batch[0].operationId);
      expect(queueItem).toBeDefined();
      expect(queueItem.status).toBe(SYNC_STATUS.COMPLETED);

      const pendingAfter = await syncQueue.getPendingCount();
      expect(pendingAfter).toBe(0);
    });

    it('pushes multiple entity types in a single batch', async () => {
      await taskRepository.createTask({ title: 'Task Multi' });
      await goalRepository.createGoal({ title: 'Goal Multi', targetDate: '2026-12-31' });
      await habitRepository.createHabit({ name: 'Habit Multi' });
      await dailyIntentRepository.save('2026-11-22', 'Intent Multi');

      expect(await syncQueue.getPendingCount()).toBe(4);

      const mockService = {
        async pushSync(batch) {
          return {
            applied: batch.length,
            rejected: 0,
            results: batch.map((item) => ({
              operation_uuid: item.operationId,
              status: 'APPLIED',
              entity_type: item.entityType,
              entity_id: item.entityId,
              server_version: 1,
            })),
            server_timestamp: new Date().toISOString(),
          };
        },
      };

      const res = await syncManager.pushChanges({ clientService: mockService });
      expect(res.pushed).toBe(4);
      expect(await syncQueue.getPendingCount()).toBe(0);
    });

    it('handles partial batch failure safely without dropping pending items', async () => {
      await taskRepository.createTask({ title: 'Task Success' });
      await taskRepository.createTask({ title: 'Task Failed' });

      const mockService = {
        async pushSync(batch) {
          return {
            applied: 1,
            rejected: 1,
            results: [
              {
                operation_uuid: batch[0].operationId,
                status: 'APPLIED',
                entity_type: 'task',
                entity_id: batch[0].entityId,
                server_version: 1,
              },
              {
                operation_uuid: batch[1].operationId,
                status: 'REJECTED',
                entity_type: 'task',
                entity_id: batch[1].entityId,
                server_version: 1,
                message: 'Temporary conflict rejection',
              },
            ],
            server_timestamp: new Date().toISOString(),
          };
        },
      };

      const res = await syncManager.pushChanges({ clientService: mockService });
      expect(res.pushed).toBe(1);
      expect(res.rejected).toBe(1);

      // Verify the first item is COMPLETED and the second is FAILED with backoff
      const allQueue = await syncQueue.getAll();
      const successItem = allQueue.find((i) => i.payload.title === 'Task Success');
      const failedItem = allQueue.find((i) => i.payload.title === 'Task Failed');

      expect(successItem.status).toBe(SYNC_STATUS.COMPLETED);
      expect(failedItem.status).toBe(SYNC_STATUS.FAILED);
      expect(failedItem.retryCount).toBe(1);
      expect(failedItem.nextRetryAt).toBeDefined();
    });

    it('preserves pending operations in queue upon network failure', async () => {
      await taskRepository.createTask({ title: 'Offline Task' });

      const failingService = {
        async pushSync() {
          throw new Error('Failed to fetch (Network offline)');
        },
      };

      const res = await syncManager.pushChanges({ clientService: failingService });
      expect(res.status).toBe('error');
      expect(res.pushed).toBe(0);

      // Verify operation is marked FAILED with retry, NOT deleted
      const allQueue = await syncQueue.getAll();
      expect(allQueue).toHaveLength(1);
      expect(allQueue[0].status).toBe(SYNC_STATUS.FAILED);
      expect(allQueue[0].retryCount).toBe(1);
      expect(allQueue[0].nextRetryAt).toBeDefined();
    });

    it('preserves the original operationId across retry submissions', async () => {
      await taskRepository.createTask({ title: 'Retry Task' });
      const initialItem = (await syncQueue.getAll())[0];
      const originalOpId = initialItem.operationId;

      // Fail once
      await syncManager.pushChanges({
        clientService: {
          async pushSync() {
            throw new Error('500 Internal Server Error');
          },
        },
      });

      // Reset to pending for retry
      await syncQueue.resetFailed(initialItem.id);

      // Capture second push invocation
      let retriedOpId = null;
      await syncManager.pushChanges({
        clientService: {
          async pushSync(batch) {
            retriedOpId = batch[0].operationId;
            return {
              applied: 1,
              rejected: 0,
              results: [{ operation_uuid: retriedOpId, status: 'APPLIED', entity_type: 'task', entity_id: '1' }],
            };
          },
        },
      });

      expect(retriedOpId).toBe(originalOpId);
    });
  });

  // -------------------------------------------------------------------------
  // 2. PULL SYNCHRONIZATION TESTS
  // -------------------------------------------------------------------------
  describe('2. Pull Synchronization', () => {
    it('downloads remote task creation into IndexedDB', async () => {
      const mockService = {
        async pullSync(cursor) {
          return {
            changes: [
              {
                id: 1,
                operation_uuid: 'remote-op-1',
                device_uuid: 'other-device-uuid',
                entity_type: 'task',
                entity_id: 'tsk_remote_101',
                operation_type: 'CREATE',
                entity_version: 1,
                payload: {
                  title: 'Remote Cloud Task',
                  category: 'Career',
                  priority: 'High',
                  status: 'In Progress',
                  dueDate: '2026-11-25',
                },
                received_at: new Date().toISOString(),
              },
            ],
            next_cursor: 1,
            has_more: false,
            server_timestamp: new Date().toISOString(),
          };
        },
        async acknowledgeSync() {
          return { acknowledged: true };
        },
      };

      const pullRes = await syncManager.pullChanges({ clientService: mockService });
      expect(pullRes.pulled).toBe(1);
      expect(pullRes.nextCursor).toBe(1);

      // Verify task exists in IndexedDB
      const task = await taskRepository.getById('tsk_remote_101');
      expect(task).toBeDefined();
      expect(task.title).toBe('Remote Cloud Task');
      expect(task.category).toBe('Career');
      expect(task.priority).toBe('High');
      expect(task.status).toBe('In Progress');

      // CRITICAL: Pull must NOT generate outgoing sync queue entries!
      const pending = await syncQueue.getPendingCount();
      expect(pending).toBe(0);
    });

    it('downloads remote task updates and applies them locally', async () => {
      // Create task locally first with trackChange: false (as if already synced)
      await taskRepository.save(
        { id: 'tsk_to_update', title: 'Local Version', priority: 'Low', version: 1 },
        null,
        { trackChange: false }
      );

      const mockService = {
        async pullSync() {
          return {
            changes: [
              {
                id: 2,
                operation_uuid: 'remote-op-2',
                device_uuid: 'other-device',
                entity_type: 'task',
                entity_id: 'tsk_to_update',
                operation_type: 'UPDATE',
                entity_version: 2,
                payload: {
                  title: 'Remotely Updated Title',
                  priority: 'High',
                },
              },
            ],
            next_cursor: 2,
            has_more: false,
          };
        },
        async acknowledgeSync() {
          return { acknowledged: true };
        },
      };

      await syncManager.pullChanges({ clientService: mockService });
      const updated = await taskRepository.getById('tsk_to_update');
      expect(updated.title).toBe('Remotely Updated Title');
      expect(updated.priority).toBe('High');
      expect(updated.version).toBe(2);

      // Zero outgoing queue operations generated
      expect(await syncQueue.getPendingCount()).toBe(0);
    });

    it('downloads remote deletion and applies tombstone locally', async () => {
      await taskRepository.save(
        { id: 'tsk_to_delete', title: 'To Be Deleted', version: 1 },
        null,
        { trackChange: false }
      );

      const mockService = {
        async pullSync() {
          return {
            changes: [
              {
                id: 3,
                operation_uuid: 'remote-op-3',
                device_uuid: 'other-device',
                entity_type: 'task',
                entity_id: 'tsk_to_delete',
                operation_type: 'DELETE',
                entity_version: 2,
                payload: {},
              },
            ],
            next_cursor: 3,
            has_more: false,
          };
        },
        async acknowledgeSync() {
          return { acknowledged: true };
        },
      };

      await syncManager.pullChanges({ clientService: mockService });

      // In repository getAll, soft-deleted task is excluded
      const allActive = await taskRepository.getAll();
      expect(allActive.find((t) => t.id === 'tsk_to_delete')).toBeUndefined();

      // In direct table query, soft-deletion tombstone is preserved
      const direct = await db.tasks.get('tsk_to_delete');
      expect(direct.isDeleted).toBe(1);
      expect(direct.deletedAt).toBeDefined();

      // Zero outgoing queue operations generated
      expect(await syncQueue.getPendingCount()).toBe(0);
    });

    it('processes multi-page pull pagination and advances cursor accurately', async () => {
      let callCount = 0;
      const acknowledgedCursors = [];

      const mockService = {
        async pullSync(cursor) {
          callCount++;
          if (cursor === 0) {
            return {
              changes: [
                {
                  id: 10,
                  operation_uuid: 'p1',
                  device_uuid: 'dev-b',
                  entity_type: 'task',
                  entity_id: 'tsk_page_1',
                  operation_type: 'CREATE',
                  entity_version: 1,
                  payload: { title: 'Page 1 Task' },
                },
              ],
              next_cursor: 10,
              has_more: true, // Indicates more pages exist
            };
          } else if (cursor === 10) {
            return {
              changes: [
                {
                  id: 20,
                  operation_uuid: 'p2',
                  device_uuid: 'dev-b',
                  entity_type: 'task',
                  entity_id: 'tsk_page_2',
                  operation_type: 'CREATE',
                  entity_version: 1,
                  payload: { title: 'Page 2 Task' },
                },
              ],
              next_cursor: 20,
              has_more: false, // End of pagination
            };
          }
          return { changes: [], next_cursor: cursor, has_more: false };
        },
        async acknowledgeSync(cursor) {
          acknowledgedCursors.push(cursor);
          return { acknowledged: true };
        },
      };

      const res = await syncManager.pullChanges({ clientService: mockService });
      expect(callCount).toBe(2);
      expect(res.pulled).toBe(2);
      expect(res.nextCursor).toBe(20);
      expect(acknowledgedCursors).toEqual([10, 20]);

      // Check stored cursor in sync_meta
      const savedCursor = await syncManager.getCursor();
      expect(savedCursor).toBe(20);
    });
  });

  // -------------------------------------------------------------------------
  // 3. MULTI-DEVICE SIMULATION & CONFLICT SAFETY TESTS
  // -------------------------------------------------------------------------
  describe('3. Multi-Device Simulation & Conflict Safety', () => {
    it('simulates cross-device synchronization exchange between Device A and Device B', async () => {
      // In-memory server cloud mock
      const cloudServer = {
        sequenceClock: 0,
        operations: [],
      };

      const makeServerClient = (deviceUuid) => ({
        async pushSync(batch) {
          const results = [];
          for (const item of batch) {
            cloudServer.sequenceClock++;
            const seqId = cloudServer.sequenceClock;
            cloudServer.operations.push({
              id: seqId,
              operation_uuid: item.operationId,
              device_uuid: deviceUuid,
              entity_type: item.entityType,
              entity_id: item.entityId,
              operation_type: item.operation,
              entity_version: item.entityVersion,
              payload: item.payload,
            });
            results.push({
              operation_uuid: item.operationId,
              status: 'APPLIED',
              entity_type: item.entityType,
              entity_id: item.entityId,
              server_version: item.entityVersion,
            });
          }
          return {
            applied: batch.length,
            rejected: 0,
            results,
            server_timestamp: new Date().toISOString(),
          };
        },
        async pullSync(cursor, limit, excludeSelf) {
          let ops = cloudServer.operations.filter((op) => op.id > cursor);
          if (excludeSelf) {
            ops = ops.filter((op) => op.device_uuid !== deviceUuid);
          }
          const page = ops.slice(0, limit);
          const nextCursor = page.length ? page[page.length - 1].id : cursor;
          return {
            changes: page,
            next_cursor: nextCursor,
            has_more: ops.length > limit,
          };
        },
        async acknowledgeSync() {
          return { acknowledged: true };
        },
      });

      // --- DEVICE A ---
      const dbA = db; // Primary db instance acts as Device A
      const clientA = makeServerClient('device_alpha_uuid');

      // Device A creates a new task
      const taskA = await taskRepository.createTask(
        { title: 'Cross-Device Shared Task', category: 'Coding', priority: 'Medium' },
        null,
        dbA
      );
      expect(await syncQueue.getPendingCount(null, dbA)).toBe(1);

      // Device A pushes to cloud
      const pushResA = await syncManager.pushChanges({ targetDb: dbA, clientService: clientA });
      expect(pushResA.pushed).toBe(1);
      expect(await syncQueue.getPendingCount(null, dbA)).toBe(0);
      expect(cloudServer.operations).toHaveLength(1);

      // --- DEVICE B ---
      // Spin up separate Dexie instance simulating Device B on phone
      const dbB = new NiyantraDatabase({ name: 'niyantra_device_b_db' });
      await dbB.open();
      const clientB = makeServerClient('device_beta_uuid');

      // Device B pulls changes from cloud
      const pullResB = await syncManager.pullChanges({ targetDb: dbB, clientService: clientB });
      expect(pullResB.pulled).toBe(1);

      // Verify task arrived on Device B
      const taskOnB = await taskRepository.getById(taskA.id, null, dbB);
      expect(taskOnB).toBeDefined();
      expect(taskOnB.title).toBe('Cross-Device Shared Task');

      // Device B updates the task on their phone
      await taskRepository.update(
        taskA.id,
        { status: 'Completed', priority: 'High' },
        null,
        { trackChange: true },
        dbB
      );
      expect(await syncQueue.getPendingCount(null, dbB)).toBe(1);

      // Device B pushes update to cloud
      const pushResB = await syncManager.pushChanges({ targetDb: dbB, clientService: clientB });
      expect(pushResB.pushed).toBe(1);
      expect(cloudServer.operations).toHaveLength(2);

      // --- DEVICE A PULLS UPDATE ---
      const pullResA = await syncManager.pullChanges({ targetDb: dbA, clientService: clientA });
      expect(pullResA.pulled).toBe(1);

      // Verify Device A reflects Device B's changes
      const updatedOnA = await taskRepository.getById(taskA.id, null, dbA);
      expect(updatedOnA.status).toBe('Completed');
      expect(updatedOnA.priority).toBe('High');

      // Clean up Device B
      dbB.close();
    });

    it('protects local unpushed edits from being overwritten by remote changes (conflict safety)', async () => {
      // 1. Local user makes an edit to Task 1 while offline (enqueued in syncQueue)
      const localTask = await taskRepository.createTask({
        title: 'Local Important Edit (Unsynced)',
        status: 'In Progress',
      });

      expect(await syncQueue.getPendingCount()).toBe(1);

      // 2. Incoming remote update targets the exact same task
      const mockService = {
        async pullSync() {
          return {
            changes: [
              {
                id: 100,
                operation_uuid: 'conflicting-remote-op',
                device_uuid: 'other-device',
                entity_type: 'task',
                entity_id: localTask.id,
                operation_type: 'UPDATE',
                entity_version: 5,
                payload: {
                  title: 'Remote Overwriting Edit',
                  status: 'Completed',
                },
              },
            ],
            next_cursor: 100,
            has_more: false,
          };
        },
        async acknowledgeSync() {
          return { acknowledged: true };
        },
      };

      // 3. Execute pull
      await syncManager.pullChanges({ clientService: mockService });

      // 4. Verify conflict safety: Local unpushed edits MUST NOT be silently replaced!
      const currentTask = await taskRepository.getById(localTask.id);
      expect(currentTask.title).toBe('Local Important Edit (Unsynced)');
      expect(currentTask.status).toBe('In Progress');

      // 5. Verify conflict notice recorded in sync_meta
      const conflictKey = `${SYNC_META_KEYS.CONFLICT_PREFIX}task_${localTask.id}`;
      const conflictRecord = await db.syncMeta.get(conflictKey);
      expect(conflictRecord).toBeDefined();
      expect(conflictRecord.value.entityType).toBe('task');
      expect(conflictRecord.value.localPendingCount).toBeGreaterThan(0);
    });
  });

  // -------------------------------------------------------------------------
  // 4. TRIGGERS, CONCURRENCY LOCKS & GUEST MODE
  // -------------------------------------------------------------------------
  describe('4. Triggers, Concurrency Locks & Account Isolation', () => {
    it('handles unauthenticated guest mode gracefully without network errors', async () => {
      localStorage.removeItem('niyantra_access_token');
      expect(syncManager.isAuthenticated()).toBe(false);

      const pushRes = await syncManager.pushChanges();
      expect(pushRes.status).toBe('unauthenticated');
      expect(pushRes.pushed).toBe(0);

      const pullRes = await syncManager.pullChanges();
      expect(pullRes.status).toBe('unauthenticated');
      expect(pullRes.pulled).toBe(0);

      const syncRes = await syncManager.sync();
      expect(syncRes.status).toBe('unauthenticated');
    });

    it('notifies onSyncComplete listeners upon push or pull', async () => {
      let listenerCalled = false;
      const unsubscribe = syncManager.onSyncComplete((evt) => {
        listenerCalled = true;
        expect(evt).toBeDefined();
      });

      const mockService = {
        async pullSync() {
          return { changes: [], next_cursor: 0, has_more: false };
        },
      };

      await syncManager.pullChanges({ clientService: mockService });
      expect(listenerCalled).toBe(true);
      unsubscribe();
    });

    it('initializes and tears down automatic triggers cleanly', async () => {
      const { initSyncTriggers, teardownSyncTriggers } = await import('../src/sync/syncTriggers');
      expect(() => {
        initSyncTriggers({ intervalMs: 1000, initialSync: false });
        teardownSyncTriggers();
      }).not.toThrow();
    });
  });
});
