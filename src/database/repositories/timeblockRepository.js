import { db } from '../db';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

export const timeblockRepository = {
  async getByDate(blockDate, statusOrUserId = null, maybeUserId = null, targetDb = db) {
    let status = null;
    let userId = null;

    if (
      typeof statusOrUserId === 'string' &&
      (statusOrUserId.includes('user') || statusOrUserId.includes('-') || statusOrUserId === 'default_user')
    ) {
      userId = statusOrUserId;
    } else {
      status = statusOrUserId;
      userId = maybeUserId;
    }

    const activeUserId = userId || targetDb.getActiveUserId();

    let blocks = await targetDb.dailyTimeblocks
      .where('userId')
      .equals(activeUserId)
      .filter((b) => b.blockDate === blockDate && !b.isDeleted)
      .toArray();

    if (status) {
      blocks = blocks.filter((b) => b.status === status);
    }

    // Sort by startTime
    blocks.sort((a, b) => (a.startTime || '').localeCompare(b.startTime || ''));
    return blocks;
  },

  async getById(id, userId = null, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const block = await targetDb.dailyTimeblocks.get(id);
    if (!block || block.userId !== activeUserId || block.isDeleted) {
      return null;
    }
    return block;
  },

  async save(blockData, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.dailyTimeblocks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const existing = blockData.id ? await targetDb.dailyTimeblocks.get(blockData.id) : null;
    const id = blockData.id || `tb-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const version = existing ? (existing.version || 1) + 1 : 1;

    const record = {
      id,
      userId: activeUserId,
      deviceUuid: targetDb.getClientDeviceUUID(),
      blockDate: blockData.blockDate || blockData.block_date || now.slice(0, 10),
      startTime: blockData.startTime || blockData.start_time || '09:00',
      endTime: blockData.endTime || blockData.end_time || '10:00',
      title: blockData.title?.trim() || '',
      taskId: blockData.taskId || blockData.task_id || null,
      status: blockData.status || 'PLANNED',
      durationMinutes:
        typeof (blockData.durationMinutes || blockData.duration_minutes) === 'number'
          ? blockData.durationMinutes || blockData.duration_minutes
          : 60,
      actualDurationMinutes:
        typeof (blockData.actualDurationMinutes || blockData.actual_duration_minutes) === 'number'
          ? blockData.actualDurationMinutes || blockData.actual_duration_minutes
          : null,
      isBreak: blockData.isBreak ? 1 : 0,
      notes: blockData.notes || '',
      version,
      isDeleted: blockData.isDeleted ? 1 : 0,
      deletedAt: blockData.deletedAt || null,
      createdAt: existing ? existing.createdAt : blockData.createdAt || now,
      updatedAt: now,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.dailyTimeblocks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyTimeblocks];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.dailyTimeblocks.put(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.DAILY_TIMEBLOCK,
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

  async saveBatch(blockList, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.dailyTimeblocks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.dailyTimeblocks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyTimeblocks];

    return await targetDb.transaction('rw', tables, async () => {
      const records = [];
      for (const b of blockList) {
        const id = b.id || `tb-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const record = {
          id,
          userId: activeUserId,
          deviceUuid: targetDb.getClientDeviceUUID(),
          blockDate: b.blockDate || b.block_date || now.slice(0, 10),
          startTime: b.startTime || b.start_time || '09:00',
          endTime: b.endTime || b.end_time || '10:00',
          title: b.title?.trim() || '',
          taskId: b.taskId || b.task_id || null,
          status: b.status || 'PLANNED',
          durationMinutes:
            typeof (b.durationMinutes || b.duration_minutes) === 'number'
              ? b.durationMinutes || b.duration_minutes
              : 60,
          actualDurationMinutes:
            typeof (b.actualDurationMinutes || b.actual_duration_minutes) === 'number'
              ? b.actualDurationMinutes || b.actual_duration_minutes
              : null,
          isBreak: b.isBreak ? 1 : 0,
          notes: b.notes || '',
          version: b.version || 1,
          isDeleted: b.isDeleted ? 1 : 0,
          deletedAt: b.deletedAt || b.deleted_at || null,
          createdAt: b.createdAt || b.created_at || now,
          updatedAt: b.updatedAt || b.updated_at || now,
        };
        records.push(record);

        if (options.trackChange !== false && targetDb.syncQueue) {
          await changeTracker.recordChange(targetDb, {
            entityType: ENTITY_TYPES.DAILY_TIMEBLOCK,
            entityId: record.id,
            operation: SYNC_OPERATIONS.CREATE,
            entityVersion: record.version,
            payload: record,
            userId: activeUserId,
            deviceUuid: record.deviceUuid,
          });
        }
      }

      await targetDb.dailyTimeblocks.bulkPut(records);
      return records;
    });
  },

  async update(id, updates, userId = null, optionsOrTargetDb = { trackChange: true }, maybeDb = db) {
    let options = { trackChange: true };
    let targetDb = db;

    if (optionsOrTargetDb && optionsOrTargetDb.dailyTimeblocks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.dailyTimeblocks.get(id);
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
      ? [targetDb.dailyTimeblocks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyTimeblocks];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.dailyTimeblocks.put(updatedRecord);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.DAILY_TIMEBLOCK,
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

    if (optionsOrTargetDb && optionsOrTargetDb.dailyTimeblocks) {
      targetDb = optionsOrTargetDb;
    } else if (typeof optionsOrTargetDb === 'object') {
      options = { ...options, ...optionsOrTargetDb };
      targetDb = maybeDb || db;
    }

    const activeUserId = userId || targetDb.getActiveUserId();
    const existing = await targetDb.dailyTimeblocks.get(id);
    if (!existing || existing.userId !== activeUserId) {
      return false;
    }

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.dailyTimeblocks, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyTimeblocks];

    return await targetDb.transaction('rw', tables, async () => {
      if (options.softDelete !== false) {
        await targetDb.dailyTimeblocks.update(id, {
          isDeleted: 1,
          deletedAt: now,
          version: nextVersion,
          updatedAt: now,
        });
      } else {
        await targetDb.dailyTimeblocks.delete(id);
      }

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.DAILY_TIMEBLOCK,
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

  async saveForDate(blockDate, blocks = [], userId = null, options = { trackChange: true }, targetDb = db) {
    const activeUserId = userId || targetDb.getActiveUserId();
    const prepared = (blocks || []).map((b) => ({
      ...b,
      blockDate,
      userId: activeUserId,
    }));
    return await this.saveBatch(prepared, activeUserId, options, targetDb);
  },

  // Ergonomic aliases matching frontend service patterns
  async createTimeblock(blockData, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.save(blockData, userId, options, targetDb);
  },

  async updateTimeblock(id, updates, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.update(id, updates, userId, options, targetDb);
  },

  async deleteTimeblock(id, userId = null, options = { softDelete: true, trackChange: true }, targetDb = db) {
    return this.delete(id, userId, options, targetDb);
  },

  async bulkUpsert(blockList, userId = null, options = { trackChange: true }, targetDb = db) {
    return this.saveBatch(blockList, userId, options, targetDb);
  },
};
