import { db } from '../database/db';
import { syncQueue } from './syncQueue';
import {
  SYNC_OPERATIONS,
  SYNC_STATUS,
  SYNC_META_KEYS,
  ENGINE_STATUS,
  ENTITY_TYPES,
} from './syncConstants';
import syncService from '../services/syncService';
import { taskRepository } from '../database/repositories/taskRepository';
import { goalRepository } from '../database/repositories/goalRepository';
import { habitRepository } from '../database/repositories/habitRepository';
import { timeblockRepository } from '../database/repositories/timeblockRepository';
import { dailyIntentRepository } from '../database/repositories/dailyIntentRepository';
import { recommendationRepository } from '../database/repositories/recommendationRepository';
import { conflictDetector } from './conflictDetector';
import { conflictResolver } from './conflictResolver';
import { tabCoordinator } from './tabCoordinator';
import { storageHealth } from '../utils/storageHealth';
import { serviceWorkerRegistration } from '../utils/serviceWorkerRegistration';

/**
 * State and synchronization listeners
 */
let isPushing = false;
let isPulling = false;
let isSyncing = false;
const syncListeners = new Set();

function notifySyncListeners(event) {
  syncListeners.forEach((fn) => {
    try {
      fn(event);
    } catch (e) {
      console.warn('Error in sync listener:', e);
    }
  });
}

function getStoredToken() {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage.getItem('niyantra_access_token');
    }
  } catch {
    return null;
  }
  return null;
}

export const syncManager = {
  /**
   * Registers a callback invoked whenever a push, pull, or full sync completes.
   */
  onSyncComplete(callback) {
    syncListeners.add(callback);
    return () => syncListeners.delete(callback);
  },

  /**
   * Emits an event to all registered sync listeners.
   */
  notify(event) {
    notifySyncListeners(event);
  },

  /**
   * Checks whether the user is authenticated and cloud sync can proceed.
   */
  isAuthenticated() {
    return Boolean(getStoredToken());
  },

  /**
   * Resolves the cursor key for a given user and device.
   */
  getCursorMetaKey(userId, deviceUuid) {
    return `${SYNC_META_KEYS.LAST_PULLED_CURSOR}_${userId}_${deviceUuid}`;
  },

  /**
   * Retrieves the latest successfully acknowledged pull cursor for the user and device.
   */
  async getCursor(userId = null, deviceUuid = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const activeDeviceUuid = deviceUuid || targetDb.getClientDeviceUUID();
    const key = this.getCursorMetaKey(activeUserId, activeDeviceUuid);

    if (targetDb.syncMeta) {
      const record = await targetDb.syncMeta.get(key);
      if (record && record.value != null) {
        return Number(record.value) || 0;
      }
    }
    return 0;
  },

  /**
   * Updates the pull cursor checkpoint in IndexedDB metadata.
   */
  async setCursor(cursor, userId = null, deviceUuid = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const activeDeviceUuid = deviceUuid || targetDb.getClientDeviceUUID();
    const key = this.getCursorMetaKey(activeUserId, activeDeviceUuid);
    const now = new Date().toISOString();

    if (targetDb.syncMeta) {
      await targetDb.syncMeta.put({
        key,
        value: Number(cursor) || 0,
        updatedAt: now,
      });
    }
  },

  /**
   * Pushes a batch of locally queued change operations to the cloud backend.
   * Enforces batching, idempotency, retry scheduling, and atomic state transitions.
   */
  async pushChanges({
    batchSize = 50,
    targetDb = db,
    clientService = syncService,
  } = {}) {
    if (isPushing) {
      return { pushed: 0, status: 'locked', message: 'Push already in progress' };
    }

    const token = getStoredToken();
    if (!token) {
      return { pushed: 0, status: 'unauthenticated', message: 'User not authenticated for cloud sync' };
    }

    const activeUserId = targetDb.getActiveUserId();
    const deviceUuid = targetDb.getClientDeviceUUID();

    isPushing = true;
    let totalPushed = 0;
    let totalRejected = 0;

    try {
      // Phase 10I: Recover any orphaned in-flight operations left from interrupted sessions/crashes
      await syncQueue.recoverInFlightOperations(targetDb);

      // Loop to drain pending queue in manageable batches (up to 5 batches per run)
      for (let run = 0; run < 5; run++) {
        const batch = await syncQueue.peek(batchSize, activeUserId, targetDb);
        if (!batch || !batch.length) {
          break;
        }

        const batchIds = batch.map((item) => item.id);
        await syncQueue.markProcessing(batchIds, targetDb);

        const now = new Date().toISOString();
        if (targetDb.syncMeta) {
          await targetDb.syncMeta.put({
            key: SYNC_META_KEYS.LAST_SYNC_ATTEMPT,
            value: now,
            updatedAt: now,
          });
        }

        let pushResponse;
        try {
          pushResponse = await clientService.pushSync(batch, deviceUuid);
        } catch (err) {
          console.warn('Network or server error during sync push:', err);
          const errMsg = String(err.message || '');
          const is401 = err.status === 401 || errMsg.includes('401') || errMsg.toLowerCase().includes('unauthorized');
          const is403 = err.status === 403 || errMsg.includes('403') || errMsg.toLowerCase().includes('revoked');
          const is429 = err.status === 429 || errMsg.includes('429');

          let engineStatus = ENGINE_STATUS.ERROR;
          if (is401) engineStatus = ENGINE_STATUS.AUTH_EXPIRED;
          else if (is403) engineStatus = ENGINE_STATUS.DEVICE_REVOKED;
          else if (is429) engineStatus = ENGINE_STATUS.RATE_LIMITED;

          if (targetDb.syncMeta) {
            await targetDb.syncMeta.put({
              key: SYNC_META_KEYS.ENGINE_STATUS,
              value: engineStatus,
              updatedAt: new Date().toISOString(),
            });
          }

          // Network or auth failure: mark operations accordingly
          for (const item of batch) {
            await syncQueue.markFailed(
              item.id,
              is401
                ? 'Authentication expired (HTTP 401)'
                : is403
                ? 'Device revoked (HTTP 403)'
                : errMsg || 'Push transmission failed',
              is401 || is403 ? { maxRetries: 0 } : {},
              targetDb
            );
          }
          return {
            pushed: totalPushed,
            rejected: totalRejected + batch.length,
            status: is401 ? 'auth_expired' : is403 ? 'device_revoked' : is429 ? 'rate_limited' : 'error',
            error: err.message,
          };
        }

        if (pushResponse && pushResponse.data) {
          pushResponse = pushResponse.data;
        }

        if (!pushResponse || !Array.isArray(pushResponse.results)) {
          // Unexpected payload structure
          for (const item of batch) {
            await syncQueue.markFailed(
              item.id,
              'Invalid server push response format',
              {},
              targetDb
            );
          }
          break;
        }

        // Process per-operation server outcomes
        const resultsMap = new Map();
        for (const res of pushResponse.results) {
          const resUuid = res.operation_uuid || res.operation_id || res.id;
          resultsMap.set(resUuid, res);
        }

        for (const op of batch) {
          const opUuid = op.operationId || op.id;
          const serverRes = resultsMap.get(opUuid);

          if (serverRes && serverRes.status === 'APPLIED') {
            await syncQueue.markCompleted([op.id], targetDb);
            totalPushed++;
          } else {
            const errorMsg = serverRes ? serverRes.message : 'Operation rejected by server';
            await syncQueue.markFailed(op.id, errorMsg, {}, targetDb);
            totalRejected++;
          }
        }

        // Update successful sync timestamp
        if (targetDb.syncMeta) {
          await targetDb.syncMeta.put({
            key: SYNC_META_KEYS.LAST_SUCCESSFUL_SYNC,
            value: pushResponse.server_timestamp || new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          });
        }

        // If batch was smaller than batchSize, we've drained the eligible items
        if (batch.length < batchSize) {
          break;
        }
      }

      notifySyncListeners({ type: 'push', pushed: totalPushed, rejected: totalRejected });
      return {
        pushed: totalPushed,
        rejected: totalRejected,
        status: 'completed',
      };
    } finally {
      isPushing = false;
    }
  },

  /**
   * Pulls delta changes from the server occurring after the local cursor checkpoint.
   * Applies remote mutations with trackChange=false to guarantee no outgoing queue loops.
   * Safeguards unpushed local changes against silent overwrites.
   */
  async pullChanges({
    limit = 50,
    targetDb = db,
    clientService = syncService,
  } = {}) {
    if (isPulling) {
      return { pulled: 0, status: 'locked', message: 'Pull already in progress' };
    }

    const token = getStoredToken();
    if (!token) {
      return { pulled: 0, status: 'unauthenticated', message: 'User not authenticated for cloud sync' };
    }

    const activeUserId = targetDb.getActiveUserId();
    const deviceUuid = targetDb.getClientDeviceUUID();

    isPulling = true;
    let totalPulled = 0;
    let hasMore = true;
    let currentCursor = await this.getCursor(activeUserId, deviceUuid, targetDb);

    try {
      while (hasMore) {
        let pullResponse;
        try {
          pullResponse = await clientService.pullSync(
            currentCursor,
            limit,
            true, // exclude_self: do not download own device's changes
            null,
            deviceUuid
          );
        } catch (err) {
          console.warn('Network or server error during sync pull:', err);
          const errMsg = String(err.message || '');
          const is401 = err.status === 401 || errMsg.includes('401') || errMsg.toLowerCase().includes('unauthorized');
          const is403 = err.status === 403 || errMsg.includes('403') || errMsg.toLowerCase().includes('revoked');

          if (is401 && targetDb.syncMeta) {
            await targetDb.syncMeta.put({
              key: SYNC_META_KEYS.ENGINE_STATUS,
              value: ENGINE_STATUS.AUTH_EXPIRED,
              updatedAt: new Date().toISOString(),
            });
          } else if (is403 && targetDb.syncMeta) {
            await targetDb.syncMeta.put({
              key: SYNC_META_KEYS.ENGINE_STATUS,
              value: ENGINE_STATUS.DEVICE_REVOKED,
              updatedAt: new Date().toISOString(),
            });
          }

          return {
            pulled: totalPulled,
            nextCursor: currentCursor,
            status: is401 ? 'auth_expired' : is403 ? 'device_revoked' : 'error',
            error: err.message,
          };
        }

        if (pullResponse && pullResponse.data) {
          pullResponse = pullResponse.data;
        }

        if (!pullResponse || !Array.isArray(pullResponse.changes)) {
          break;
        }

        const changes = pullResponse.changes;
        if (changes.length === 0) {
          break;
        }

        // Apply remote changes to local IndexedDB with safe crash isolation
        try {
          for (const change of changes) {
            const entityType = change.entity_type;
            const entityId = String(change.entity_id);
            const opType = (change.operation_type || 'UPDATE').toUpperCase();
            const version = Number(change.entity_version) || 1;
            const payload = change.payload || {};

            // PHASE 10H CONFLICT SAFETY CHECK:
            // Detect concurrent offline edits, update vs delete, and divergent versions
            const conflictEval = await conflictDetector.detectConflict({
              change,
              targetDb,
              activeUserId,
            });

            if (conflictEval.hasConflict) {
              // Local unsynced edits or conflicting states exist! Do NOT silently overwrite user's local work.
              // Record structured 3-way conflict in Dexie conflicts store for user resolution
              await conflictDetector.recordConflict({
                change,
                conflictEvaluation: conflictEval,
                targetDb,
                activeUserId,
              });

              // Backward-compatibility: also maintain sync_meta stub
              if (targetDb.syncMeta) {
                const conflictKey = `${SYNC_META_KEYS.CONFLICT_PREFIX}${entityType}_${entityId}`;
                await targetDb.syncMeta.put({
                  key: conflictKey,
                  value: {
                    entityType,
                    entityId,
                    remoteVersion: version,
                    remoteOperation: opType,
                    remotePayload: payload,
                    localPendingCount: conflictEval.localPendingOps.length,
                    detectedAt: new Date().toISOString(),
                  },
                  updatedAt: new Date().toISOString(),
                });
              }
              // Defer remote change to protect local unpushed state
              continue;
            }

            // No local conflict: Apply remote change with trackChange: false
            await this.applyRemoteChange({
              entityType,
              entityId,
              operationType: opType,
              version,
              payload,
              activeUserId,
              targetDb,
            });

            totalPulled++;
          }

          // Advance cursor checkpoint and acknowledge to server ONLY after successful local writes
          const serverCursor = pullResponse.next_cursor != null ? pullResponse.next_cursor : pullResponse.cursor;
          if (serverCursor != null) {
            currentCursor = Number(serverCursor);
            await this.setCursor(currentCursor, activeUserId, deviceUuid, targetDb);

            try {
              if (typeof clientService.acknowledgeSync === 'function') {
                await clientService.acknowledgeSync(currentCursor, deviceUuid);
              } else if (typeof clientService.acknowledgeCursor === 'function') {
                await clientService.acknowledgeCursor(currentCursor, deviceUuid);
              }
            } catch (ackErr) {
              console.warn('Failed to send cursor acknowledgement to server (continuing):', ackErr);
            }
          }

          hasMore = Boolean(pullResponse.has_more);
        } catch (applyErr) {
          console.error('[SyncManager] Error applying remote change batch:', applyErr);
          return {
            pulled: totalPulled,
            nextCursor: currentCursor,
            status: 'error',
            error: applyErr.message,
          };
        }
      }

      // Update successful sync timestamp
      if (targetDb.syncMeta) {
        await targetDb.syncMeta.put({
          key: SYNC_META_KEYS.LAST_SUCCESSFUL_SYNC,
          value: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        });
      }

      notifySyncListeners({ type: 'pull', pulled: totalPulled, cursor: currentCursor });
      return {
        pulled: totalPulled,
        nextCursor: currentCursor,
        status: 'completed',
      };
    } finally {
      isPulling = false;
    }
  },

  /**
   * Internal dispatcher that applies a remote mutation to the corresponding Dexie repository
   * with trackChange: false so it never loops back into the outgoing sync queue.
   */
  async applyRemoteChange({
    entityType,
    entityId,
    operationType,
    version,
    payload,
    activeUserId,
    targetDb,
  }) {
    const now = new Date().toISOString();
    const isDelete = operationType === 'DELETE';

    switch (entityType) {
      case ENTITY_TYPES.TASK:
      case 'task': {
        if (isDelete) {
          await taskRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await taskRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.GOAL:
      case 'goal': {
        if (isDelete) {
          await goalRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await goalRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.HABIT:
      case 'habit': {
        if (isDelete) {
          await habitRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await habitRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.HABIT_LOG:
      case 'habit_log': {
        if (isDelete) {
          const existing = await targetDb.habitLogs.get(entityId);
          if (existing) {
            await targetDb.habitLogs.update(entityId, {
              isDeleted: 1,
              deletedAt: now,
              version,
              updatedAt: now,
            });
          }
        } else {
          await targetDb.habitLogs.put({
            id: entityId,
            habitId: payload.habitId || payload.habit_id,
            userId: activeUserId,
            logDate: payload.logDate || payload.log_date || now.slice(0, 10),
            completed: payload.completed !== undefined ? payload.completed : true,
            notes: payload.notes || null,
            version,
            isDeleted: 0,
            deletedAt: null,
            createdAt: payload.createdAt || payload.created_at || now,
            updatedAt: now,
          });
        }
        break;
      }

      case ENTITY_TYPES.DAILY_TIMEBLOCK:
      case 'daily_timeblock':
      case 'timeblock': {
        if (isDelete) {
          await timeblockRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await timeblockRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.DAILY_INTENT:
      case 'daily_intent': {
        if (isDelete) {
          await dailyIntentRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await dailyIntentRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.RECOMMENDATION:
      case 'recommendation': {
        if (isDelete) {
          await recommendationRepository.delete(
            entityId,
            activeUserId,
            { softDelete: true, trackChange: false },
            targetDb
          );
        } else {
          await recommendationRepository.save(
            {
              ...payload,
              id: entityId,
              version,
              isDeleted: 0,
            },
            activeUserId,
            { trackChange: false },
            targetDb
          );
        }
        break;
      }

      case ENTITY_TYPES.ACTIVITY_LOG:
      case 'activity_log': {
        if (!isDelete) {
          await targetDb.activityLogs.put({
            ...payload,
            id: entityId,
            userId: activeUserId,
            deviceUuid: payload.deviceUuid || payload.device_id || 'remote',
            timestamp: payload.timestamp || now,
          });
        }
        break;
      }

      default:
        console.warn(`[SyncManager] Unrecognized entity type '${entityType}', skipping.`);
    }
  },

  async _applyRemoteChange(args) {
    return this.applyRemoteChange(args);
  },

  /**
   * Performs full two-way synchronization: Pushes pending local changes first,
   * then pulls remote delta changes.
   * Coordinates multi-tab execution using tabCoordinator Web Locks.
   */
  async sync({ targetDb = db, clientService = syncService } = {}) {
    const lockRes = await tabCoordinator.withLock(async () => {
      return await this._executeSyncInternal({ targetDb, clientService });
    });

    if (lockRes.locked) {
      return {
        status: 'locked',
        pushed: 0,
        pulled: 0,
        message: lockRes.message || 'Synchronization in progress in another tab',
      };
    }

    return lockRes.result;
  },

  /**
   * Internal execution of two-way push and pull pipeline.
   */
  async _executeSyncInternal({ targetDb = db, clientService = syncService } = {}) {
    if (isSyncing) {
      return { status: 'locked', message: 'Synchronization already in progress' };
    }

    const token = getStoredToken();
    if (!token) {
      return {
        status: 'unauthenticated',
        pushed: 0,
        pulled: 0,
        message: 'Guest/offline mode: user not logged in.',
      };
    }

    isSyncing = true;
    try {
      if (targetDb.syncMeta) {
        await targetDb.syncMeta.put({
          key: SYNC_META_KEYS.ENGINE_STATUS,
          value: ENGINE_STATUS.PROCESSING,
          updatedAt: new Date().toISOString(),
        });
      }

      // Step 1: Push outgoing local changes
      const pushRes = await this.pushChanges({ targetDb, clientService });

      // Step 2: Pull incoming remote changes
      const pullRes = await this.pullChanges({ targetDb, clientService });

      const isAuthExpired = pushRes.status === 'auth_expired' || pullRes.status === 'auth_expired';
      const isDeviceRevoked = pushRes.status === 'device_revoked' || pullRes.status === 'device_revoked';
      const hasErrors = pushRes.status === 'error' || pullRes.status === 'error';

      const engineStatus = isAuthExpired
        ? ENGINE_STATUS.AUTH_EXPIRED
        : isDeviceRevoked
        ? ENGINE_STATUS.DEVICE_REVOKED
        : hasErrors
        ? ENGINE_STATUS.ERROR
        : ENGINE_STATUS.IDLE;

      if (targetDb.syncMeta) {
        await targetDb.syncMeta.put({
          key: SYNC_META_KEYS.ENGINE_STATUS,
          value: engineStatus,
          updatedAt: new Date().toISOString(),
        });
      }

      // Register background sync task if supported and pending items exist
      if (serviceWorkerRegistration.isBackgroundSyncSupported() && pushRes.rejected > 0) {
        void serviceWorkerRegistration.requestBackgroundSync();
      }

      // Broadcast outcome to other open tabs
      tabCoordinator.broadcast({
        type: 'SYNC_COMPLETED',
        pushed: pushRes.pushed || 0,
        pulled: pullRes.pulled || 0,
        status: engineStatus,
      });

      notifySyncListeners({
        type: 'sync',
        pushed: pushRes.pushed || 0,
        pulled: pullRes.pulled || 0,
        status: engineStatus,
      });

      return {
        status: isAuthExpired
          ? 'auth_expired'
          : isDeviceRevoked
          ? 'device_revoked'
          : hasErrors
          ? 'error'
          : 'synced',
        pushed: pushRes.pushed || 0,
        pulled: pullRes.pulled || 0,
        pushStatus: pushRes.status,
        pullStatus: pullRes.status,
      };
    } finally {
      isSyncing = false;
    }
  },

  /**
   * Retrieves high-level synchronization metrics, active queue counts, and cursor checkpoints.
   */
  async getSyncSummary(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const deviceUuid = targetDb.getClientDeviceUUID();

    const [pendingCount, failedCount, allRecords] = await Promise.all([
      syncQueue.getPendingCount(activeUserId, targetDb),
      syncQueue.getFailedCount(activeUserId, targetDb),
      targetDb.syncQueue.where('userId').equals(activeUserId).toArray(),
    ]);

    const completedCount = allRecords.filter(
      (r) => r.status === SYNC_STATUS.COMPLETED
    ).length;

    let lastMutationAt = null;
    let lastAttemptAt = null;
    let lastSuccessfulSyncAt = null;
    let engineStatus = ENGINE_STATUS.IDLE;
    let cursor = 0;
    let conflictCount = 0;

    if (targetDb.conflicts) {
      try {
        conflictCount = await targetDb.conflicts
          .where('status')
          .equals('PENDING_RESOLUTION')
          .filter((c) => c.userId === activeUserId)
          .count();
      } catch {
        conflictCount = 0;
      }
    }

    if (targetDb.syncMeta) {
      const cursorKey = this.getCursorMetaKey(activeUserId, deviceUuid);
      const [mutMeta, attMeta, succMeta, engMeta, curMeta] = await Promise.all([
        targetDb.syncMeta.get(SYNC_META_KEYS.LAST_LOCAL_MUTATION),
        targetDb.syncMeta.get(SYNC_META_KEYS.LAST_SYNC_ATTEMPT),
        targetDb.syncMeta.get(SYNC_META_KEYS.LAST_SUCCESSFUL_SYNC),
        targetDb.syncMeta.get(SYNC_META_KEYS.ENGINE_STATUS),
        targetDb.syncMeta.get(cursorKey),
      ]);

      if (mutMeta && mutMeta.value) lastMutationAt = mutMeta.value;
      if (attMeta && attMeta.value) lastAttemptAt = attMeta.value;
      if (succMeta && succMeta.value) lastSuccessfulSyncAt = succMeta.value;
      if (engMeta && engMeta.value) engineStatus = engMeta.value;
      if (curMeta && curMeta.value != null) cursor = Number(curMeta.value) || 0;
    }

    const authenticated = this.isAuthenticated();

    return {
      userId: activeUserId,
      deviceUuid,
      pendingCount,
      failedCount,
      completedCount,
      totalCount: allRecords.length,
      lastMutationAt,
      lastAttemptAt,
      lastSuccessfulSyncAt,
      currentCursor: cursor,
      conflictCount,
      isAllSavedLocally: true,
      cloudSyncImplemented: false,
      isAuthenticated: authenticated,
      engineStatus: !authenticated ? ENGINE_STATUS.UNAUTHENTICATED : engineStatus,
    };
  },

  /**
   * Retrieves comprehensive synchronization diagnostics for the UI modal & debugging.
   */
  async getSyncDiagnostics(userId = null, targetDb = db) {
    const summary = await this.getSyncSummary(userId, targetDb);
    const [storageEstimate, isPersisted] = await Promise.all([
      storageHealth.getStorageQuotaEstimate(),
      storageHealth.isStoragePersisted(),
    ]);

    let lastRecoveryAt = null;
    if (targetDb.syncMeta) {
      try {
        const rec = await targetDb.syncMeta.get(SYNC_META_KEYS.LAST_RECOVERY_AT);
        if (rec && rec.value) lastRecoveryAt = rec.value;
      } catch {
        lastRecoveryAt = null;
      }
    }

    let inFlightCount = 0;
    try {
      inFlightCount = await targetDb.syncQueue
        .where('userId')
        .equals(summary.userId)
        .filter((op) => op.status === SYNC_STATUS.PROCESSING)
        .count();
    } catch {
      inFlightCount = 0;
    }

    const isBgSyncSupported = serviceWorkerRegistration.isBackgroundSyncSupported();
    const isServiceWorkerSupported = serviceWorkerRegistration.isServiceWorkerSupported();

    return {
      ...summary,
      inFlightCount,
      lastRecoveryAt,
      isSyncing,
      isPushing,
      isPulling,
      tabId: tabCoordinator.getTabId(),
      isWebLocksSupported: tabCoordinator.isWebLocksSupported(),
      storage: {
        isPersisted,
        ...storageEstimate,
      },
      serviceWorker: {
        isSupported: isServiceWorkerSupported,
        isBackgroundSyncSupported: isBgSyncSupported,
      },
    };
  },

  /**
   * Resets all failed queue items back to PENDING so they can be retried immediately.
   */
  async retryAllFailed(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const count = await syncQueue.resetAllFailed(activeUserId, targetDb);
    notifySyncListeners({ type: 'FAILED_RESET', count });
    return count;
  },

  /**
   * Legacy simulation helper preserved for Phase 10E tests.
   */
  async simulateProcessBatch(options = {}) {
    const { batchSize = 50, shouldFail = false, failPredicate = null, targetDb = db } = options;
    const activeUserId = targetDb.getActiveUserId();
    const batch = await syncQueue.peek(batchSize, activeUserId, targetDb);
    if (!batch.length) {
      return { processed: 0, completed: 0, failed: 0 };
    }

    const now = new Date().toISOString();
    const ids = batch.map((b) => b.id);
    await syncQueue.markProcessing(ids, targetDb);

    if (targetDb.syncMeta) {
      await targetDb.syncMeta.put({
        key: SYNC_META_KEYS.LAST_SYNC_ATTEMPT,
        value: now,
        updatedAt: now,
      });
    }

    let completed = 0;
    let failed = 0;

    for (const op of batch) {
      const willFail = shouldFail || (typeof failPredicate === 'function' && failPredicate(op));

      if (willFail) {
        await syncQueue.markFailed(op.id, 'Simulated local processing error', {}, targetDb);
        failed++;
      } else {
        await syncQueue.markCompleted([op.id], targetDb);
        completed++;
      }
    }

    return {
      processed: batch.length,
      completed,
      failed,
    };
  },

  /**
   * Resets the sync queue for a user.
   */
  async resetQueue(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const records = await targetDb.syncQueue.where('userId').equals(activeUserId).toArray();
    if (records.length > 0) {
      const ids = records.map((r) => r.id);
      await targetDb.syncQueue.bulkDelete(ids);
    }
    return records.length;
  },
};
