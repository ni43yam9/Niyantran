/**
 * NIYANTRA Phase 10I: Service Worker & Background Sync Registration
 * 
 * Configures the service worker and registers the Background Sync API where supported,
 * providing graceful degradation for browsers without Background Sync.
 */

const BACKGROUND_SYNC_TAG = 'niyantra-background-sync';

export const serviceWorkerRegistration = {
  /**
   * Checks whether the Service Worker API is supported.
   */
  isServiceWorkerSupported() {
    return (
      typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      'serviceWorker' in navigator
    );
  },

  /**
   * Checks whether the Background Sync API is supported.
   */
  isBackgroundSyncSupported() {
    return (
      typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      'serviceWorker' in navigator &&
      'SyncManager' in window
    );
  },

  /**
   * Registers the service worker in production / browser environments.
   */
  async registerServiceWorker() {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return null;
    }

    try {
      const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      return registration;
    } catch (e) {
      console.warn('[ServiceWorker] Service worker registration failed:', e);
      return null;
    }
  },

  /**
   * Registers a background synchronization task with the browser.
   */
  async requestBackgroundSync(tag = BACKGROUND_SYNC_TAG) {
    if (!this.isBackgroundSyncSupported() || !navigator?.serviceWorker) {
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      if (registration && registration.sync) {
        await registration.sync.register(tag);
        return true;
      }
    } catch (err) {
      console.warn('[ServiceWorker] Background sync registration failed:', err);
      return false;
    }

    return false;
  },
};
