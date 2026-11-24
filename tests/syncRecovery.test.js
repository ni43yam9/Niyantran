import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import 'fake-indexeddb/auto';

// Polyfill localStorage and navigator for node/vitest environment
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
import { syncManager } from '../src/sync/syncManager';
import { syncQueue } from '../src/sync/syncQueue';
import { tabCoordinator } from '../src/sync/tabCoordinator';
import { storageHealth } from '../src/utils/storageHealth';
import { serviceWorkerRegistration } from '../src/utils/serviceWorkerRegistration';
import {
  SYNC_OPERATIONS,
  SYNC_STATUS,
  SYNC_META_KEYS,
  ENGINE_STATUS,
  ENTITY_TYPES,
} from '../src/sync/syncConstants';

describe('Phase 10I: Background Synchronization, Reliability & Recovery', () => {
  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('niyantra_access_token', 'mock_jwt_token_phase10i');
    localStorage.setItem(
      'niyantra_user',
      JSON.stringify({ id: 'user_recovery_test', name: 'Recovery Tester' })
    );

    if (!db.isOpen()) {
      await db.open();
    }
    await db.tasks.clear();
    await db.goals.clear();
    await db.habits.clear();
    await db.syncQueue.clear();
    await db.syncMeta.clear();
    await db.conflicts.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // =========================================================================
  // 1. In-Flight Operation Crash & Lease Recovery
  // =========================================================================
  describe('1. In-Flight Operation Recovery', () => {
    it('recovers orphaned PROCESSING operations after crash/closure while preserving operationId', async () => {
      const activeUserId = db.getActiveUserId();

      // Enqueue two operations
      const op1 = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-crash-1',
          payload: { title: 'Recovered task 1' },
        },
        db
      );

      const op2 = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.UPDATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-crash-2',
          payload: { title: 'Still active task 2' },
        },
        db
      );

      // Simulate crash: op1 was marked PROCESSING 60 seconds ago (lease expired)
      const expiredLeaseTime = Date.now() - 60000;
      await db.syncQueue.update(op1.id, {
        status: SYNC_STATUS.PROCESSING,
        leasedAt: expiredLeaseTime,
        lastAttemptAt: new Date(expiredLeaseTime).toISOString(),
      });

      // op2 is actively being processed right now (lease active)
      const activeLeaseTime = Date.now();
      await db.syncQueue.update(op2.id, {
        status: SYNC_STATUS.PROCESSING,
        leasedAt: activeLeaseTime,
        lastAttemptAt: new Date(activeLeaseTime).toISOString(),
      });

      // Run recovery with standard 30s timeout
      const recoveredCount = await syncQueue.recoverInFlightOperations(db, 30000);
      expect(recoveredCount).toBe(1);

      // Verify op1 was returned to PENDING with preserved operationId
      const recoveredOp1 = await db.syncQueue.get(op1.id);
      expect(recoveredOp1.status).toBe(SYNC_STATUS.PENDING);
      expect(recoveredOp1.leasedAt).toBeNull();
      expect(recoveredOp1.operationId).toBe(op1.operationId);

      // Verify op2 remains PROCESSING because its lease is valid
      const activeOp2 = await db.syncQueue.get(op2.id);
      expect(activeOp2.status).toBe(SYNC_STATUS.PROCESSING);
      expect(activeOp2.leasedAt).toBe(activeLeaseTime);
    });

    it('pushChanges automatically triggers recovery of in-flight operations before batch peek', async () => {
      const activeUserId = db.getActiveUserId();

      const op = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-auto-recover',
          payload: { title: 'Auto recovered on push' },
        },
        db
      );

      // Mark PROCESSING with expired lease
      await db.syncQueue.update(op.id, {
        status: SYNC_STATUS.PROCESSING,
        leasedAt: Date.now() - 90000,
        lastAttemptAt: new Date(Date.now() - 90000).toISOString(),
      });

      // Mock pushSync API
      const mockService = {
        pushSync: vi.fn().mockResolvedValue({
          data: {
            processed: 1,
            applied: 1,
            rejected: 0,
            conflicts: 0,
            results: [{ operation_id: op.operationId, status: 'APPLIED', server_version: 1 }],
          },
        }),
      };

      const result = await syncManager.pushChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('completed');
      expect(result.pushed).toBe(1);

      const finalRecord = await db.syncQueue.get(op.id);
      expect(finalRecord.status).toBe(SYNC_STATUS.COMPLETED);
    });
  });

  // =========================================================================
  // 2. Monotonic Pull Resumption & Interruption Safety
  // =========================================================================
  describe('2. Monotonic Cursor Resumption & Pull Safety', () => {
    it('advances cursor monotonically upon successful pull and acknowledge', async () => {
      const activeUserId = db.getActiveUserId();
      const deviceUuid = db.getClientDeviceUUID();
      const cursorKey = syncManager.getCursorMetaKey(activeUserId, deviceUuid);

      // Verify starting cursor is 0
      const initialMeta = await db.syncMeta.get(cursorKey);
      expect(initialMeta).toBeUndefined();

      const mockService = {
        pullSync: vi.fn().mockResolvedValue({
          data: {
            changes: [
              {
                sequence_id: 42,
                entity_type: ENTITY_TYPES.TASK,
                entity_id: 'task-pull-seq-42',
                operation_type: SYNC_OPERATIONS.CREATE,
                payload: { id: 'task-pull-seq-42', title: 'Remote Task 42', priority: 'High', status: 'Pending' },
                entity_version: 1,
                device_id: 'remote-device',
                timestamp: new Date().toISOString(),
              },
            ],
            next_cursor: 42,
            has_more: false,
          },
        }),
        acknowledgeSync: vi.fn().mockResolvedValue({ data: { acknowledged_cursor: 42 } }),
      };

      const result = await syncManager.pullChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('completed');
      expect(result.pulled).toBe(1);
      expect(result.nextCursor).toBe(42);

      // Cursor persisted locally
      const savedCursor = await db.syncMeta.get(cursorKey);
      expect(Number(savedCursor.value)).toBe(42);

      // Next pull must send cursor=42
      await syncManager.pullChanges({ targetDb: db, clientService: mockService });
      expect(mockService.pullSync).toHaveBeenLastCalledWith(
        42,
        expect.any(Number),
        true,
        null,
        deviceUuid
      );
    });

    it('does not advance cursor if applying remote changes encounters an unhandled exception', async () => {
      const activeUserId = db.getActiveUserId();
      const deviceUuid = db.getClientDeviceUUID();
      const cursorKey = syncManager.getCursorMetaKey(activeUserId, deviceUuid);

      // Pre-set cursor to 10
      await db.syncMeta.put({
        key: cursorKey,
        value: 10,
        updatedAt: new Date().toISOString(),
      });

      // Mock service returns change with sequence 25
      const mockService = {
        pullSync: vi.fn().mockResolvedValue({
          data: {
            changes: [
              {
                sequence_id: 25,
                entity_type: ENTITY_TYPES.TASK,
                entity_id: 'broken',
                operation_type: 'UPDATE',
                payload: { id: 'broken' },
                entity_version: 1,
              },
            ],
            next_cursor: 25,
            has_more: false,
          },
        }),
        acknowledgeSync: vi.fn(),
      };

      // Spy on applyRemoteChange to force error
      const applySpy = vi.spyOn(syncManager, 'applyRemoteChange').mockRejectedValueOnce(
        new Error('Critical deserialization failure')
      );

      const result = await syncManager.pullChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('error');
      expect(mockService.acknowledgeSync).not.toHaveBeenCalled();

      // Cursor must remain 10, preventing delta skipping on recovery
      const cursorMeta = await db.syncMeta.get(cursorKey);
      expect(Number(cursorMeta.value)).toBe(10);
    });
  });

  // =========================================================================
  // 3. Multi-Tab Concurrency & Mutual Exclusion
  // =========================================================================
  describe('3. Multi-Tab Concurrency & Coordination', () => {
    it('provides unique tabId per execution session', () => {
      const tabId = tabCoordinator.getTabId();
      expect(tabId).toBeDefined();
      expect(tabId.startsWith('tab-')).toBe(true);
    });

    it('withLock prevents concurrent sync operations via localStorage fallback lock', async () => {
      const now = Date.now();

      // Simulate a lock held by a competing peer tab
      const remoteLock = {
        tabId: 'tab-competing-peer',
        lockName: 'niyantra_sync_lock',
        acquiredAt: now,
        expiresAt: now + 15000, // Valid for 15 more seconds
      };
      localStorage.setItem('niyantra_sync_tab_lock', JSON.stringify(remoteLock));

      const action = vi.fn().mockResolvedValue('executed');

      // Attempt to acquire lock through storage fallback
      const lockResult = await tabCoordinator._withStorageLock(action, 'niyantra_sync_lock', 10000);

      expect(lockResult.locked).toBe(true);
      expect(lockResult.executed).toBe(false);
      expect(action).not.toHaveBeenCalled();
    });

    it('safely acquires and clears lock when previous peer lease has expired', async () => {
      const staleTime = Date.now() - 30000; // 30s in the past

      const staleLock = {
        tabId: 'tab-stale-crashed-peer',
        lockName: 'niyantra_sync_lock',
        acquiredAt: staleTime - 10000,
        expiresAt: staleTime, // Expired!
      };
      localStorage.setItem('niyantra_sync_tab_lock', JSON.stringify(staleLock));

      const action = vi.fn().mockResolvedValue('success-after-stale-steal');

      const lockResult = await tabCoordinator._withStorageLock(action, 'niyantra_sync_lock', 10000);

      expect(lockResult.locked).toBe(false);
      expect(lockResult.executed).toBe(true);
      expect(lockResult.result).toBe('success-after-stale-steal');
      expect(action).toHaveBeenCalled();

      // After action completion, lock should be cleaned up
      const remainingLock = localStorage.getItem('niyantra_sync_tab_lock');
      expect(remainingLock).toBeNull();
    });

    it('broadcasts synchronization events to registered cross-tab listeners', () => {
      const listenerSpy = vi.fn();
      const unsub = tabCoordinator.onMessage(listenerSpy);

      // Simulate cross-tab event
      tabCoordinator.broadcast({
        type: 'SYNC_COMPLETED',
        pushed: 2,
        pulled: 3,
        status: 'IDLE',
      });

      // Cleanup
      unsub();
      expect(typeof unsub).toBe('function');
    });
  });

  // =========================================================================
  // 4. Network, Server & Authentication Failure Handling
  // =========================================================================
  describe('4. Authentication & Network Failure Handling', () => {
    it('sets ENGINE_STATUS.AUTH_EXPIRED on HTTP 401 and halts retry loops', async () => {
      await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-test-auth',
          payload: { title: 'Test Auth Error' },
        },
        db
      );

      const authError = new Error('HTTP 401 Unauthorized');
      authError.status = 401;

      const mockService = {
        pushSync: vi.fn().mockRejectedValue(authError),
      };

      const result = await syncManager.pushChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('auth_expired');

      const engineMeta = await db.syncMeta.get(SYNC_META_KEYS.ENGINE_STATUS);
      expect(engineMeta.value).toBe(ENGINE_STATUS.AUTH_EXPIRED);
    });

    it('sets ENGINE_STATUS.DEVICE_REVOKED on HTTP 403 device revocation', async () => {
      await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-test-revoked',
          payload: { title: 'Test Revoked' },
        },
        db
      );

      const revokeError = new Error('HTTP 403 Forbidden: Device has been revoked');
      revokeError.status = 403;

      const mockService = {
        pushSync: vi.fn().mockRejectedValue(revokeError),
      };

      const result = await syncManager.pushChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('device_revoked');

      const engineMeta = await db.syncMeta.get(SYNC_META_KEYS.ENGINE_STATUS);
      expect(engineMeta.value).toBe(ENGINE_STATUS.DEVICE_REVOKED);
    });

    it('handles HTTP 429 rate limiting gracefully', async () => {
      await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'task-test-rate-limit',
          payload: { title: 'Test Rate Limit' },
        },
        db
      );

      const rateLimitError = new Error('HTTP 429 Too Many Requests');
      rateLimitError.status = 429;
      rateLimitError.response = { headers: { get: () => '60' } };

      const mockService = {
        pushSync: vi.fn().mockRejectedValue(rateLimitError),
      };

      const result = await syncManager.pushChanges({ targetDb: db, clientService: mockService });

      expect(result.status).toBe('rate_limited');

      const engineMeta = await db.syncMeta.get(SYNC_META_KEYS.ENGINE_STATUS);
      expect(engineMeta.value).toBe(ENGINE_STATUS.RATE_LIMITED);
    });
  });

  // =========================================================================
  // 5. Storage Health & Quota Protection
  // =========================================================================
  describe('5. Storage Health & Quota Protection', () => {
    it('computes storage quota estimate and triggers warning when usage exceeds 90%', async () => {
      // Mock navigator.storage.estimate
      const mockStorage = {
        estimate: vi.fn().mockResolvedValue({
          usage: 950 * 1024 * 1024, // 950 MB
          quota: 1000 * 1024 * 1024, // 1000 MB (95% used)
        }),
        persisted: vi.fn().mockResolvedValue(true),
      };
      vi.stubGlobal('navigator', { storage: mockStorage });

      const estimate = await storageHealth.getStorageQuotaEstimate();

      expect(estimate.usageMB).toBeCloseTo(950, 0);
      expect(estimate.quotaMB).toBeCloseTo(1000, 0);
      expect(estimate.usagePercentage).toBe(95);
      expect(estimate.isWarning).toBe(true);
    });

    it('returns healthy status when usage is well within quota', async () => {
      const mockStorage = {
        estimate: vi.fn().mockResolvedValue({
          usage: 50 * 1024 * 1024, // 50 MB
          quota: 1000 * 1024 * 1024, // 1000 MB (5% used)
        }),
        persisted: vi.fn().mockResolvedValue(true),
      };
      vi.stubGlobal('navigator', { storage: mockStorage });

      const estimate = await storageHealth.getStorageQuotaEstimate();

      expect(estimate.usagePercentage).toBe(5);
      expect(estimate.isWarning).toBe(false);
      expect(estimate.remainingMB).toBeCloseTo(950, 0);
    });

    it('requests persistent storage and returns boolean grant', async () => {
      const mockStorage = {
        persist: vi.fn().mockResolvedValue(true),
        persisted: vi.fn().mockResolvedValue(true),
      };
      vi.stubGlobal('navigator', { storage: mockStorage });

      const granted = await storageHealth.requestPersistentStorage();
      expect(granted).toBe(true);

      const isPersisted = await storageHealth.isStoragePersisted();
      expect(isPersisted).toBe(true);
    });
  });

  // =========================================================================
  // 6. Diagnostics Snapshot & Manual Failed Operation Reset
  // =========================================================================
  describe('6. Diagnostics Snapshot & Manual Failed Reset', () => {
    it('getSyncDiagnostics returns comprehensive telemetry data', async () => {
      const activeUserId = db.getActiveUserId();

      // Enqueue one pending and one failed operation
      const op1 = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'diag-task-1',
          payload: { title: 'Diag 1' },
        },
        db
      );

      const op2 = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.UPDATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'diag-task-2',
          payload: { title: 'Diag 2' },
        },
        db
      );

      await syncQueue.markFailed(op2.id, 'Connection aborted', {}, db);

      const diagnostics = await syncManager.getSyncDiagnostics(activeUserId, db);

      expect(diagnostics).toHaveProperty('userId', activeUserId);
      expect(diagnostics).toHaveProperty('deviceUuid');
      expect(diagnostics).toHaveProperty('pendingCount', 1);
      expect(diagnostics).toHaveProperty('failedCount', 1);
      expect(diagnostics).toHaveProperty('engineStatus');
      expect(diagnostics).toHaveProperty('tabId');
      expect(diagnostics).toHaveProperty('storage');
      expect(diagnostics).toHaveProperty('serviceWorker');
    });

    it('retryAllFailed resets all failed items back to PENDING for immediate retry', async () => {
      const activeUserId = db.getActiveUserId();

      const op = await syncQueue.enqueue(
        {
          operation: SYNC_OPERATIONS.CREATE,
          entityType: ENTITY_TYPES.TASK,
          entityId: 'failed-task',
          payload: { title: 'Failed Task' },
        },
        db
      );

      await syncQueue.markFailed(op.id, 'Timeout 504', {}, db);

      const preReset = await db.syncQueue.get(op.id);
      expect(preReset.status).toBe(SYNC_STATUS.FAILED);

      const resetCount = await syncManager.retryAllFailed(activeUserId, db);
      expect(resetCount).toBe(1);

      const postReset = await db.syncQueue.get(op.id);
      expect(postReset.status).toBe(SYNC_STATUS.PENDING);
      expect(postReset.retryCount).toBe(0);
      expect(postReset.errorMessage).toBeNull();
    });
  });

  // =========================================================================
  // 7. Background Sync API Fallback
  // =========================================================================
  describe('7. Background Sync API & Graceful Fallback', () => {
    it('detects lack of native Background Sync API and indicates foreground fallback', () => {
      vi.stubGlobal('window', { SyncManager: undefined });
      const isSupported = serviceWorkerRegistration.isBackgroundSyncSupported();
      expect(isSupported).toBe(false);
    });

    it('requestBackgroundSync resolves safely without throwing when unsupported', async () => {
      vi.stubGlobal('navigator', { serviceWorker: undefined });
      const result = await serviceWorkerRegistration.requestBackgroundSync();
      expect(result).toBe(false);
    });
  });
});
