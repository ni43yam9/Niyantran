/**
 * NIYANTRA Phase 10I Service Worker
 * Provides offline shell caching and Background Sync API registration.
 */

const CACHE_NAME = 'niyantra-cache-v1';
const BACKGROUND_SYNC_TAG = 'niyantra-background-sync';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

/**
 * Notification Click Event Listener
 * Focuses or opens the NIYANTRAN window when a deadline notification is clicked.
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url && 'focus' in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow('/');
      }
    })
  );
});
 * Triggered by the browser when network connectivity is restored,
 * even if the user closed the window shortly after making changes.
 */
self.addEventListener('sync', (event) => {
  if (event.tag === BACKGROUND_SYNC_TAG) {
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then((clientList) => {
        // Notify any active clients to execute an immediate sync cycle
        clientList.forEach((client) => {
          client.postMessage({
            type: 'NIYANTRA_BACKGROUND_SYNC_TRIGGERED',
            tag: event.tag,
            timestamp: new Date().toISOString(),
          });
        });
      })
    );
  }
});
