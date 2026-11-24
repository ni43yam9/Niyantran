import { syncManager } from './syncManager';
import { tabCoordinator } from './tabCoordinator';
import { storageHealth } from '../utils/storageHealth';
import { serviceWorkerRegistration } from '../utils/serviceWorkerRegistration';

let periodicTimer = null;
let debounceTimer = null;
let isInitialized = false;
let unsubscribeTabCoordinator = null;

function handleOnline() {
  if (syncManager.isAuthenticated()) {
    void syncManager.sync();
  }
}

function handleVisibilityChange() {
  if (document.visibilityState === 'visible' && syncManager.isAuthenticated()) {
    void syncManager.sync();
  }
}

/**
 * Initializes automatic background synchronization triggers:
 * 1. Connectivity restored ('online' event)
 * 2. Window/tab focus ('visibilitychange' event)
 * 3. Periodic synchronization interval (default 30s)
 * 4. Cross-tab sync coordination & event propagation
 * 5. Storage persistence verification
 * 6. Service worker background sync registration
 */
export function initSyncTriggers({
  intervalMs = 30000,
  initialSync = true,
} = {}) {
  if (typeof window === 'undefined' || isInitialized) {
    return;
  }

  isInitialized = true;

  // 1. Request persistent storage on startup
  void storageHealth.requestPersistentStorage();

  // 2. Register Service Worker for offline and background sync
  void serviceWorkerRegistration.registerServiceWorker();

  // 3. Listen to cross-tab synchronization broadcasts
  unsubscribeTabCoordinator = tabCoordinator.onMessage((event) => {
    if (event && event.type === 'SYNC_COMPLETED') {
      // Notify local listeners that another tab synced so UI re-evaluates queue state
      syncManager.notify({
        type: 'REMOTE_TAB_SYNC',
        senderTabId: event.senderTabId,
        pushed: event.pushed,
        pulled: event.pulled,
        status: event.status,
      });
    }
  });

  // 4. Network and visibility triggers
  if (typeof window.addEventListener === 'function') {
    window.addEventListener('online', handleOnline);
  }
  if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  }

  // 5. Periodic polling fallback
  if (intervalMs > 0) {
    periodicTimer = setInterval(() => {
      const isVisible = typeof document === 'undefined' || document.visibilityState !== 'hidden';
      if (isVisible && syncManager.isAuthenticated()) {
        void syncManager.sync();
      }
    }, intervalMs);
  }

  // 6. Initial startup synchronization
  if (initialSync && syncManager.isAuthenticated()) {
    void syncManager.sync();
  }
}

/**
 * Debounces synchronization after local mutations (e.g. 1.5s delay)
 * to bundle rapid successive edits into a single push request.
 */
export function triggerDebouncedSync(delayMs = 1500) {
  if (typeof window === 'undefined') return;

  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  debounceTimer = setTimeout(() => {
    debounceTimer = null;
    if (syncManager.isAuthenticated()) {
      void syncManager.sync();
    }
  }, delayMs);
}

/**
 * Cleans up listeners and background intervals.
 */
export function teardownSyncTriggers() {
  if (typeof window === 'undefined') return;

  isInitialized = false;

  if (typeof unsubscribeTabCoordinator === 'function') {
    unsubscribeTabCoordinator();
    unsubscribeTabCoordinator = null;
  }

  if (typeof window.removeEventListener === 'function') {
    window.removeEventListener('online', handleOnline);
  }
  if (typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  }

  if (periodicTimer) {
    clearInterval(periodicTimer);
    periodicTimer = null;
  }

  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}
