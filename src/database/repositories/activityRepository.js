import { db } from '../db';
import { v4 as uuidv4 } from '../../utils/uuid';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

let lastTimestampMs = 0;
function getMonotonicTimestamp() {
  let now = Date.now();
  if (now <= lastTimestampMs) {
    now = lastTimestampMs + 1;
  }
  lastTimestampMs = now;
  return new Date(now).toISOString();
}

/**
 * Activity Log Client-Side Repository (IndexedDB via Dexie)
 * Tracks user productivity actions offline and prepares for multi-device audit trails.
 */
export const activityRepository = {
  /**
   * Records a user productivity event into IndexedDB and queues change record.
   */
  async log(
    {
      eventType,
      entityType = null,
      entityId = null,
      details = null,
      userId = null,
      deviceUuid = null,
    },
    options = { trackChange: true },
    targetDb = db
  ) {
    const uid = userId || targetDb.getActiveUserId();
    const duid = deviceUuid || targetDb.getClientDeviceUUID();
    const timestamp = getMonotonicTimestamp();

    const record = {
      id: uuidv4(),
      userId: uid,
      deviceUuid: duid,
      eventType,
      entityType,
      entityId: entityId ? String(entityId) : null,
      details: details ? (typeof details === 'object' ? details : { raw: details }) : {},
      timestamp,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.activityLogs, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.activityLogs];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.activityLogs.add(record);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.ACTIVITY_LOG,
          entityId: record.id,
          operation: SYNC_OPERATIONS.CREATE,
          entityVersion: 1,
          payload: record,
          userId: uid,
          deviceUuid: duid,
        });
      }

      return record;
    });
  },

  /**
   * Retrieves recent activity logs sorted by timestamp descending.
   */
  async getRecent({ limit = 50, entityType = null, eventType = null, userId = null } = {}, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();

    const records = await targetDb.activityLogs
      .where('userId')
      .equals(uid)
      .filter((item) => {
        if (entityType && item.entityType !== entityType) return false;
        if (eventType && item.eventType !== eventType) return false;
        return true;
      })
      .toArray();

    records.sort((a, b) => {
      const diff = b.timestamp.localeCompare(a.timestamp);
      if (diff !== 0) return diff;
      return (b.id || '').localeCompare(a.id || '');
    });

    return records.slice(0, limit);
  },

  /**
   * Bulk adds activity logs (used for sync or bulk imports).
   */
  async bulkAdd(logs = [], options = { trackChange: false }, targetDb = db) {
    if (!logs.length) return [];
    const uid = targetDb.getActiveUserId();
    const duid = targetDb.getClientDeviceUUID();
    const now = new Date().toISOString();

    const prepared = logs.map((log) => ({
      id: log.id || uuidv4(),
      userId: log.userId || uid,
      deviceUuid: log.deviceUuid || duid,
      eventType: log.eventType,
      entityType: log.entityType || null,
      entityId: log.entityId ? String(log.entityId) : null,
      details: log.details || {},
      timestamp: log.timestamp || now,
    }));

    await targetDb.activityLogs.bulkAdd(prepared);
    return prepared;
  },
};
