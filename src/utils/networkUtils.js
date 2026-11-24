import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

/**
 * NIYANTRA Network & Offline Detection Utility
 * Combines browser navigator events with backend reachability probes.
 */

let currentIsOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
let currentIsBackendReachable = true;
const listeners = new Set();

function notifyListeners() {
  listeners.forEach((fn) => {
    try {
      fn({
        isOnline: currentIsOnline,
        isBackendReachable: currentIsBackendReachable,
      });
    } catch (e) {
      console.warn('Error in network listener:', e);
    }
  });
}

/**
 * Checks whether the browser is online and backend can be reached.
 */
export async function probeBackendReachability() {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    currentIsOnline = false;
    currentIsBackendReachable = false;
    notifyListeners();
    return { isOnline: false, isBackendReachable: false };
  }

  currentIsOnline = true;
  try {
    const res = await api.checkHealth();
    currentIsBackendReachable = res.online;
  } catch {
    currentIsBackendReachable = false;
  }

  notifyListeners();
  return {
    isOnline: currentIsOnline,
    isBackendReachable: currentIsBackendReachable,
  };
}

// Global window event listeners
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    currentIsOnline = true;
    notifyListeners();
    probeBackendReachability();
  });

  window.addEventListener('offline', () => {
    currentIsOnline = false;
    currentIsBackendReachable = false;
    notifyListeners();
  });
}

/**
 * Subscribes to network status changes.
 * Returns unsubscribe function.
 */
export function subscribeNetworkStatus(callback) {
  listeners.add(callback);
  callback({
    isOnline: currentIsOnline,
    isBackendReachable: currentIsBackendReachable,
  });
  return () => listeners.delete(callback);
}

/**
 * Returns instantaneous network status.
 */
export function getNetworkStatus() {
  return {
    isOnline: currentIsOnline,
    isBackendReachable: currentIsBackendReachable,
  };
}

/**
 * Custom React Hook for UI components to track online/offline status.
 */
export function useNetworkStatus(probeIntervalMs = 30000) {
  const [status, setStatus] = useState(() => ({
    isOnline: currentIsOnline,
    isBackendReachable: currentIsBackendReachable,
  }));

  const checkNow = useCallback(async () => {
    return await probeBackendReachability();
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeNetworkStatus(setStatus);

    // Initial probe
    probeBackendReachability();

    // Background interval when online
    let timer = null;
    if (probeIntervalMs > 0) {
      timer = setInterval(() => {
        if (currentIsOnline) {
          probeBackendReachability();
        }
      }, probeIntervalMs);
    }

    return () => {
      unsubscribe();
      if (timer) clearInterval(timer);
    };
  }, [probeIntervalMs]);

  const isFullyConnected = status.isOnline && status.isBackendReachable;
  const statusLabel = !status.isOnline
    ? 'Offline'
    : !status.isBackendReachable
    ? 'Local Mode (Server Unreachable)'
    : 'Online';

  return {
    ...status,
    isFullyConnected,
    statusLabel,
    checkNow,
  };
}
