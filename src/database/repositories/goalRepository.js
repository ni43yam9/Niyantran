import { db } from '../db';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

export const goalRepository = {
  async getAll(params = {}, userIdOrTargetDb = db, maybeDb = db) {
    let userId = null;
    let targetDb = db;

    if (typeof userIdOrTargetDb === 'string') {
      userId = userIdOrTargetDb;
      targetDb = maybeDb || db;
    } else if (userIdOrTargetDb && userIdOrTargetDb.getActiveUserId) {
      targetDb = userIdOrTargetDb;
    }

    if (!userId) {
      userId = params.userId || targetDb.getActiveUserId();
    }

    const includeDeleted = Boolean(params.includeDeleted);

    let goals = await targetDb.goals.where('userId').equals(userId).toArray();

    if (!includeDeleted) {
      goals = goals.filter((g) => !g.isDeleted);
    }

    if (params.status) {
      goals = goals.filter((g) => g.status === params.status);
    }
    if (params.priority) {
      goals = goals.filter((g) => g.priority === params.priority);
    }
    if (params.goalType || params.type) {
      const type = params.goalType || params.type;
      goals = goals.filter((g) => g.goalType === type);
    }
    if (params.category) {
      goals = goals.filter((g) => g.category === params.category);
    }
    if (params.search) {
      const q = params.search.trim().toLowerCase();
      goals = goals.filter(
        (g) =>
          (g.title && g.title.toLowerCase().includes(q)) ||
          (g.description && g.description.toLowerCase().includes(q)) ||
          (g.keyMilestone && g.keyMilestone.toLowerCase().includes(q))
      );
    }

    // Default sorting: targetDate ascending
    goals.sort((a, b) => {
      if (a.targetDate && b.targetDate) {
        return a.targetDate.localeCompare(b.targetDate);
      }
      return (b.createdAt || '').localeCompare(a.createdAt || '');
    });

    if (params.skip !== undefined || params.limit !== undefined) {
      const skip = params.skip || 0;
      const limit = params.limit || 100;
      goals = goals.slice(skip, skip + limit);
    }

    return goals;
  },

  async getById(id, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const goal = await targetDb.goals.get(id);
    if (!goal || goal.userId !== activeUserId || goal.isDeleted) {
      return null;
    }
    return goal;
  },

  async save(goalData, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.goals) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const existing = goalData.id ? await targetDb.goals.get(goalData.id) : null;
    const id = goalData.id || `g-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const version = goalData.version != null ? Number(goalData.version) : (existing ? (existing.version || 1) + 1 : 1);

    const record = {
      id,
      userId: activeUserId,
      deviceUuid: targetDb.getClientDeviceUUID(),
      title: goalData.title?.trim() || '',
      description: goalData.description?.trim() || '',
      goalType: goalData.goalType || goalData.goal_type || goalData.type || 'Short-Term',
      category: goalData.category || 'Coding',
      priority: goalData.priority || 'Medium',
      status: goalData.status || 'In Progress',
      startDate: goalData.startDate || goalData.start_date || now.slice(0, 10),
      targetDate: goalData.targetDate || goalData.target_date || now.slice(0, 10),
      progress: typeof goalData.progress === 'number'
        ? goalData.progress
        : (typeof goalData.progressPercentage === 'number' ? goalData.progressPercentage : 0),
      keyMilestone: goalData.keyMilestone || goalData.key_milestone || '',
      version,
      isDeleted: goalData.isDeleted ? 1 : 0,
      deletedAt: goalData.deletedAt || null,
      createdAt: existing ? existing.createdAt : goalData.createdAt || now,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.goals, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.goals];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.goals.put(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.GOAL,
          entityId: record.id,
          operation: existing ? SYNC_OPERATIONS.UPDATE : SYNC_OPERATIONS.CREATE,
          entityVersion: record.version,
          previousVersion: existing ? existing.version : null,
          payload: record,
          userId: activeUserId,
          deviceUuid: record.deviceUuid,
        });
      }

      return record;
    });
  },

  async saveBatch(goalsList, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.goals) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.goals, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.goals];

    return await targetDb.transaction('rw', tables, async () => {
      const records = [];
      for (const g of goalsList) {
        const id = g.id || `g-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const record = {
          id,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
          title: g.title?.trim() || '',
          description: g.description?.trim() || '',
          goalType: g.goalType || g.goal_type || g.type || 'Short-Term',
          category: g.category || 'Coding',
          priority: g.priority || 'Medium',
          status: g.status || 'In Progress',
          startDate: g.startDate || g.start_date || now.slice(0, 10),
          targetDate: g.targetDate || g.target_date || now.slice(0, 10),
          progress: typeof g.progress === 'number' ? g.progress : 0,
          keyMilestone: g.keyMilestone || g.key_milestone || '',
          version: g.version || 1,
          isDeleted: g.isDeleted ? 1 : 0,
          deletedAt: g.deletedAt || g.deleted_at || null,
          createdAt: g.createdAt || g.created_at || now,
          updatedAt: g.updatedAt || g.updated_at || now,
        };
        records.push(record);

        if (options.trackChange !== false && targetDb.syncQueue) {
          await changeTracker.recordChange(targetDb, {
            entityType: ENTITY_TYPES.GOAL,
            entityId: record.id,
            operation: SYNC_OPERATIONS.CREATE,
            entityVersion: record.version,
            payload: record,
            userId: activeUserId,
            deviceUuid: record.deviceUuid,
          });
        }
      }

      await targetDb.goals.bulkPut(records);
      return records;
    });
  },

  async update(id, updates, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.goals) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.goals.get(id);
    if (!existing || existing.userId !== activeUserId || existing.isDeleted) {
      return null;
    }

    const now = new Date().toISOString();
    const updatedRecord = {
      ...existing,
      ...updates,
      version: (existing.version || 1) + 1,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.goals, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.goals];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.goals.put(updatedRecord);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.GOAL,
          entityId: updatedRecord.id,
          operation: SYNC_OPERATIONS.UPDATE,
          entityVersion: updatedRecord.version,
          previousVersion: existing.version,
          payload: updatedRecord,
          userId: activeUserId,
          deviceUuid: updatedRecord.deviceUuid,
        });
      }

      return updatedRecord;
    });
  },

  async delete(id, userId = null, optionsOrTargetDb = { softDelete: true, trackChange: true }, maybeDb = db) {
    let options = { softDelete: true, trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.goals) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.goals.get(id);
    if (!existing || existing.userId !== activeUserId) {
      return false;
    }

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.goals, targetDb.tasks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.goals, targetDb.tasks];

    return await targetDb.transaction('rw', tables, async () => {
      // Unlink associated tasks
      const linkedTasks = await targetDb.tasks
        .where('userId')
        .equals(activeUserId)
        .filter((t) => t.goalId === id)
        .toArray();

      for (const t of linkedTasks) {
        await targetDb.tasks.update(t.id, {
          goalId: null,
          updatedAt: now,
          version: (t.version || 1) + 1,
        });
      }

      if (options.softDelete !== false) {
        await targetDb.goals.update(id, {
          isDeleted: 1,
          deletedAt: now,
          version: nextVersion,
          updatedAt: now,
        });
      } else {
        await targetDb.goals.delete(id);
      }

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.GOAL,
          entityId: id,
          operation: SYNC_OPERATIONS.DELETE,
          entityVersion: nextVersion,
          previousVersion: existing.version,
          payload: {
            id,
            isDeleted: 1,
            deletedAt: now,
            version: nextVersion,
          },
          userId: activeUserId,
          deviceUuid: existing.deviceUuid || targetDb.getClientDeviceUUID(),
        });
      }

      return true;
    });
  },

  async updateProgress(id, progress, status = null, userId = null, options = { trackChange: true }, targetDb = db) {
    const updates = { progress };
    if (status) {
      updates.status = status;
    } else if (progress === 100) {
      updates.status = 'Completed';
    }
    return this.update(id, updates, userId, options, targetDb);
  },

  // Ergonomic aliases matching frontend service patterns
  async createGoal(goalData, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.save(goalData, userId, options, targetDb);
  },

  async updateGoal(id, updates, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.update(id, updates, userId, options, targetDb);
  },

  async deleteGoal(id, userId = null, options = { softDelete: true, trackChange: true }, targetDb = db) {
    return this.delete(id, userId, options, targetDb);
  },

  async bulkUpsert(goalsList, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.saveBatch(goalsList, userId, options, targetDb);
  },
};
