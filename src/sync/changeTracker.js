import { v4 as uuidv4 } from '../utils/uuid';
import {
  SYNC_OPERATIONS,
  SYNC_STATUS,
  SYNC_META_KEYS,
} from './syncConstants';
import { triggerDebouncedSync } from './syncTriggers';

let lastTimestampMs = 0;
let timestampSeq = 0;

function getMonotonicIsoTimestamp() {
  const now = Date.now();
  if (now <= lastTimestampMs) {
    timestampSeq++;
  } else {
    lastTimestampMs = now;
    timestampSeq = 0;
  }
  return new Date(now + timestampSeq).toISOString();
}

/**
 * Centralized Change-Tracking Service
 * Records mutations on synchronized entities into the durable sync queue.
 */
export const changeTracker = {
  /**
   * Constructs a standardized change record.
   */
  createChangeRecord({
    entityType,
    entityId,
    operation,
    entityVersion = 1,
    previousVersion = null,
    payload = {},
    userId = null,
    deviceUuid = null,
    operationId = null,
  }) {
    if (!entityType || !entityId || !operation) {
      throw new Error(
        `Invalid change record parameters: entityType, entityId, and operation are required.`
      );
    }

    if (!Object.values(SYNC_OPERATIONS).includes(operation)) {
      throw new Error(`Unsupported sync operation type: ${operation}`);
    }

    const now = getMonotonicIsoTimestamp();
    const opId = operationId || uuidv4();
    const recordId = uuidv4();

    return {
      id: recordId,
      operationId: opId,
      userId: userId || 'default_user',
      deviceUuid: deviceUuid || 'unknown-device',
      entityType,
      entityId: String(entityId),
      operation,
      entityVersion: Number(entityVersion) || 1,
      previousVersion: previousVersion != null ? Number(previousVersion) : null,
      payload: payload ? JSON.parse(JSON.stringify(payload)) : {},
      createdAt: now,
      updatedAt: now,
      status: SYNC_STATUS.PENDING,
      retryCount: 0,
      lastAttemptAt: null,
      nextRetryAt: null,
      errorMessage: null,
    };
  },

  /**
   * Records a change atomically within the provided Dexie transaction/database.
   * Updates sync_queue and sync_meta.
   */
  async recordChange(targetDb, changeParams) {
    if (!targetDb || !targetDb.syncQueue) {
      console.warn('Target database does not have syncQueue table initialized.');
      return null;
    }

    const activeUserId = changeParams.userId || targetDb.getActiveUserId();
    const deviceUuid = changeParams.deviceUuid || targetDb.getClientDeviceUUID();

    const record = this.createChangeRecord({
      ...changeParams,
      userId: activeUserId,
      deviceUuid,
    });

    const now = new Date().toISOString();

    // Persist into sync_queue
    await targetDb.syncQueue.put(record);

    // Update synchronization metadata
    if (targetDb.syncMeta) {
      await targetDb.syncMeta.put({
        key: SYNC_META_KEYS.LAST_LOCAL_MUTATION,
        value: now,
        updatedAt: now,
      });

      await targetDb.syncMeta.put({
        key: SYNC_META_KEYS.LAST_QUEUED_OP,
        value: record.operationId,
        updatedAt: now,
      });
    }

    try {
      if (typeof window !== 'undefined' && typeof triggerDebouncedSync === 'function') {
        triggerDebouncedSync();
      }
    } catch {
      // Safe fallback in headless/test environments
    }

    return record;
  },
};
