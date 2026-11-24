/**
 * NIYANTRA Phase 10I: Storage Health & Eviction Protection
 * 
 * Provides browser storage durability checks, persistence requests,
 * and quota exhaustion warnings for offline-first IndexedDB safety.
 */

import { SYNC_META_KEYS } from '../sync/syncConstants';

export const storageHealth = {
  /**
   * Checks whether the StorageManager API is supported by the current environment.
   */
  isSupported() {
    return (
      typeof navigator !== 'undefined' &&
      typeof navigator.storage !== 'undefined' &&
      typeof navigator.storage.estimate === 'function'
    );
  },

  /**
   * Requests durable storage persistence from the browser to prevent eviction.
   */
  async requestPersistentStorage() {
    if (
      typeof navigator === 'undefined' ||
      !navigator.storage ||
      typeof navigator.storage.persist !== 'function'
    ) {
      return false;
    }

    try {
      const isPersisted = await navigator.storage.persist();
      return Boolean(isPersisted);
    } catch (e) {
      console.warn('[StorageHealth] Failed requesting persistent storage:', e);
      return false;
    }
  },

  /**
   * Checks whether storage is currently persisted.
   */
  async isStoragePersisted() {
    if (
      typeof navigator === 'undefined' ||
      !navigator.storage ||
      typeof navigator.storage.persisted !== 'function'
    ) {
      return false;
    }

    try {
      return await navigator.storage.persisted();
    } catch {
      return false;
    }
  },

  /**
   * Queries storage quota and usage estimates.
   * Emits a warning if quota usage exceeds 90% or remaining space is <50MB.
   */
  async getStorageQuotaEstimate(targetDb = null) {
    const isSupported = this.isSupported();
    if (!isSupported) {
      return {
        isSupported: false,
        isPersisted: false,
        quotaBytes: null,
        usageBytes: null,
        remainingBytes: null,
        usagePercent: 0,
        isQuotaWarning: false,
      };
    }

    try {
      const [estimate, isPersisted] = await Promise.all([
        navigator.storage.estimate(),
        this.isStoragePersisted(),
      ]);

      const quotaBytes = Number(estimate.quota) || 0;
      const usageBytes = Number(estimate.usage) || 0;
      const remainingBytes = Math.max(0, quotaBytes - usageBytes);
      const usagePercent = quotaBytes > 0 ? Math.round((usageBytes / quotaBytes) * 100) : 0;

      // Threshold: >90% used OR less than 50MB remaining (52,428,800 bytes)
      const isQuotaWarning = (usagePercent >= 90) || (quotaBytes > 0 && remainingBytes < 52428800);

      const usageMB = usageBytes / (1024 * 1024);
      const quotaMB = quotaBytes / (1024 * 1024);
      const remainingMB = remainingBytes / (1024 * 1024);

      const healthData = {
        isSupported: true,
        isPersisted,
        quotaBytes,
        usageBytes,
        remainingBytes,
        usagePercent,
        usagePercentage: usagePercent,
        usageMB,
        quotaMB,
        remainingMB,
        isQuotaWarning,
        isWarning: isQuotaWarning,
        checkedAt: new Date().toISOString(),
      };

      if (targetDb && targetDb.syncMeta) {
        try {
          await targetDb.syncMeta.put({
            key: SYNC_META_KEYS.STORAGE_HEALTH,
            value: healthData,
            updatedAt: new Date().toISOString(),
          });
        } catch {
          // Ignore metadata write error during quota pressure
        }
      }

      return healthData;
    } catch (err) {
      console.warn('[StorageHealth] Error querying storage estimate:', err);
      return {
        isSupported: true,
        isPersisted: false,
        quotaBytes: null,
        usageBytes: null,
        remainingBytes: null,
        usagePercent: 0,
        isQuotaWarning: false,
        error: err.message,
      };
    }
  },
};
