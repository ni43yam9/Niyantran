/**
 * NIYANTRA Cloud Synchronization API Service (Phase 10F)
 * 
 * Provides HTTP client bindings to the backend synchronization API (/api/sync).
 * Note: Automated synchronization and background timers are intentionally deferred to Phase 10G.
 */

import { api } from './api';

/**
 * Pushes a batch of locally queued change operations to the cloud backend.
 * 
 * @param {Array<Object>} operations - Array of sync operations from sync_queue
 * @param {string} [deviceUuid] - Optional hardware device UUID
 * @returns {Promise<Object>} Push response with applied count, rejected count, and per-item results
 */
export async function pushSync(operations = [], deviceUuid = null) {
  const headers = {};
  if (deviceUuid) {
    headers['X-Device-UUID'] = deviceUuid;
  }

  const payload = {
    device_uuid: deviceUuid,
    operations: operations.map((op) => ({
      operation_uuid: op.operationId || op.operation_uuid || op.id,
      device_uuid: op.deviceUuid || deviceUuid,
      entity_type: op.entityType || op.entity_type,
      entity_id: String(op.entityId || op.entity_id),
      operation_type: (op.operation || op.operation_type || 'UPDATE').toUpperCase(),
      entity_version: Number(op.entityVersion || op.entity_version || 1),
      payload: op.payload || {},
      created_at: op.createdAt || op.created_at || new Date().toISOString(),
    })),
  };

  return api.post('/sync/push', payload, { headers });
}

/**
 * Pulls delta changes from the backend occurring after the given sequence cursor.
 * 
 * @param {number} [cursor=0] - Sequence ID cursor
 * @param {number} [limit=50] - Maximum records to fetch
 * @param {boolean} [excludeSelf=false] - Whether to exclude operations originating from this device
 * @param {string} [entityType=null] - Optional entity type filter
 * @param {string} [deviceUuid=null] - Requesting device UUID
 * @returns {Promise<Object>} Pull response containing changes, next_cursor, and has_more
 */
export async function pullSync(cursor = 0, limit = 50, excludeSelf = false, entityType = null, deviceUuid = null) {
  const headers = {};
  if (deviceUuid) {
    headers['X-Device-UUID'] = deviceUuid;
  }

  const params = new URLSearchParams({
    cursor: String(cursor),
    limit: String(limit),
    exclude_self: String(excludeSelf),
  });

  if (entityType) {
    params.append('entity_type', entityType);
  }
  if (deviceUuid) {
    params.append('device_uuid', deviceUuid);
  }

  return api.get(`/sync/pull?${params.toString()}`, { headers });
}

/**
 * Retrieves the current synchronization status, pending change counts, and server checkpoint.
 * 
 * @param {string} [deviceUuid=null] - Requesting device UUID
 * @returns {Promise<Object>} Status response
 */
export async function getSyncStatus(deviceUuid = null) {
  const headers = {};
  if (deviceUuid) {
    headers['X-Device-UUID'] = deviceUuid;
  }

  const query = deviceUuid ? `?device_uuid=${encodeURIComponent(deviceUuid)}` : '';
  return api.get(`/sync/status${query}`, { headers });
}

/**
 * Acknowledges receipt of pulled changes, updating the device's server-side checkpoint.
 * 
 * @param {number} cursor - Highest sequence ID acknowledged
 * @param {string} [deviceUuid=null] - Requesting device UUID
 * @returns {Promise<Object>} Acknowledgment confirmation
 */
export async function acknowledgeSync(cursor, deviceUuid = null) {
  const headers = {};
  if (deviceUuid) {
    headers['X-Device-UUID'] = deviceUuid;
  }

  return api.post('/sync/acknowledge', { cursor, device_uuid: deviceUuid }, { headers });
}

/**
 * Inspects recent synchronization changes across all user devices.
 * 
 * @param {number} [cursor=0] - Sequence ID cursor
 * @param {number} [limit=50] - Records limit
 * @param {string} [entityType=null] - Entity filter
 * @returns {Promise<Object>} Changes log
 */
export async function inspectChanges(cursor = 0, limit = 50, entityType = null) {
  const params = new URLSearchParams({
    cursor: String(cursor),
    limit: String(limit),
  });
  if (entityType) {
    params.append('entity_type', entityType);
  }
  return api.get(`/sync/changes?${params.toString()}`);
}

export default {
  pushSync,
  pullSync,
  getSyncStatus,
  acknowledgeSync,
  inspectChanges,
};
