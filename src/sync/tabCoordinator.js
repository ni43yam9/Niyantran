/**
 * NIYANTRA Phase 10I: Multi-Tab Concurrency Coordinator & Cross-Tab Event Bus
 * 
 * Prevents race conditions and duplicate sync operations across concurrent browser tabs.
 * Uses Web Locks API (navigator.locks) with leased localStorage fallback and BroadcastChannel.
 */

import { v4 as uuidv4 } from '../utils/uuid';

const TAB_ID = `tab-${uuidv4().slice(0, 8)}`;
const SYNC_LOCK_KEY = 'niyantra_sync_tab_lock';
const LOCK_LEASE_MS = 20000; // 20s lease timeout
const CHANNEL_NAME = 'niyantra_sync_channel';

let broadcastBus = null;
const crossTabListeners = new Set();

try {
  if (typeof BroadcastChannel !== 'undefined') {
    broadcastBus = new BroadcastChannel(CHANNEL_NAME);
    broadcastBus.onmessage = (event) => {
      if (event && event.data) {
        crossTabListeners.forEach((listener) => {
          try {
            listener(event.data);
          } catch (e) {
            console.warn('[TabCoordinator] Error in cross-tab listener:', e);
          }
        });
      }
    };
  }
} catch (e) {
  console.warn('[TabCoordinator] BroadcastChannel not supported in this environment:', e);
}

export const tabCoordinator = {
  /**
   * Returns the current tab's unique session identifier.
   */
  getTabId() {
    return TAB_ID;
  },

  /**
   * Checks whether the native Web Locks API is supported in the current environment.
   */
  isWebLocksSupported() {
    return (
      typeof navigator !== 'undefined' &&
      Boolean(navigator.locks) &&
      typeof navigator.locks.request === 'function'
    );
  },

  /**
   * Broadcasts a synchronization event to all other open tabs.
   */
  broadcast(event) {
    if (broadcastBus && typeof broadcastBus.postMessage === 'function') {
      try {
        broadcastBus.postMessage({
          ...event,
          senderTabId: TAB_ID,
          broadcastAt: new Date().toISOString(),
        });
      } catch {
        // Ignore broadcast failure during unload
      }
    }
  },

  /**
   * Subscribes to events broadcast from other tabs.
   */
  onMessage(callback) {
    if (typeof callback === 'function') {
      crossTabListeners.add(callback);
      return () => crossTabListeners.delete(callback);
    }
    return () => {};
  },

  /**
   * Executes a synchronization action with mutual exclusion across tabs.
   * Uses the Web Locks API where supported, with a leased localStorage fallback.
   */
  async withLock(action, { lockName = 'niyantra_sync_lock', leaseMs = LOCK_LEASE_MS } = {}) {
    // 1. Preferred: Web Locks API
    if (
      typeof navigator !== 'undefined' &&
      navigator.locks &&
      typeof navigator.locks.request === 'function'
    ) {
      return await navigator.locks.request(
        lockName,
        { ifAvailable: true },
        async (lock) => {
          if (!lock) {
            return {
              locked: true,
              executed: false,
              message: 'Sync in progress in another tab (Web Lock acquired by peer)',
            };
          }
          const result = await action();
          return { locked: false, executed: true, result };
        }
      );
    }

    // 2. Fallback: Leased localStorage lock
    return await this._withStorageLock(action, lockName, leaseMs);
  },

  /**
   * Fallback lock implementation utilizing localStorage timestamps.
   */
  async _withStorageLock(action, lockName, leaseMs) {
    if (typeof window === 'undefined' || !window.localStorage) {
      // In non-browser environment, execute directly
      const result = await action();
      return { locked: false, executed: true, result };
    }

    const now = Date.now();
    const existingLockJson = window.localStorage.getItem(SYNC_LOCK_KEY);

    if (existingLockJson) {
      try {
        const parsed = JSON.parse(existingLockJson);
        if (parsed.expiresAt && parsed.expiresAt > now && parsed.tabId !== TAB_ID) {
          return {
            locked: true,
            executed: false,
            message: `Sync in progress in another tab (${parsed.tabId})`,
          };
        }
      } catch {
        // Stale or corrupt lock data; overwrite
      }
    }

    // Acquire lock
    const lockPayload = {
      tabId: TAB_ID,
      lockName,
      acquiredAt: now,
      expiresAt: now + leaseMs,
    };

    try {
      window.localStorage.setItem(SYNC_LOCK_KEY, JSON.stringify(lockPayload));
      const result = await action();
      return { locked: false, executed: true, result };
    } finally {
      // Release lock if held by this tab
      try {
        const current = window.localStorage.getItem(SYNC_LOCK_KEY);
        if (current) {
          const parsed = JSON.parse(current);
          if (parsed.tabId === TAB_ID) {
            window.localStorage.removeItem(SYNC_LOCK_KEY);
          }
        }
      } catch {
        // Ignore cleanup error
      }
    }
  },
};
