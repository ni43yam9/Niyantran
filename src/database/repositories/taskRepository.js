import { db } from '../db';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

export const taskRepository = {
  /**
   * Retrieves tasks with optional filtering, search, and pagination.
   * Scoped strictly by user ID (defaulting to active user).
   */
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

    let collection = targetDb.tasks.where('userId').equals(userId);
    let tasks = await collection.toArray();

    if (!includeDeleted) {
      tasks = tasks.filter((t) => !t.isDeleted);
    }

    if (params.status) {
      tasks = tasks.filter((t) => t.status === params.status);
    }
    if (params.priority) {
      tasks = tasks.filter((t) => t.priority === params.priority);
    }
    if (params.category) {
      tasks = tasks.filter((t) => t.category === params.category);
    }
    if (params.taskType) {
      tasks = tasks.filter((t) => t.taskType === params.taskType);
    }
    if (params.search) {
      const q = params.search.trim().toLowerCase();
      tasks = tasks.filter(
        (t) =>
          (t.title && t.title.toLowerCase().includes(q)) ||
          (t.description && t.description.toLowerCase().includes(q))
      );
    }

    const todayStr = new Date().toISOString().slice(0, 10);

    if (params.isToday === true) {
      tasks = tasks.filter((t) => t.dueDate === todayStr || t.startDate === todayStr);
    }

    if (params.isOverdue === true) {
      tasks = tasks.filter(
        (t) => t.status !== 'Completed' && t.dueDate && t.dueDate < todayStr
      );
    }

    // Default sorting: status (Pending/In Progress first), then dueDate asc, then createdAt desc
    tasks.sort((a, b) => {
      const statusOrder = { Pending: 1, 'In Progress': 2, Completed: 3 };
      const diffStatus = (statusOrder[a.status] || 2) - (statusOrder[b.status] || 2);
      if (diffStatus !== 0) return diffStatus;

      if (a.dueDate && b.dueDate) {
        const diffDate = a.dueDate.localeCompare(b.dueDate);
        if (diffDate !== 0) return diffDate;
      }
      return (b.createdAt || '').localeCompare(a.createdAt || '');
    });

    if (params.skip !== undefined || params.limit !== undefined) {
      const skip = params.skip || 0;
      const limit = params.limit || 100;
      tasks = tasks.slice(skip, skip + limit);
    }

    return tasks;
  },

  async getById(id, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const task = await targetDb.tasks.get(id);
    if (!task || task.userId !== activeUserId || task.isDeleted) {
      return null;
    }
    return task;
  },

  async save(taskData, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.tasks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const existing = taskData.id ? await targetDb.tasks.get(taskData.id) : null;
    const id = taskData.id || `t-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const version = taskData.version != null ? Number(taskData.version) : (existing ? (existing.version || 1) + 1 : 1);

    const record = {
      id,
      userId: activeUserId,
      deviceUuid: targetDb.getClientDeviceUUID(),
      title: taskData.title?.trim() || '',
      description: taskData.description?.trim() || '',
      taskType: taskData.taskType || taskData.task_type || 'Daily',
      category: taskData.category || 'Coding',
      priority: taskData.priority || 'Medium',
      status: taskData.status || 'Pending',
      startDate: taskData.startDate || taskData.start_date || null,
      dueDate: taskData.dueDate || taskData.due_date || null,
      goalId: taskData.goalId || taskData.goal_id || null,
      completedAt: taskData.status === 'Completed' ? taskData.completedAt || now : null,
      version,
      isDeleted: taskData.isDeleted ? 1 : 0,
      deletedAt: taskData.deletedAt || null,
      createdAt: existing ? existing.createdAt : taskData.createdAt || now,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.tasks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.tasks];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.tasks.put(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.TASK,
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

  async saveBatch(tasksList, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.tasks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.tasks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.tasks];

    return await targetDb.transaction('rw', tables, async () => {
      const records = [];
      for (const t of tasksList) {
        const id = t.id || `t-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const record = {
          id,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
          title: t.title?.trim() || '',
          description: t.description?.trim() || '',
          taskType: t.taskType || t.task_type || 'Daily',
          category: t.category || 'Coding',
          priority: t.priority || 'Medium',
          status: t.status || 'Pending',
          startDate: t.startDate || t.start_date || null,
          dueDate: t.dueDate || t.due_date || null,
          goalId: t.goalId || t.goal_id || null,
          completedAt: t.status === 'Completed' ? t.completedAt || now : null,
          version: t.version || 1,
          isDeleted: t.isDeleted ? 1 : 0,
          deletedAt: t.deletedAt || t.deleted_at || null,
          createdAt: t.createdAt || t.created_at || now,
          updatedAt: t.updatedAt || t.updated_at || now,
        };
        records.push(record);

        if (options.trackChange !== false && targetDb.syncQueue) {
          await changeTracker.recordChange(targetDb, {
            entityType: ENTITY_TYPES.TASK,
            entityId: record.id,
            operation: SYNC_OPERATIONS.CREATE,
            entityVersion: record.version,
            payload: record,
            userId: activeUserId,
            deviceUuid: record.deviceUuid,
          });
        }
      }

      await targetDb.tasks.bulkPut(records);
      return records;
    });
  },

  async update(id, updates, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.tasks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.tasks.get(id);
    if (!existing || existing.userId !== activeUserId || existing.isDeleted) {
      return null;
    }

    const now = new Date().toISOString();
    const updatedStatus = updates.status !== undefined ? updates.status : existing.status;
    let completedAt = existing.completedAt;
    if (updatedStatus === 'Completed' && existing.status !== 'Completed') {
      completedAt = now;
    } else if (updatedStatus !== 'Completed') {
      completedAt = null;
    }

    const updatedRecord = {
      ...existing,
      ...updates,
      status: updatedStatus,
      completedAt,
      completionDate: completedAt,
      version: (existing.version || 1) + 1,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.tasks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.tasks];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.tasks.put(updatedRecord);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.TASK,
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

    if (optionsOrTargetDb && optionsOrTargetDb.tasks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.tasks.get(id);
    if (!existing || existing.userId !== activeUserId) {
      return false;
    }

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.tasks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.tasks];

    return await targetDb.transaction('rw', tables, async () => {
      if (options.softDelete !== false) {
        await targetDb.tasks.update(id, {
          isDeleted: 1,
          deletedAt: now,
          version: nextVersion,
          updatedAt: now,
        });
      } else {
        await targetDb.tasks.delete(id);
      }

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.TASK,
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

  async markComplete(id, userId = null, targetDb = db) {
    return this.update(id, { status: 'Completed' }, userId, { trackChange: true }, targetDb);
  },

  async markPending(id, userId = null, targetDb = db) {
    return this.update(id, { status: 'Pending' }, userId, { trackChange: true }, targetDb);
  },

  async toggleCompletion(id, userId = null, targetDb = db) {
    const existing = await this.getById(id, userId, targetDb);
    if (!existing) return null;
    const isCompleted = existing.status === 'Completed';
    return await this.update(
      id,
      {
        status: isCompleted ? 'Pending' : 'Completed',
        completedAt: isCompleted ? null : new Date().toISOString(),
      },
      userId,
      { trackChange: true },
      targetDb
    );
  },

  // Ergonomic aliases matching frontend service patterns
  async createTask(taskData, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.save(taskData, userId, options, targetDb);
  },

  async updateTask(id, updates, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.update(id, updates, userId, options, targetDb);
  },

  async deleteTask(id, userId = null, options = { softDelete: true, trackChange: true }, targetDb = db) {
    return this.delete(id, userId, options, targetDb);
  },

  async bulkUpsert(tasksList, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.saveBatch(tasksList, userId, options, targetDb);
  },

  async count(userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    return await targetDb.tasks
      .where('userId')
      .equals(activeUserId)
      .filter((t) => !t.isDeleted)
      .count();
  },
};
