/**
 * NIYANTRA Client-Side Database Schema (IndexedDB via Dexie)
 * Provides robust multi-index definitions for offline-first querying,
 * user account isolation, durable synchronization queue, and multi-device metadata.
 */

export const DB_NAME = 'niyantra_client_db';
export const DB_VERSION = 3;

export const DB_SCHEMA_V1 = {
  tasks:
    'id, userId, status, priority, category, taskType, dueDate, startDate, goalId, isDeleted, updatedAt, [userId+isDeleted], [userId+dueDate], [userId+status]',
  goals:
    'id, userId, status, priority, goalType, category, targetDate, isDeleted, updatedAt, [userId+isDeleted], [userId+status]',
  habits:
    'id, userId, archived, category, isDeleted, updatedAt, [userId+isDeleted], [userId+archived]',
  habit_logs:
    'id, habitId, userId, logDate, completed, isDeleted, updatedAt, [habitId+logDate], [userId+logDate], [userId+isDeleted]',
  daily_timeblocks:
    'id, userId, blockDate, status, taskId, isDeleted, updatedAt, [userId+blockDate], [userId+isDeleted]',
  daily_intents:
    'id, userId, intentDate, isDeleted, updatedAt, [userId+intentDate], [userId+isDeleted]',
  activity_logs:
    'id, userId, deviceUuid, eventType, entityType, timestamp, [userId+timestamp]',
  recommendations:
    'id, userId, status, type, category, priority, isDeleted, updatedAt, [userId+status], [userId+isDeleted]',
  sync_meta:
    'key, value, updatedAt',
};

export const DB_SCHEMA_V2 = {
  ...DB_SCHEMA_V1,
  sync_queue:
    'id, operationId, userId, deviceUuid, entityType, entityId, operation, status, entityVersion, createdAt, nextRetryAt, [userId+status], [userId+entityType+entityId], [status+nextRetryAt]',
};

export const DB_SCHEMA_V3 = {
  ...DB_SCHEMA_V2,
  conflicts:
    'id, entityType, entityId, status, detectedAt, resolvedAt, [status+entityType], [userId+status], [userId+entityType+entityId]',
};
