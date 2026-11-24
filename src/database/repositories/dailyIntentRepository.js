import { db } from '../db';
import { v4 as uuidv4 } from '../../utils/uuid';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

/**
 * Daily Intent Client-Side Repository (IndexedDB via Dexie)
 * Provides offline persistence and durable change tracking for daily productivity focus statements.
 */
export const dailyIntentRepository = {
  /**
   * Retrieves intent for a specific date and user.
   */
  async getByDate(intentDate, userId = null, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const records = await targetDb.dailyIntents
      .where('userId')
      .equals(uid)
      .filter((item) => item.intentDate === intentDate && !item.isDeleted)
      .toArray();

    return records.length > 0 ? records[0] : null;
  },

  /**
   * Retrieves all non-deleted intents for user as a map { [date]: text }.
   */
  async getMap(userId = null, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const records = await targetDb.dailyIntents
      .where('userId')
      .equals(uid)
      .filter((item) => !item.isDeleted)
      .toArray();

    const map = {};
    for (const record of records) {
      map[record.intentDate] = record.intentText;
    }
    return map;
  },

  /**
   * Lists intents within optional date range.
   */
  async list({ startDate = null, endDate = null, userId = null } = {}, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    let query = targetDb.dailyIntents.where('userId').equals(uid);

    const records = await query
      .filter((item) => {
        if (item.isDeleted) return false;
        if (startDate && item.intentDate < startDate) return false;
        if (endDate && item.intentDate > endDate) return false;
        return true;
      })
      .toArray();

    return records.sort((a, b) => b.intentDate.localeCompare(a.intentDate));
  },

  /**
   * Creates or updates daily intent for a given date.
   */
  async save(intentDate, intentText, userId = null, options = { trackChange: true }, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const existing = await this.getByDate(intentDate, uid, targetDb);
    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.dailyIntents, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyIntents];

    return await targetDb.transaction('rw', tables, async () => {
      let record = null;
      let opType = SYNC_OPERATIONS.CREATE;

      if (existing) {
        record = {
          ...existing,
          intentText: intentText.trim(),
          version: (existing.version || 1) + 1,
          updatedAt: now,
        };
        opType = SYNC_OPERATIONS.UPDATE;
      } else {
        record = {
          id: uuidv4(),
          userId: uid,
          deviceUuid: targetDb.getClientDeviceUUID(),
          intentDate,
          intentText: intentText.trim(),
          version: 1,
          isDeleted: 0,
          createdAt: now,
          updatedAt: now,
        };
        opType = SYNC_OPERATIONS.CREATE;
      }

      await targetDb.dailyIntents.put(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.DAILY_INTENT,
          entityId: record.id,
          operation: opType,
          entityVersion: record.version,
          previousVersion: existing ? existing.version : null,
          payload: record,
          userId: uid,
          deviceUuid: record.deviceUuid || targetDb.getClientDeviceUUID(),
        });
      }

      return record;
    });
  },

  /**
   * Soft-deletes intent for a date.
   */
  async delete(intentDate, userId = null, options = { trackChange: true }, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const existing = await this.getByDate(intentDate, uid, targetDb);
    if (!existing) return false;

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.dailyIntents, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.dailyIntents];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.dailyIntents.update(existing.id, {
        isDeleted: 1,
        deletedAt: now,
        updatedAt: now,
        version: nextVersion,
      });

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.DAILY_INTENT,
          entityId: existing.id,
          operation: SYNC_OPERATIONS.DELETE,
          entityVersion: nextVersion,
          previousVersion: existing.version,
          payload: {
            id: existing.id,
            intentDate,
            isDeleted: 1,
            deletedAt: now,
            version: nextVersion,
          },
          userId: uid,
          deviceUuid: existing.deviceUuid || targetDb.getClientDeviceUUID(),
        });
      }

      return true;
    });
  },

  /**
   * Batch upsert (used during migration and syncing).
   */
  async bulkUpsert(intents = [], userId = null, options = { trackChange: false }, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const prepared = intents.map((intent) => ({
      id: intent.id || uuidv4(),
      userId: intent.userId || uid,
      deviceUuid: targetDb.getClientDeviceUUID(),
      intentDate: intent.intentDate,
      intentText: (intent.intentText || '').trim(),
      version: intent.version || 1,
      isDeleted: intent.isDeleted ? 1 : 0,
      createdAt: intent.createdAt || now,
      updatedAt: intent.updatedAt || now,
    }));

    await targetDb.dailyIntents.bulkPut(prepared);
    return prepared;
  },
};
