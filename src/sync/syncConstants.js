/**
 * NIYANTRA Phase 10E: Synchronization Architecture Constants
 * Defines operations, statuses, entity definitions, and retry configurations.
 */

export const SYNC_OPERATIONS = Object.freeze({
  CREATE: 'CREATE',
  UPDATE: 'UPDATE',
  DELETE: 'DELETE',
});

export const SYNC_STATUS = Object.freeze({
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  FAILED: 'FAILED',
  COMPLETED: 'COMPLETED',
  SUPERSEDED: 'SUPERSEDED',
});

export const CONFLICT_STATUS = Object.freeze({
  DETECTED: 'DETECTED',
  PENDING_RESOLUTION: 'PENDING_RESOLUTION',
  RESOLVED_LOCAL: 'RESOLVED_LOCAL',
  RESOLVED_REMOTE: 'RESOLVED_REMOTE',
  RESOLVED_MERGED: 'RESOLVED_MERGED',
});

export const RESOLUTION_STRATEGY = Object.freeze({
  KEEP_LOCAL: 'KEEP_LOCAL',
  KEEP_REMOTE: 'KEEP_REMOTE',
  MANUAL_MERGE: 'MANUAL_MERGE',
});

export const ENTITY_TYPES = Object.freeze({
  TASK: 'task',
  GOAL: 'goal',
  HABIT: 'habit',
  HABIT_LOG: 'habit_log',
  DAILY_TIMEBLOCK: 'daily_timeblock',
  DAILY_INTENT: 'daily_intent',
  RECOMMENDATION: 'recommendation',
  ACTIVITY_LOG: 'activity_log',
});

export const DEFAULT_RETRY_CONFIG = Object.freeze({
  maxRetries: 5,
  initialBackoffMs: 2000, // 2s
  maxBackoffMs: 300000, // 5 mins
  backoffFactor: 2,
});

export const SYNC_META_KEYS = Object.freeze({
  LAST_LOCAL_MUTATION: 'last_local_mutation_at',
  LAST_QUEUED_OP: 'last_queued_operation_id',
  LAST_SYNC_ATTEMPT: 'last_sync_attempt_at',
  LAST_SUCCESSFUL_SYNC: 'last_successful_sync_at',
  LAST_PULLED_CURSOR: 'last_pulled_cursor',
  ENGINE_STATUS: 'sync_engine_status',
  PENDING_COUNT: 'pending_operation_count',
  FAILED_COUNT: 'failed_operation_count',
  CONFLICT_COUNT: 'unresolved_conflict_count',
  CONFLICT_PREFIX: 'conflict_',
  STORAGE_HEALTH: 'storage_health',
  PERSISTENT_STORAGE: 'is_persistent_storage',
  LAST_RECOVERY_AT: 'last_recovery_at',
  MULTI_TAB_LOCK: 'niyantra_sync_tab_lock',
});

export const ENGINE_STATUS = Object.freeze({
  IDLE: 'IDLE',
  OFFLINE: 'OFFLINE',
  PROCESSING: 'PROCESSING',
  ERROR: 'ERROR',
  UNAUTHENTICATED: 'UNAUTHENTICATED',
  SYNCED: 'SYNCED',
  PENDING: 'PENDING',
  AUTH_EXPIRED: 'AUTH_EXPIRED',
  DEVICE_REVOKED: 'DEVICE_REVOKED',
  RATE_LIMITED: 'RATE_LIMITED',
  STORAGE_WARNING: 'STORAGE_WARNING',
});
