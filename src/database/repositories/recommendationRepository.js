import { db } from '../db';
import { v4 as uuidv4 } from '../../utils/uuid';
import { changeTracker } from '../../sync/changeTracker';
import { SYNC_OPERATIONS, ENTITY_TYPES } from '../../sync/syncConstants';

/**
 * Recommendation Client-Side Repository (IndexedDB via Dexie)
 * Provides offline caching, filtering, and durable change tracking for recommendations.
 */
export const recommendationRepository = {
  /**
   * Retrieves recommendations for the user with optional filtering.
   */
  async getAll({
    status = 'PENDING',
    category = null,
    type = null,
    limit = 50,
    userId = null,
  } = {}, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();

    const records = await targetDb.recommendations
      .where('userId')
      .equals(uid)
      .filter((rec) => {
        if (rec.isDeleted) return false;
        if (status && rec.status !== status) return false;
        if (category && rec.category !== category) return false;
        if (type && rec.type !== type && rec.rec_type !== type) return false;
        return true;
      })
      .toArray();

    // Sort by priority/score descending, then updatedAt descending
    const priorityWeight = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    records.sort((a, b) => {
      const scoreDiff = (b.score || 0) - (a.score || 0);
      if (scoreDiff !== 0) return scoreDiff;
      const prioDiff = (priorityWeight[b.priority] || 0) - (priorityWeight[a.priority] || 0);
      if (prioDiff !== 0) return prioDiff;
      return (b.updatedAt || '').localeCompare(a.updatedAt || '');
    });

    return records.slice(0, limit);
  },

  /**
   * Retrieves recommendation by ID.
   */
  async getById(id, userId = null, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const rec = await targetDb.recommendations.get(String(id));
    if (!rec || rec.userId !== uid || rec.isDeleted) return null;
    return rec;
  },

  /**
   * Updates recommendation status (ACCEPTED, DISMISSED, COMPLETED).
   */
  async updateStatus(id, newStatus, userId = null, options = { trackChange: true }, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const existing = await this.getById(id, uid, targetDb);
    if (!existing) return null;

    const now = new Date().toISOString();
    const updated = {
      ...existing,
      status: newStatus,
      updatedAt: now,
      version: (existing.version || 1) + 1,
    };

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.recommendations, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.recommendations];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.recommendations.put(updated);

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.RECOMMENDATION,
          entityId: updated.id,
          operation: SYNC_OPERATIONS.UPDATE,
          entityVersion: updated.version,
          previousVersion: existing.version,
          payload: updated,
          userId: uid,
          deviceUuid: targetDb.getClientDeviceUUID(),
        });
      }

      return updated;
    });
  },

  /**
   * Soft-deletes a recommendation.
   */
  async delete(id, userId = null, options = { trackChange: true }, targetDb = db) {
    const uid = userId || targetDb.getActiveUserId();
    const existing = await this.getById(id, uid, targetDb);
    if (!existing) return false;

    const now = new Date().toISOString();
    const nextVersion = (existing.version || 1) + 1;

    const tables = targetDb.syncQueue && targetDb.syncMeta
      ? [targetDb.recommendations, targetDb.syncQueue, targetDb.syncMeta]
      : [targetDb.recommendations];

    return await targetDb.transaction('rw', tables, async () => {
      await targetDb.recommendations.update(String(id), {
        isDeleted: 1,
        deletedAt: now,
        updatedAt: now,
        version: nextVersion,
      });

      if (options.trackChange !== false && targetDb.syncQueue) {
        await changeTracker.recordChange(targetDb, {
          entityType: ENTITY_TYPES.RECOMMENDATION,
          entityId: String(id),
          operation: SYNC_OPERATIONS.DELETE,
          entityVersion: nextVersion,
          previousVersion: existing.version,
          payload: {
            id: String(id),
            isDeleted: 1,
            deletedAt: now,
            version: nextVersion,
          },
          userId: uid,
          deviceUuid: targetDb.getClientDeviceUUID(),
        });
      }

      return true;
    });
  },

  /**
   * Bulk upserts recommendations into IndexedDB.
   */
  async bulkUpsert(recommendations = [], userId = null, options = { trackChange: false }, targetDb = db) {
    if (!recommendations.length) return [];
    const uid = userId || targetDb.getActiveUserId();
    const now = new Date().toISOString();

    const prepared = recommendations.map((rec) => {
      const recId = rec.id ? String(rec.id) : uuidv4();
      return {
        id: recId,
        userId: rec.userId || uid,
        title: rec.title || '',
        description: rec.description || rec.message || '',
        type: rec.type || rec.rec_type || 'GENERAL',
        rec_type: rec.type || rec.rec_type || 'GENERAL',
        category: rec.category || 'WORK',
        priority: rec.priority || 'MEDIUM',
        status: rec.status || 'PENDING',
        score: rec.score != null ? Number(rec.score) : 0.5,
        confidence: rec.confidence != null ? Number(rec.confidence) : 0.5,
        actionPayload: rec.actionPayload || rec.action_payload || null,
        isDeleted: rec.isDeleted ? 1 : 0,
        createdAt: rec.createdAt || rec.created_at || now,
        updatedAt: rec.updatedAt || rec.updated_at || now,
        version: rec.version || 1,
      };
    });

    await targetDb.recommendations.bulkPut(prepared);
    return prepared;
  },
};
