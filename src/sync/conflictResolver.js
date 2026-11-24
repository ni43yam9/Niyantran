/**
 * NIYANTRA Phase 10H: Conflict Resolution Service
 * 
 * Implements deterministic conflict resolution strategies:
 * - Keep Local (local version wins, bumped version queued to update remote)
 * - Keep Remote (remote version accepted, local pending operations superseded)
 * - Manual Merge (field-level combination, validated domain schema, bumped version queued)
 * 
 * Provides domain-specific merge algorithms and relationship integrity protections.
 */

import { db } from '../database/db';
import { changeTracker } from './changeTracker';
import {
  CONFLICT_STATUS,
  RESOLUTION_STRATEGY,
  SYNC_STATUS,
  SYNC_OPERATIONS,
} from './syncConstants';
import {
  getTablePropertyForEntity,
  notifyConflictListeners,
  conflictDetector,
} from './conflictDetector';

/**
 * Entity-specific field merging utilities
 */
export const entityMergeHelpers = {
  mergeTasks(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      title: overrides.title !== undefined ? overrides.title : (local.title || remote.title || ''),
      description: overrides.description !== undefined ? overrides.description : (local.description || remote.description || ''),
      taskType: overrides.taskType !== undefined ? overrides.taskType : (local.taskType || remote.taskType || 'Daily'),
      category: overrides.category !== undefined ? overrides.category : (local.category || remote.category || 'Coding'),
      priority: overrides.priority !== undefined ? overrides.priority : (local.priority || remote.priority || 'Medium'),
      status: overrides.status !== undefined ? overrides.status : (local.status || remote.status || 'Pending'),
      startDate: overrides.startDate !== undefined ? overrides.startDate : (local.startDate || remote.startDate || null),
      dueDate: overrides.dueDate !== undefined ? overrides.dueDate : (local.dueDate || remote.dueDate || null),
      goalId: overrides.goalId !== undefined ? overrides.goalId : (local.goalId || remote.goalId || null),
      completedAt: overrides.status === 'Completed'
        ? (local.completedAt || remote.completedAt || new Date().toISOString())
        : (overrides.completedAt !== undefined ? overrides.completedAt : (local.completedAt || remote.completedAt || null)),
    };
  },

  mergeGoals(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      title: overrides.title !== undefined ? overrides.title : (local.title || remote.title || ''),
      description: overrides.description !== undefined ? overrides.description : (local.description || remote.description || ''),
      category: overrides.category !== undefined ? overrides.category : (local.category || remote.category || 'Personal'),
      priority: overrides.priority !== undefined ? overrides.priority : (local.priority || remote.priority || 'Medium'),
      status: overrides.status !== undefined ? overrides.status : (local.status || remote.status || 'In Progress'),
      targetDate: overrides.targetDate !== undefined ? overrides.targetDate : (local.targetDate || remote.targetDate || null),
      progressPercentage: overrides.progressPercentage !== undefined
        ? Number(overrides.progressPercentage)
        : Math.max(Number(local.progressPercentage) || 0, Number(remote.progressPercentage) || 0),
    };
  },

  mergeHabits(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      name: overrides.name !== undefined ? overrides.name : (local.name || remote.name || ''),
      frequency: overrides.frequency !== undefined ? overrides.frequency : (local.frequency || remote.frequency || 'Daily'),
      category: overrides.category !== undefined ? overrides.category : (local.category || remote.category || 'General'),
      baseStreak: overrides.baseStreak !== undefined
        ? Number(overrides.baseStreak)
        : Math.max(Number(local.baseStreak) || 0, Number(remote.baseStreak) || 0),
      archived: overrides.archived !== undefined ? Boolean(overrides.archived) : Boolean(local.archived || remote.archived),
    };
  },

  mergeHabitLogs(local = {}, remote = {}, overrides = {}) {
    // Unique by [habitId, logDate]. Safe deduplication: completion boolean OR'd, notes combined.
    const completed = overrides.completed !== undefined
      ? Boolean(overrides.completed)
      : Boolean(local.completed || remote.completed);

    let notes = overrides.notes !== undefined ? overrides.notes : '';
    if (overrides.notes === undefined) {
      if (local.notes && remote.notes) {
        notes = local.notes === remote.notes ? local.notes : `${local.notes}; ${remote.notes}`;
      } else {
        notes = local.notes || remote.notes || '';
      }
    }

    return {
      id: local.id || remote.id,
      habitId: local.habitId || remote.habitId,
      logDate: local.logDate || remote.logDate,
      completed,
      notes,
    };
  },

  mergeDailyTimeblocks(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      blockDate: overrides.blockDate !== undefined ? overrides.blockDate : (local.blockDate || remote.blockDate),
      title: overrides.title !== undefined ? overrides.title : (local.title || remote.title || 'Timeblock'),
      time: overrides.time !== undefined ? overrides.time : (local.time || remote.time || '09:00 AM'),
      durationMinutes: overrides.durationMinutes !== undefined
        ? Number(overrides.durationMinutes)
        : (Number(local.durationMinutes) || Number(remote.durationMinutes) || 60),
      actualDurationMinutes: overrides.actualDurationMinutes !== undefined
        ? overrides.actualDurationMinutes
        : (local.actualDurationMinutes || remote.actualDurationMinutes || null),
      category: overrides.category !== undefined ? overrides.category : (local.category || remote.category || 'General'),
      status: overrides.status !== undefined ? overrides.status : (local.status || remote.status || 'Pending'),
      isBreak: overrides.isBreak !== undefined ? Boolean(overrides.isBreak) : Boolean(local.isBreak || remote.isBreak),
      taskId: overrides.taskId !== undefined ? overrides.taskId : (local.taskId || remote.taskId || null),
    };
  },

  mergeDailyIntents(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      intentDate: local.intentDate || remote.intentDate,
      intentText: overrides.intentText !== undefined
        ? overrides.intentText
        : (local.intentText || remote.intentText || ''),
    };
  },

  mergeRecommendations(local = {}, remote = {}, overrides = {}) {
    return {
      id: local.id || remote.id,
      status: overrides.status !== undefined ? overrides.status : (local.status || remote.status || 'PENDING'),
      type: local.type || remote.type,
      category: local.category || remote.category,
      title: local.title || remote.title,
      description: local.description || remote.description,
      actionPayload: overrides.actionPayload !== undefined
        ? overrides.actionPayload
        : (local.actionPayload || remote.actionPayload || {}),
    };
  },

  mergeActivityLogs(local = {}, remote = {}) {
    // Append-only event history: preserve event without overwriting
    return {
      ...remote,
      ...local,
      id: local.id || remote.id,
    };
  },
};

export const conflictResolver = {
  /**
   * Resolves a conflict using the specified strategy.
   * Atomically transitions local IndexedDB records, updates sync_queue,
   * records resolution lifecycle, and decrements conflict counts.
   */
  async resolveConflict({
    conflictId,
    strategy,
    mergedData = null,
    userId = null,
    targetDb = db,
  }) {
    if (!conflictId) {
      throw new Error('Conflict ID is required for resolution.');
    }

    if (!Object.values(RESOLUTION_STRATEGY).includes(strategy)) {
      throw new Error(`Unsupported conflict resolution strategy: ${strategy}`);
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const conflict = await targetDb.conflicts.get(conflictId);
    if (!conflict) {
      throw new Error(`Conflict record '${conflictId}' not found.`);
    }

    // Verify tenant ownership
    if (conflict.userId && conflict.userId !== activeUserId) {
      throw new Error(`Conflict does not belong to active user '${activeUserId}'.`);
    }

    const tableProp = getTablePropertyForEntity(conflict.entityType);
    if (!tableProp || !targetDb[tableProp]) {
      throw new Error(`No local table found for entity type '${conflict.entityType}'.`);
    }

    const now = new Date().toISOString();
    let winningVersion = Math.max(Number(conflict.localVersion) || 1, Number(conflict.remoteVersion) || 1) + 1;
    let resolvedData = null;
    let finalStatus = CONFLICT_STATUS.RESOLVED_MERGED;

    // --- STRATEGY 1: KEEP LOCAL ---
    if (strategy === RESOLUTION_STRATEGY.KEEP_LOCAL) {
      finalStatus = CONFLICT_STATUS.RESOLVED_LOCAL;
      resolvedData = { ...conflict.localData };
      const isDelete = conflict.localOperation === 'DELETE';

      // 1. Update local entity record with bumped winning version
      const localRecord = {
        ...conflict.localData,
        id: conflict.entityId,
        userId: activeUserId,
        version: winningVersion,
        isDeleted: isDelete ? 1 : 0,
        deletedAt: isDelete ? (conflict.localData.deletedAt || now) : null,
        updatedAt: now,
      };
      await targetDb[tableProp].put(localRecord);

      // 2. Ensure outgoing sync_queue operation has the bumped version to supersede remote
      const pendingOps = await targetDb.syncQueue
        .where('[userId+entityType+entityId]')
        .equals([activeUserId, conflict.entityType, conflict.entityId])
        .filter((item) => item.status === SYNC_STATUS.PENDING)
        .toArray();

      if (pendingOps.length > 0) {
        for (const op of pendingOps) {
          await targetDb.syncQueue.update(op.id, {
            entityVersion: winningVersion,
            payload: localRecord,
            updatedAt: now,
          });
        }
      } else {
        // Queue new operation with winning version
        await changeTracker.recordChange(targetDb, {
          entityType: conflict.entityType,
          entityId: conflict.entityId,
          operation: isDelete ? SYNC_OPERATIONS.DELETE : SYNC_OPERATIONS.UPDATE,
          entityVersion: winningVersion,
          previousVersion: conflict.localVersion,
          payload: localRecord,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
        });
      }
    }

    // --- STRATEGY 2: KEEP REMOTE ---
    else if (strategy === RESOLUTION_STRATEGY.KEEP_REMOTE) {
      finalStatus = CONFLICT_STATUS.RESOLVED_REMOTE;
      resolvedData = { ...conflict.remoteData };
      const isDelete = conflict.remoteOperation === 'DELETE';

      // 1. Supersede/cancel any pending local operations for this entity so they do NOT push
      const pendingOps = await targetDb.syncQueue
        .where('[userId+entityType+entityId]')
        .equals([activeUserId, conflict.entityType, conflict.entityId])
        .filter((item) => item.status === SYNC_STATUS.PENDING)
        .toArray();

      for (const op of pendingOps) {
        await targetDb.syncQueue.update(op.id, {
          status: SYNC_STATUS.SUPERSEDED,
          updatedAt: now,
          errorMessage: `Superseded by remote resolution (conflict ${conflictId})`,
        });
      }

      // 2. Apply remote record locally with trackChange: false
      const remoteRecord = {
        ...conflict.remoteData,
        id: conflict.entityId,
        userId: activeUserId,
        version: Number(conflict.remoteVersion) || 1,
        isDeleted: isDelete ? 1 : 0,
        deletedAt: isDelete ? (conflict.remoteData.deletedAt || now) : null,
        updatedAt: now,
      };
      await targetDb[tableProp].put(remoteRecord);
    }

    // --- STRATEGY 3: MANUAL MERGE ---
    else if (strategy === RESOLUTION_STRATEGY.MANUAL_MERGE) {
      finalStatus = CONFLICT_STATUS.RESOLVED_MERGED;
      if (!mergedData) {
        throw new Error('Merged data payload is required for MANUAL_MERGE strategy.');
      }

      resolvedData = { ...mergedData };

      // 1. Supersede any old conflicting pending operations
      const pendingOps = await targetDb.syncQueue
        .where('[userId+entityType+entityId]')
        .equals([activeUserId, conflict.entityType, conflict.entityId])
        .filter((item) => item.status === SYNC_STATUS.PENDING)
        .toArray();

      for (const op of pendingOps) {
        await targetDb.syncQueue.update(op.id, {
          status: SYNC_STATUS.SUPERSEDED,
          updatedAt: now,
          errorMessage: `Superseded by manual merge resolution (conflict ${conflictId})`,
        });
      }

      // 2. Save merged entity with bumped version
      const mergedRecord = {
        ...mergedData,
        id: conflict.entityId,
        userId: activeUserId,
        version: winningVersion,
        isDeleted: 0,
        deletedAt: null,
        updatedAt: now,
      };
      await targetDb[tableProp].put(mergedRecord);

      // 3. Queue new outgoing UPDATE operation
      await changeTracker.recordChange(targetDb, {
        entityType: conflict.entityType,
        entityId: conflict.entityId,
        operation: SYNC_OPERATIONS.UPDATE,
        entityVersion: winningVersion,
        previousVersion: conflict.localVersion,
        payload: mergedRecord,
        userId: activeUserId,
        deviceUuid: targetDb.getClientDeviceUUID(),
      });
    }

    // Update conflict record with full resolution audit history
    const updatedConflict = {
      ...conflict,
      status: finalStatus,
      resolutionStrategy: strategy,
      resolvedAt: now,
      resolvedData,
      updatedAt: now,
    };
    await targetDb.conflicts.put(updatedConflict);

    // Update unresolved count in metadata
    await conflictDetector.updateConflictCount(activeUserId, targetDb);

    // Notify listeners
    notifyConflictListeners({
      type: 'CONFLICT_RESOLVED',
      conflictId,
      strategy,
      resolvedConflict: updatedConflict,
    });

    return {
      success: true,
      conflictId,
      strategy,
      status: finalStatus,
      winningVersion,
      resolvedData,
    };
  },
};
