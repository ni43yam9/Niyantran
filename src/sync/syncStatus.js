import { useState, useEffect, useCallback } from 'react';
import { syncManager } from './syncManager';
import { ENGINE_STATUS } from './syncConstants';
import { registerConflictListener } from './conflictDetector';

/**
 * Custom React Hook providing real-time multi-device synchronization status,
 * pending queue counts, conflict tracking, connectivity tracking, and a manual "Sync Now" action.
 */
export function useSyncStatus(pollIntervalMs = 5000) {
  const [status, setStatus] = useState({
    syncState: 'SYNCED', // 'OFFLINE' | 'SYNCING' | 'SYNCED' | 'PENDING' | 'ERROR' | 'CONFLICT'
    pendingCount: 0,
    failedCount: 0,
    completedCount: 0,
    conflictCount: 0,
    currentCursor: 0,
    lastSuccessfulSyncAt: null,
    lastMutationAt: null,
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isSyncing: false,
    isAuthenticated: false,
    statusLabel: 'Checking sync...',
  });

  const [isManualSyncing, setIsManualSyncing] = useState(false);

  const refreshSyncStatus = useCallback(async () => {
    try {
      const summary = await syncManager.getSyncSummary();
      const isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;

      let syncState = 'SYNCED';
      let statusLabel = 'Synced';

      if (!isOnline) {
        syncState = 'OFFLINE';
        statusLabel = summary.pendingCount > 0
          ? `Offline (${summary.pendingCount} pending)`
          : 'Offline (Local data ready)';
      } else if (summary.conflictCount > 0) {
        syncState = 'CONFLICT';
        statusLabel = `${summary.conflictCount} conflict${summary.conflictCount > 1 ? 's' : ''} require attention`;
      } else if (summary.engineStatus === ENGINE_STATUS.PROCESSING || isManualSyncing) {
        syncState = 'SYNCING';
        statusLabel = 'Syncing...';
      } else if (summary.failedCount > 0 || summary.engineStatus === ENGINE_STATUS.ERROR) {
        syncState = 'ERROR';
        statusLabel = `Sync error (${summary.failedCount} failed)`;
      } else if (summary.pendingCount > 0) {
        syncState = 'PENDING';
        statusLabel = `${summary.pendingCount} pending upload`;
      } else if (!summary.isAuthenticated) {
        syncState = 'OFFLINE';
        statusLabel = 'Guest mode (saved locally)';
      } else {
        syncState = 'SYNCED';
        statusLabel = summary.lastSuccessfulSyncAt
          ? 'Synced'
          : 'Ready to sync';
      }

      setStatus({
        ...summary,
        syncState,
        isOnline,
        isSyncing: syncState === 'SYNCING',
        statusLabel,
      });
    } catch (e) {
      console.warn('Failed retrieving sync status:', e);
    }
  }, [isManualSyncing]);

  const syncNow = useCallback(async () => {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      return { status: 'offline', message: 'Cannot sync while offline' };
    }
    setIsManualSyncing(true);
    try {
      const res = await syncManager.sync();
      return res;
    } finally {
      setIsManualSyncing(false);
      void refreshSyncStatus();
    }
  }, [refreshSyncStatus]);

  useEffect(() => {
    let active = true;

    const run = async () => {
      if (active) await refreshSyncStatus();
    };

    void run();

    // Register with syncManager for real-time notifications
    const unsubscribeSync = syncManager.onSyncComplete(() => {
      if (active) void run();
    });

    const unsubscribeConflict = registerConflictListener(() => {
      if (active) void run();
    });

    // Network listeners
    const handleNetChange = () => {
      if (active) void run();
    };
    window.addEventListener('online', handleNetChange);
    window.addEventListener('offline', handleNetChange);

    let timer = null;
    if (pollIntervalMs > 0) {
      timer = setInterval(run, pollIntervalMs);
    }

    return () => {
      active = false;
      unsubscribeSync();
      unsubscribeConflict();
      if (typeof window !== 'undefined' && window.removeEventListener) {
        window.removeEventListener('online', handleNetChange);
        window.removeEventListener('offline', handleNetChange);
      }
      if (timer) clearInterval(timer);
    };
  }, [pollIntervalMs, refreshSyncStatus]);

  return {
    ...status,
    syncNow,
    refreshSyncStatus,
  };
}
