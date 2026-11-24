/**
 * NIYANTRA Client-Side Database Entry Point (IndexedDB)
 * Exports the primary database instance, repositories, schemas, and sync queue.
 */

export { db, NiyantraDatabase } from './db';
export { DB_NAME, DB_VERSION, DB_SCHEMA_V1, DB_SCHEMA_V2 } from './schema';

export { taskRepository } from './repositories/taskRepository';
export { goalRepository } from './repositories/goalRepository';
export { habitRepository } from './repositories/habitRepository';
export { timeblockRepository } from './repositories/timeblockRepository';
export { dailyIntentRepository } from './repositories/dailyIntentRepository';
export { activityRepository } from './repositories/activityRepository';
export { recommendationRepository } from './repositories/recommendationRepository';

// Phase 10E Sync & Queue Exports
export * from '../sync';
