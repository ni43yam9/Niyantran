import Dexie from 'dexie';
import { DB_NAME, DB_SCHEMA_V1, DB_SCHEMA_V2, DB_SCHEMA_V3 } from './schema';
import { getOrCreateDeviceUUID } from '../utils/deviceUtils';

export class NiyantraDatabase extends Dexie {
  constructor(options = {}) {
    super(options.name || DB_NAME, options);

    // Schema versioning for smooth non-breaking upgrades
    this.version(1).stores(DB_SCHEMA_V1);
    this.version(2).stores(DB_SCHEMA_V2);
    this.version(3).stores(DB_SCHEMA_V3);

    // Bind tables to convenience properties
    this.tasks = this.table('tasks');
    this.goals = this.table('goals');
    this.habits = this.table('habits');
    this.habitLogs = this.table('habit_logs');
    this.dailyTimeblocks = this.table('daily_timeblocks');
    this.dailyIntents = this.table('daily_intents');
    this.activityLogs = this.table('activity_logs');
    this.recommendations = this.table('recommendations');
    this.syncMeta = this.table('sync_meta');
    this.syncQueue = this.table('sync_queue');
    this.conflicts = this.table('conflicts');
  }

  /**
   * Resolves the active user ID for client storage operations.
   * Defaults to authenticated user or 'default_user' in local/guest mode.
   */
  getActiveUserId() {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const userJson = window.localStorage.getItem('niyantra_user');
        if (userJson) {
          const user = JSON.parse(userJson);
          if (user && user.id) return user.id;
        }
      }
    } catch (e) {
      console.warn('Failed resolving active user from localStorage:', e);
    }
    return 'default_user';
  }

  /**
   * Resolves the client hardware device UUID.
   */
  getClientDeviceUUID() {
    return getOrCreateDeviceUUID();
  }
}

// Singleton client database instance
export const db = new NiyantraDatabase();
