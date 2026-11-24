/**
 * NIYANTRA Phase 10H: Advanced Conflict Detection Engine
 * 
 * Detects concurrent offline edits, update vs delete divergence, stale versions,
 * and multi-batch collisions using canonical versions and entity state.
 * Preserves 3-way conflict data (base, local, remote) safely in IndexedDB.
 */

import { v4 as uuidv4 } from '../utils/uuid';
import {
  CONFLICT_STATUS,
  SYNC_STATUS,
  SYNC_META_KEYS,
  ENTITY_TYPES,
} from './syncConstants';

const conflictListeners = new Set();

/**
 * Register a listener callback invoked when conflicts are detected or resolved.
 */
export function registerConflictListener(callback) {
  if (typeof callback === 'function') {
    conflictListeners.add(callback);
    return () => conflictListeners.delete(callback);
  }
  return () => {};
}

/**
 * Notify all registered conflict listeners.
 */
export function notifyConflictListeners(event) {
  conflictListeners.forEach((listener) => {
    try {
      listener(event);
    } catch (e) {
      console.warn('Error in conflict listener:', e);
    }
  });
}

/**
 * Map entity type string to Dexie table property name on NiyantraDatabase.
 */
export function getTablePropertyForEntity(entityType) {
  const norm = String(entityType).toLowerCase().trim();
  switch (norm) {
    case 'task':
    case ENTITY_TYPES.TASK:
      return 'tasks';
    case 'goal':
    case ENTITY_TYPES.GOAL:
      return 'goals';
    case 'habit':
    case ENTITY_TYPES.HABIT:
      return 'habits';
    case 'habit_log':
    case ENTITY_TYPES.HABIT_LOG:
      return 'habitLogs';
    case 'daily_timeblock':
    case ENTITY_TYPES.DAILY_TIMEBLOCK:
      return 'dailyTimeblocks';
    case 'daily_intent':
    case ENTITY_TYPES.DAILY_INTENT:
      return 'dailyIntents';
    case 'activity_log':
    case ENTITY_TYPES.ACTIVITY_LOG:
      return 'activityLogs';
    case 'recommendation':
    case ENTITY_TYPES.RECOMMENDATION:
      return 'recommendations';
    default:
      return null;
  }
}

export const conflictDetector = {
  /**
   * Evaluates whether an incoming remote change conflicts with current local state.
   * A conflict is triggered if:
   * 1. There are pending unpushed operations in sync_queue for this entity.
   * 2. Or the local entity has been modified/deleted concurrently while offline.
   * 3. Or update vs delete collision occurs.
   */
  async detectConflict({
    change,
    targetDb,
    activeUserId,
  }) {
    const entityType = change.entity_type;
    const entityId = String(change.entity_id);
    const remoteVersion = Number(change.entity_version) || 1;
    const remoteOp = (change.operation_type || 'UPDATE').toUpperCase();

    // 1. Check local pending unpushed operations
    let localPendingOps = [];
    if (targetDb.syncQueue) {
      localPendingOps = await targetDb.syncQueue
        .where('[userId+entityType+entityId]')
        .equals([activeUserId, entityType, entityId])
        .filter((item) => item.status === SYNC_STATUS.PENDING)
        .toArray();
    }

    // 2. Inspect local entity in its table
    const tableProp = getTablePropertyForEntity(entityType);
    let localEntity = null;
    if (tableProp && targetDb[tableProp]) {
      localEntity = await targetDb[tableProp].get(entityId);
    }

    // Detect conditions:
    // Condition A: Local unsynced pending changes exist while remote change arrived
    if (localPendingOps.length > 0) {
      const localOp = localPendingOps[0];
      const isUpdateVsDelete =
        (remoteOp === 'DELETE' && localOp.operation !== 'DELETE') ||
        (remoteOp !== 'DELETE' && localOp.operation === 'DELETE');

      return {
        hasConflict: true,
        reason: isUpdateVsDelete
          ? 'UPDATE_VS_DELETE'
          : 'CONCURRENT_OFFLINE_EDITS',
        localPendingOps,
        localEntity,
        remoteOp,
        remoteVersion,
      };
    }

    // Condition B: Stale incoming remote update if local version is higher and entity was modified
    if (localEntity && localEntity.version > remoteVersion && localEntity.updatedAt) {
      return {
        hasConflict: true,
        reason: 'STALE_REMOTE_VERSION',
        localPendingOps: [],
        localEntity,
        remoteOp,
        remoteVersion,
      };
    }

    return {
      hasConflict: false,
      reason: null,
      localPendingOps: [],
      localEntity,
      remoteOp,
      remoteVersion,
    };
  },

  /**
   * Persists a structured 3-way conflict record into IndexedDB `conflicts` table.
   * Preserves local version, remote version, base version, originating devices, and timestamps.
   */
  async recordConflict({
    change,
    conflictEvaluation,
    targetDb,
    activeUserId,
  }) {
    const entityType = change.entity_type;
    const entityId = String(change.entity_id);
    const now = new Date().toISOString();
    const tableProp = getTablePropertyForEntity(entityType);

    const localPendingOp = conflictEvaluation.localPendingOps[0] || null;
    let localEntity = conflictEvaluation.localEntity;

    if (!localEntity && tableProp && targetDb[tableProp]) {
      localEntity = await targetDb[tableProp].get(entityId);
    }

    // Determine versions
    const localVersion = localPendingOp
      ? Number(localPendingOp.entityVersion) || 1
      : localEntity
      ? Number(localEntity.version) || 1
      : 1;

    const baseVersion = localPendingOp && localPendingOp.previousVersion != null
      ? Number(localPendingOp.previousVersion)
      : Math.max(1, localVersion - 1);

    const remoteVersion = Number(change.entity_version) || 1;
    const remoteOp = (change.operation_type || 'UPDATE').toUpperCase();
    const localOp = localPendingOp
      ? localPendingOp.operation
      : localEntity?.isDeleted
      ? 'DELETE'
      : 'UPDATE';

    const localData = localPendingOp?.payload
      ? { ...localPendingOp.payload }
      : localEntity
      ? { ...localEntity }
      : {};

    const remoteData = change.payload ? { ...change.payload } : {};

    // Check if an existing unresolved conflict already exists for this entity
    let existingConflict = null;
    if (targetDb.conflicts) {
      existingConflict = await targetDb.conflicts
        .where('[userId+entityType+entityId]')
        .equals([activeUserId, entityType, entityId])
        .filter((c) => c.status === CONFLICT_STATUS.PENDING_RESOLUTION)
        .first();
    }

    const conflictId = existingConflict ? existingConflict.id : uuidv4();
    const detectedAt = existingConflict ? existingConflict.detectedAt : now;

    const conflictRecord = {
      id: conflictId,
      userId: activeUserId,
      entityType,
      entityId,
      status: CONFLICT_STATUS.PENDING_RESOLUTION,
      reason: conflictEvaluation.reason,
      baseVersion,
      localVersion,
      remoteVersion,
      localOperation: localOp,
      remoteOperation: remoteOp,
      localOperationId: localPendingOp ? (localPendingOp.operationId || localPendingOp.id) : null,
      remoteOperationId: change.operation_uuid || null,
      localDeviceUuid: localPendingOp?.deviceUuid || targetDb.getClientDeviceUUID(),
      remoteDeviceUuid: change.device_uuid || 'remote_device',
      localData,
      remoteData,
      baseData: existingConflict?.baseData || null,
      detectedAt,
      updatedAt: now,
      resolvedAt: null,
      resolutionStrategy: null,
      resolvedData: null,
    };

    if (targetDb.conflicts) {
      await targetDb.conflicts.put(conflictRecord);
    }

    // Update metadata conflict counter
    await this.updateConflictCount(activeUserId, targetDb);

    // Notify listeners
    notifyConflictListeners({
      type: 'CONFLICT_DETECTED',
      conflict: conflictRecord,
    });

    return conflictRecord;
  },

  /**
   * Recalculates and updates the unresolved conflict count in sync_meta.
   */
  async updateConflictCount(userId, targetDb) {
    if (!targetDb.conflicts || !targetDb.syncMeta) return 0;

    const count = await targetDb.conflicts
      .where('status')
      .equals(CONFLICT_STATUS.PENDING_RESOLUTION)
      .filter((c) => c.userId === userId)
      .count();

    const now = new Date().toISOString();
    await targetDb.syncMeta.put({
      key: SYNC_META_KEYS.CONFLICT_COUNT,
      value: count,
      updatedAt: now,
    });

    return count;
  },

  /**
   * Returns unresolved conflict count for user.
   */
  async getUnresolvedConflictCount(userId, targetDb) {
    if (!targetDb.conflicts) return 0;
    return await targetDb.conflicts
      .where('status')
      .equals(CONFLICT_STATUS.PENDING_RESOLUTION)
      .filter((c) => c.userId === userId)
      .count();
  },

  /**
   * Retrieves all unresolved conflicts for the user.
   */
  async getUnresolvedConflicts(userId, targetDb) {
    if (!targetDb.conflicts) return [];
    return await targetDb.conflicts
      .where('status')
      .equals(CONFLICT_STATUS.PENDING_RESOLUTION)
      .filter((c) => c.userId === userId)
      .reverse()
      .sortBy('detectedAt');
  },

  /**
   * Retrieves conflict history (all resolved conflicts).
   */
  async getConflictHistory(userId, targetDb) {
    if (!targetDb.conflicts) return [];
    const all = await targetDb.conflicts
      .where('userId')
      .equals(userId)
      .toArray();

    return all
      .filter((c) => c.status !== CONFLICT_STATUS.PENDING_RESOLUTION)
      .sort((a, b) => new Date(b.resolvedAt || b.updatedAt) - new Date(a.resolvedAt || a.updatedAt));
  },
};
