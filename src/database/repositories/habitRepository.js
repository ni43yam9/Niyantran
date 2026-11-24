import { db } from '../db';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

export const habitRepository = {
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
    const includeArchived = Boolean(params.includeArchived);

    let habits = await targetDb.habits.where('userId').equals(userId).toArray();

    if (!includeDeleted) {
      habits = habits.filter((h) => !h.isDeleted);
    }
    if (!includeArchived) {
      habits = habits.filter((h) => !h.archived);
    }
    if (params.category) {
      habits = habits.filter((h) => h.category === params.category);
    }

    // Attach completedDates and logs from habitLogs table
    const allLogs = await targetDb.habitLogs
      .where('userId')
      .equals(userId)
      .filter((l) => !l.isDeleted)
      .toArray();

    const logsByHabit = {};
    for (const log of allLogs) {
      if (!logsByHabit[log.habitId]) logsByHabit[log.habitId] = [];
      logsByHabit[log.habitId].push(log);
    }

    return habits.map((h) => {
      const hLogs = logsByHabit[h.id] || [];
      const completedDates = {};
      for (const l of hLogs) {
        if (l.completed) {
          completedDates[l.logDate] = true;
        }
      }
      return {
        ...h,
        completed_dates: completedDates,
        completedDates,
        logs: hLogs,
      };
    });
  },

  async getById(id, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const habit = await targetDb.habits.get(id);
    if (!habit || habit.userId !== activeUserId || habit.isDeleted) {
      return null;
    }

    const hLogs = await targetDb.habitLogs
      .where('userId')
      .equals(activeUserId)
      .filter((l) => l.habitId === id && !l.isDeleted)
      .toArray();

    const completedDates = {};
    for (const l of hLogs) {
      if (l.completed) {
        completedDates[l.logDate] = true;
      }
    }

    return {
      ...habit,
      completed_dates: completedDates,
      completedDates,
      logs: hLogs,
    };
  },

  async save(habitData, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.habits) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const existing = habitData.id ? await targetDb.habits.get(habitData.id) : null;
    const id = habitData.id || `h-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const version = habitData.version != null ? Number(habitData.version) : (existing ? (existing.version || 1) + 1 : 1);

    const record = {
      id,
      userId: activeUserId,
      deviceUuid: targetDb.getClientDeviceUUID(),
      name: habitData.name?.trim() || '',
      target: habitData.target || '',
      category: habitData.category || 'General',
      frequency: habitData.frequency || 'Daily',
      baseStreak: habitData.baseStreak || habitData.base_streak || 0,
      archived: Boolean(habitData.archived),
      version,
      isDeleted: habitData.isDeleted ? 1 : 0,
      deletedAt: habitData.deletedAt || null,
      createdAt: existing ? existing.createdAt : habitData.createdAt || now,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.habits, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.habits];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.habits.put(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.HABIT,
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

  async saveBatch(habitsList, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.habits) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.habits, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.habits];

    return await targetDb.transaction('rw', tables, async () => {
      const records = [];
      for (const h of habitsList) {
        const id = h.id || `h-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const record = {
          id,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
          name: h.name?.trim() || '',
          target: h.target || '',
          category: h.category || 'General',
          frequency: h.frequency || 'Daily',
          baseStreak: h.baseStreak || h.base_streak || 0,
          archived: Boolean(h.archived),
          version: h.version || 1,
          isDeleted: h.isDeleted ? 1 : 0,
          deletedAt: h.deletedAt || h.deleted_at || null,
          createdAt: h.createdAt || h.created_at || now,
          updatedAt: h.updatedAt || h.updated_at || now,
        };
        records.push(record);

        if (options.trackChange !== false && targetDb.syncQueue) {
          await changeTracker.recordChange(targetDb, {
            entityType: ENTITY_TYPES.HABIT,
            entityId: record.id,
            operation: SYNC_OPERATIONS.CREATE,
            entityVersion: record.version,
            payload: record,
            userId: activeUserId,
            deviceUuid: record.deviceUuid,
          });
        }
      }

      await targetDb.habits.bulkPut(records);
      return records;
    });
  },

  async update(id, updates, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.habits) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.habits.get(id);
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
      ? [targetDb.habits, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.habits];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.habits.put(updatedRecord);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.HABIT,
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

    if (optionsOrTargetDb && optionsOrTargetDb.habits) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.habits.get(id);
    if (!existing || existing.userId !== activeUserId) {
      return false;
    }

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.habits, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.habits];

    return await targetDb.transaction('rw', tables, async () => {
      if (options.softDelete !== false) {
        await targetDb.habits.update(id, {
          isDeleted: 1,
          deletedAt: now,
          version: nextVersion,
          updatedAt: now,
        });
      } else {
        await targetDb.habits.delete(id);
      }

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.HABIT,
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

  async toggleLog(habitId, logDate, completed = null, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.habits) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const habit = await targetDb.habits.get(habitId);
    if (!habit || habit.userId !== activeUserId || habit.isDeleted) {
      return null;
    }

    const now = new Date().toISOString();

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.habits, targetDb.habitLogs, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.habits, targetDb.habitLogs];

    return await targetDb.transaction('rw', tables, async () => {
      const existingLogs = await targetDb.habitLogs
        .where('[habitId+logDate]')
        .equals([habitId, logDate])
        .toArray();

      const existing = existingLogs.find((l) => l.userId === activeUserId && !l.isDeleted);
      let newCompletedState = true;
      let logRecord = null;
      let logOperation = SYNC_OPERATIONS.CREATE;

      if (existing) {
        newCompletedState = completed !== null ? completed : !existing.completed;
        const nextLogVersion = (existing.version || 1) + 1;
        logRecord = {
          ...existing,
          completed: newCompletedState,
          version: nextLogVersion,
          updatedAt: now,
        };
        await targetDb.habitLogs.update(existing.id, {
          completed: newCompletedState,
          version: nextLogVersion,
          updatedAt: now,
        });
        logOperation = SYNC_OPERATIONS.UPDATE;
      } else {
        newCompletedState = completed !== null ? completed : true;
        const logId = `hl-${habitId}-${logDate}`;
        logRecord = {
          id: logId,
          habitId,
          userId: activeUserId,
          logDate,
          completed: newCompletedState,
          version: 1,
          isDeleted: 0,
          deletedAt: null,
          createdAt: now,
          updatedAt: now,
        };
        await targetDb.habitLogs.put(logRecord);
        logOperation = SYNC_OPERATIONS.CREATE;
      }

      // Update parent habit version
      const nextHabitVersion = (habit.version || 1) + 1;
      await targetDb.habits.update(habitId, {
        version: nextHabitVersion,
        updatedAt: now,
      });

      // Track queue changes
      if (options.trackChange !== false && targetDb.syncQueue) {
        // Track habit log change
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.HABIT_LOG,
          entityId: logRecord.id,
          operation: logOperation,
          entityVersion: logRecord.version,
          previousVersion: existing ? existing.version : null,
          payload: logRecord,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
        });

        // Track parent habit update
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.HABIT,
          entityId: habitId,
          operation: SYNC_OPERATIONS.UPDATE,
          entityVersion: nextHabitVersion,
          previousVersion: habit.version,
          payload: { id: habitId, version: nextHabitVersion, updatedAt: now },
          userId: activeUserId,
          deviceUuid: habit.deviceUuid || targetDb.getClientDeviceUUID(),
        });
      }

      return await this.getById(habitId, activeUserId, targetDb);
    });
  },

  // Ergonomic aliases matching frontend service patterns
  async createHabit(habitData, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.save(habitData, userId, options, targetDb);
  },

  async updateHabit(id, updates, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.update(id, updates, userId, options, targetDb);
  },

  async deleteHabit(id, userId = null, options = { softDelete: true, trackChange: true }, targetDb = db) {
    return this.delete(id, userId, options, targetDb);
  },

  async bulkUpsert(habitsList, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.saveBatch(habitsList, userId, options, targetDb);
  },
};
