import { db } from '../database/db';
import { changeTracker } from './changeTracker';
import {
  SYNC_STATUS,
  DEFAULT_RETRY_CONFIG,
  SYNC_META_KEYS,
} from './syncConstants';

/**
 * Durable Synchronization Queue Manager
 * Provides reliable IndexedDB persistence, FIFO retrieval, retry scheduling,
 * and lifecycle transitions for client change operations.
 */
export const syncQueue = {
  /**
   * Enqueues a new change operation.
   */
  async enqueue(changeParams, targetDb = db) {
    return await changeTracker.recordChange(targetDb, changeParams);
  },

  /**
   * Retrieves pending or retry-eligible operations in FIFO order (createdAt ascending).
   */
  async peek(limit = 50, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const records = await targetDb.syncQueue
      .where('userId')
      .equals(activeUserId)
      .filter((item) => {
        if (item.status === SYNC_STATUS.PENDING) return true;
        if (item.status === SYNC_STATUS.FAILED && item.nextRetryAt && item.nextRetryAt <= now) {
          return true;
        }
        return false;
      })
      .toArray();

    // FIFO sort: oldest operations first to preserve causal ordering, break ties with entityVersion
    records.sort((a, b) => {
      const timeDiff = (a.createdAt || '').localeCompare(b.createdAt || '');
      if (timeDiff !== 0) return timeDiff;
      const verDiff = (a.entityVersion || 1) - (b.entityVersion || 1);
      if (verDiff !== 0) return verDiff;
      return (a.id || '').localeCompare(b.id || '');
    });
    return records.slice(0, limit);
  },

  /**
   * Retrieves an operation by internal record ID.
   */
  async getById(id, targetDb = db) {
    return await targetDb.syncQueue.get(id);
  },

  /**
   * Retrieves an operation by unique operationId.
   */
  async getByOperationId(operationId, targetDb = db) {
    const matches = await targetDb.syncQueue
      .where('operationId')
      .equals(operationId)
      .toArray();
    return matches.length > 0 ? matches[0] : null;
  },

  /**
   * Returns count of PENDING operations for user.
   */
  async getPendingCount(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    return await targetDb.syncQueue
      .where('userId')
      .equals(activeUserId)
      .filter((item) => item.status === SYNC_STATUS.PENDING)
      .count();
  },

  /**
   * Returns count of FAILED operations for user.
   */
  async getFailedCount(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    return await targetDb.syncQueue
      .where('userId')
      .equals(activeUserId)
      .filter((item) => item.status === SYNC_STATUS.FAILED)
      .count();
  },

  /**
   * Retrieves all queue records matching optional filters.
   */
  async getAll(params = {}, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();

    let records = await targetDb.syncQueue
      .where('userId')
      .equals(activeUserId)
      .toArray();

    if (params.status) {
      records = records.filter((r) => r.status === params.status);
    }
    if (params.entityType) {
      records = records.filter((r) => r.entityType === params.entityType);
    }
    if (params.entityId) {
      records = records.filter((r) => r.entityId === String(params.entityId));
    }
    if (params.operation) {
      records = records.filter((r) => r.operation === params.operation);
    }

    records.sort((a, b) => {
      const timeDiff = (a.createdAt || '').localeCompare(b.createdAt || '');
      if (timeDiff !== 0) return timeDiff;
      const verDiff = (a.entityVersion || 1) - (b.entityVersion || 1);
      if (verDiff !== 0) return verDiff;
      return (a.id || '').localeCompare(b.id || '');
    });
    return records;
  },

  /**
   * Marks a batch of operation IDs as PROCESSING.
   */
  async markProcessing(ids = [], targetDb = db) {
    if (!ids.length) return [];
    const now = new Date().toISOString();
    const nowMs = Date.now();

    await targetDb.transaction('rw', targetDb.syncQueue, async () => {
      for (const id of ids) {
        await targetDb.syncQueue.update(id, {
          status: SYNC_STATUS.PROCESSING,
          lastAttemptAt: now,
          leasedAt: nowMs,
          updatedAt: now,
        });
      }
    });

    return ids;
  },

  /**
   * Marks a batch of operation IDs as COMPLETED.
   * Does not remove records prematurely so history is preserved.
   */
  async markCompleted(ids = [], targetDb = db) {
    if (!ids.length) return [];
    const now = new Date().toISOString();

    await targetDb.transaction('rw', [targetDb.syncQueue, targetDb.syncMeta], async () => {
      for (const id of ids) {
        await targetDb.syncQueue.update(id, {
          status: SYNC_STATUS.COMPLETED,
          updatedAt: now,
        });
      }
    });

    return ids;
  },

  /**
   * Marks an operation as FAILED and computes exponential backoff retry time.
   */
  async markFailed(id, errorMessage, retryConfig = {}, targetDb = db) {
    const existing = await targetDb.syncQueue.get(id);
    if (!existing) return null;

    const config = { ...DEFAULT_RETRY_CONFIG, ...retryConfig };
    const nextRetryCount = (existing.retryCount || 0) + 1;
    const now = Date.now();
    const nowIso = new Date(now).toISOString();

    let nextRetryAt = null;
    let isPermanent = false;

    if (nextRetryCount <= config.maxRetries) {
      // Exponential backoff: initial * (factor ^ (retryCount - 1))
      const delayMs = Math.min(
        config.initialBackoffMs * Math.pow(config.backoffFactor, nextRetryCount - 1),
        config.maxBackoffMs
      );
      nextRetryAt = new Date(now + delayMs).toISOString();
    } else {
      isPermanent = true;
    }

    const updates = {
      status: SYNC_STATUS.FAILED,
      retryCount: nextRetryCount,
      lastAttemptAt: nowIso,
      nextRetryAt,
      errorMessage: String(errorMessage || 'Unknown synchronization error'),
      isPermanentFailure: isPermanent,
      updatedAt: nowIso,
    };

    await targetDb.syncQueue.update(id, updates);
    return { ...existing, ...updates };
  },

  /**
   * Resets a failed operation back to PENDING.
   */
  async resetFailed(id, targetDb = db) {
    const existing = await targetDb.syncQueue.get(id);
    if (!existing) return null;

    const now = new Date().toISOString();
    const updates = {
      status: SYNC_STATUS.PENDING,
      retryCount: 0,
      nextRetryAt: null,
      errorMessage: null,
      isPermanentFailure: false,
      updatedAt: now,
    };

    await targetDb.syncQueue.update(id, updates);
    return { ...existing, ...updates };
  },

  /**
   * Safe garbage collection of aged completed records.
   */
  async clearCompleted(olderThanMs = 7 * 86400000, targetDb = db) {
    const cutoffIso = new Date(Date.now() - olderThanMs).toISOString();

    const completed = await targetDb.syncQueue
      .where('status')
      .equals(SYNC_STATUS.COMPLETED)
      .filter((item) => (item.updatedAt || item.createdAt) < cutoffIso)
      .toArray();

    if (completed.length > 0) {
      const ids = completed.map((c) => c.id);
      await targetDb.syncQueue.bulkDelete(ids);
    }
    return completed.length;
  },

  /**
   * Recovers in-flight operations abandoned in PROCESSING state due to browser refresh,
   * unexpected termination, or network crash.
   * Reverts them to PENDING while preserving the original operationId and version.
   */
  async recoverInFlightOperations(targetDb = db, maxLeaseMs = 60000) {
    const now = Date.now();
    const cutoffIso = new Date(now - maxLeaseMs).toISOString();

    const inFlight = await targetDb.syncQueue
      .where('status')
      .equals(SYNC_STATUS.PROCESSING)
      .toArray();

    if (!inFlight.length) return 0;

    let recoveredCount = 0;
    const nowIso = new Date().toISOString();

    await targetDb.transaction('rw', [targetDb.syncQueue, targetDb.syncMeta], async () => {
      for (const op of inFlight) {
        let attemptMs = 0;
        if (op.leasedAt != null) {
          attemptMs = typeof op.leasedAt === 'number' ? op.leasedAt : new Date(op.leasedAt).getTime();
        } else if (op.lastAttemptAt) {
          attemptMs = new Date(op.lastAttemptAt).getTime();
        }

        // If lease expired or absent, recover back to PENDING
        if (!attemptMs || attemptMs <= (now - maxLeaseMs)) {
          await targetDb.syncQueue.update(op.id, {
            status: SYNC_STATUS.PENDING,
            leasedAt: null,
            updatedAt: nowIso,
            errorMessage: 'Recovered from interrupted in-flight session (resumed PENDING)',
          });
          recoveredCount++;
        }
      }

      if (recoveredCount > 0 && targetDb.syncMeta) {
        await targetDb.syncMeta.put({
          key: SYNC_META_KEYS.LAST_RECOVERY_AT,
          value: nowIso,
          updatedAt: nowIso,
        });
      }
    });

    return recoveredCount;
  },

  /**
   * Resets all FAILED operations for the active user back to PENDING.
   * Useful for manual retry triggered by the user.
   */
  async resetAllFailed(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const failed = await targetDb.syncQueue
      .where('userId')
      .equals(activeUserId)
      .filter((item) => item.status === SYNC_STATUS.FAILED)
      .toArray();

    if (!failed.length) return 0;

    const nowIso = new Date().toISOString();
    await targetDb.transaction('rw', targetDb.syncQueue, async () => {
      for (const item of failed) {
        await targetDb.syncQueue.update(item.id, {
          status: SYNC_STATUS.PENDING,
          retryCount: 0,
          nextRetryAt: null,
          errorMessage: null,
          isPermanentFailure: false,
          updatedAt: nowIso,
        });
      }
    });

    return failed.length;
  },
};
