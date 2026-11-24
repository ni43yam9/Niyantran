import { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  HardDrive,
  Layers,
  Lock,
  Radio,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  User,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react';
import { syncManager } from '../../sync/syncManager';
import { storageHealth } from '../../utils/storageHealth';

export function SyncDiagnosticsModal({ isOpen, onClose }) {
  const [diagnostics, setDiagnostics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [feedbackMessage, setFeedbackMessage] = useState(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadDiagnostics = useCallback(async () => {
    try {
      const data = await syncManager.getSyncDiagnostics();
      setDiagnostics(data);
    } catch (err) {
      console.warn('Failed to load sync diagnostics:', err);
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    loadDiagnostics();
    const interval = setInterval(loadDiagnostics, 2500);

    const unsubSync = syncManager.onSyncComplete(() => {
      loadDiagnostics();
    });

    return () => {
      clearInterval(interval);
      unsubSync();
    };
  }, [isOpen, loadDiagnostics]);

  if (!isOpen) return null;

  const handleSyncNow = async () => {
    setActionLoading('sync');
    setFeedbackMessage(null);
    try {
      const res = await syncManager.sync();
      setFeedbackMessage({
        type: res.status === 'error' ? 'error' : 'success',
        text: `Sync finished: ${res.pushed || 0} pushed, ${res.pulled || 0} pulled (${res.status}).`,
      });
      await loadDiagnostics();
    } catch (e) {
      setFeedbackMessage({
        type: 'error',
        text: `Sync failed: ${e.message}`,
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetryFailed = async () => {
    setActionLoading('retry');
    setFeedbackMessage(null);
    try {
      const count = await syncManager.retryAllFailed();
      setFeedbackMessage({
        type: 'success',
        text: `Reset ${count} failed operation(s) to PENDING for immediate retry.`,
      });
      await loadDiagnostics();
    } catch (e) {
      setFeedbackMessage({
        type: 'error',
        text: `Failed to reset operations: ${e.message}`,
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRequestPersistence = async () => {
    setActionLoading('persist');
    setFeedbackMessage(null);
    try {
      const granted = await storageHealth.requestPersistentStorage();
      setFeedbackMessage({
        type: granted ? 'success' : 'warning',
        text: granted
          ? 'Browser granted Persistent Storage! IndexedDB will not be cleared under disk pressure.'
          : 'Browser denied or defaulted to best-effort storage.',
      });
      await loadDiagnostics();
    } catch (e) {
      setFeedbackMessage({
        type: 'error',
        text: `Could not request persistence: ${e.message}`,
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCopyJson = () => {
    if (!diagnostics) return;
    try {
      navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.warn('Clipboard copy failed:', e);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes == null || isNaN(bytes)) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatTimestamp = (isoString) => {
    if (!isoString) return 'Never';
    try {
      const date = new Date(isoString);
      return date.toLocaleString(undefined, {
        dateStyle: 'short',
        timeStyle: 'medium',
      });
    } catch {
      return isoString;
    }
  };

  const isWarningStorage = diagnostics?.storage?.isWarning;
  const isPersisted = diagnostics?.storage?.isPersisted;
  const usagePercentage = diagnostics?.storage?.usagePercentage || 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="w-full max-w-3xl max-h-[90vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-100 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                  Sync & Reliability Diagnostics
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {diagnostics?.tabId || 'tab-local'}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Phase 10I: Background Sync, Multi-Tab Coordination & Storage Health
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Alert */}
        {feedbackMessage && (
          <div
            className={`px-6 py-2.5 text-xs flex items-center justify-between border-b ${
              feedbackMessage.type === 'error'
                ? 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900'
                : feedbackMessage.type === 'warning'
                ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900'
                : 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900'
            }`}
          >
            <span>{feedbackMessage.text}</span>
            <button
              onClick={() => setFeedbackMessage(null)}
              className="underline font-medium ml-4 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Storage Quota Warning Banner */}
        {isWarningStorage && (
          <div className="px-6 py-3 bg-amber-500/10 border-b border-amber-500/30 text-amber-800 dark:text-amber-300 flex items-center gap-3 text-xs">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
            <div>
              <p className="font-semibold">Local Storage Space Critical</p>
              <p className="text-[11px] opacity-90">
                IndexedDB storage usage exceeds 90% or has under 50 MB remaining. Synchronize changes to prevent browser eviction.
              </p>
            </div>
          </div>
        )}

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Engine & Identity Status */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-1">
                Engine Status
              </span>
              <div className="flex items-center gap-1.5">
                {diagnostics?.engineStatus === 'IDLE' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                ) : diagnostics?.engineStatus === 'PROCESSING' ? (
                  <RefreshCw className="w-4 h-4 text-indigo-500 animate-spin" />
                ) : diagnostics?.engineStatus === 'AUTH_EXPIRED' ? (
                  <ShieldAlert className="w-4 h-4 text-rose-500" />
                ) : diagnostics?.engineStatus === 'DEVICE_REVOKED' ? (
                  <AlertOctagon className="w-4 h-4 text-rose-500" />
                ) : diagnostics?.engineStatus === 'RATE_LIMITED' ? (
                  <Clock className="w-4 h-4 text-amber-500" />
                ) : diagnostics?.engineStatus === 'OFFLINE' ? (
                  <WifiOff className="w-4 h-4 text-slate-400" />
                ) : (
                  <Radio className="w-4 h-4 text-indigo-500" />
                )}
                <span className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wider">
                  {diagnostics?.engineStatus || 'UNKNOWN'}
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-1">
                Active Account
              </span>
              <div className="flex items-center gap-1.5">
                <User className="w-4 h-4 text-slate-400" />
                <span
                  className="text-xs font-mono font-medium text-slate-900 dark:text-white truncate"
                  title={diagnostics?.userId || 'anonymous-user'}
                >
                  {diagnostics?.userId
                    ? `${diagnostics.userId.slice(0, 14)}...`
                    : 'anonymous-user'}
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-1">
                Device UUID
              </span>
              <div className="flex items-center gap-1.5">
                <Smartphone className="w-4 h-4 text-slate-400" />
                <span
                  className="text-xs font-mono font-medium text-slate-900 dark:text-white truncate"
                  title={diagnostics?.deviceUuid || 'unknown'}
                >
                  {diagnostics?.deviceUuid
                    ? `${diagnostics.deviceUuid.slice(0, 12)}...`
                    : 'Not initialized'}
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-1">
                Server Sequence (Cursor)
              </span>
              <div className="flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-500" />
                <span className="text-sm font-semibold text-slate-900 dark:text-white font-mono">
                  #{diagnostics?.currentCursor ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Sync Queue Breakdown */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900">
            <h3 className="text-xs font-semibold text-slate-900 dark:text-white uppercase tracking-wider mb-3 flex items-center justify-between">
              <span>Local Synchronization Queue (Durable IndexedDB)</span>
              <span className="text-[11px] font-normal text-slate-500 lowercase">
                Total operations: {diagnostics?.totalCount ?? 0}
              </span>
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/50">
                <span className="text-[11px] font-medium text-amber-800 dark:text-amber-400 block">
                  Pending Upload
                </span>
                <span className="text-xl font-bold text-amber-700 dark:text-amber-300">
                  {diagnostics?.pendingCount ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/50">
                <span className="text-[11px] font-medium text-indigo-800 dark:text-indigo-400 block">
                  In-Flight (Leased)
                </span>
                <span className="text-xl font-bold text-indigo-700 dark:text-indigo-300">
                  {diagnostics?.inFlightCount ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-rose-50/70 dark:bg-rose-950/30 border border-rose-200/80 dark:border-rose-800/50">
                <span className="text-[11px] font-medium text-rose-800 dark:text-rose-400 block">
                  Failed Operations
                </span>
                <span className="text-xl font-bold text-rose-700 dark:text-rose-300">
                  {diagnostics?.failedCount ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/50">
                <span className="text-[11px] font-medium text-emerald-800 dark:text-emerald-400 block">
                  Completed & Synced
                </span>
                <span className="text-xl font-bold text-emerald-700 dark:text-emerald-300">
                  {diagnostics?.completedCount ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Storage & Browser Subsystem Health */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900 space-y-4">
            <h3 className="text-xs font-semibold text-slate-900 dark:text-white uppercase tracking-wider">
              Storage Health & Multi-Tab Concurrency
            </h3>

            {/* Storage Quota Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs text-slate-600 dark:text-slate-400">
                <span className="flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5" />
                  Origin Quota: {formatBytes(diagnostics?.storage?.usageBytes)} used of{' '}
                  {formatBytes(diagnostics?.storage?.quotaBytes)}
                </span>
                <span className="font-semibold">{usagePercentage}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 rounded-full ${
                    usagePercentage > 90
                      ? 'bg-rose-500'
                      : usagePercentage > 75
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(0, usagePercentage))}%` }}
                />
              </div>
            </div>

            {/* Feature Flags Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                    Persistent Storage
                  </span>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {isPersisted ? 'Persisted (Protected)' : 'Best-Effort (Evictable)'}
                  </span>
                </div>
                {isPersisted ? (
                  <ShieldCheck className="w-4 h-4 text-emerald-500" />
                ) : (
                  <ShieldAlert className="w-4 h-4 text-amber-500" />
                )}
              </div>

              <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                    Multi-Tab Locking
                  </span>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {diagnostics?.isWebLocksSupported
                      ? 'Web Locks API (Native)'
                      : 'LocalStorage Lease'}
                  </span>
                </div>
                <Lock className="w-4 h-4 text-indigo-500" />
              </div>

              <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">
                    Background Sync API
                  </span>
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {diagnostics?.serviceWorker?.isBackgroundSyncSupported
                      ? 'Supported (SW Tag)'
                      : 'Foreground Fallback'}
                  </span>
                </div>
                <Database className="w-4 h-4 text-emerald-500" />
              </div>
            </div>
          </div>

          {/* Timestamps Card */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900">
            <h3 className="text-xs font-semibold text-slate-900 dark:text-white uppercase tracking-wider mb-2">
              Synchronization Timeline
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Last Successful Sync</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {formatTimestamp(diagnostics?.lastSuccessfulSyncAt)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Last Sync Attempt</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {formatTimestamp(diagnostics?.lastAttemptAt)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Last Local Mutation</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {formatTimestamp(diagnostics?.lastMutationAt)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Last Crash/Recovery</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {formatTimestamp(diagnostics?.lastRecoveryAt)}
                </span>
              </div>
            </div>
          </div>

          {/* Collapsible Raw JSON Inspector */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <button
              type="button"
              onClick={() => setShowRawJson(!showRawJson)}
              className="w-full px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center justify-between"
            >
              <span>Raw Diagnostics Payload</span>
              <span>{showRawJson ? 'Hide ▲' : 'Show ▼'}</span>
            </button>
            {showRawJson && (
              <div className="p-4 bg-slate-950 text-slate-200 font-mono text-[11px] overflow-x-auto relative">
                <button
                  type="button"
                  onClick={handleCopyJson}
                  className="absolute top-3 right-3 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 flex items-center gap-1 cursor-pointer"
                >
                  <Copy className="w-3 h-3" />
                  <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
                </button>
                <pre>{JSON.stringify(diagnostics, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>

        {/* Modal Action Footer */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/70 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {!isPersisted && (
              <button
                type="button"
                onClick={handleRequestPersistence}
                disabled={actionLoading != null}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-100 hover:bg-amber-200 dark:bg-amber-950/60 dark:hover:bg-amber-900/60 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Protect Storage</span>
              </button>
            )}

            {diagnostics?.failedCount > 0 && (
              <button
                type="button"
                onClick={handleRetryFailed}
                disabled={actionLoading != null}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-100 hover:bg-rose-200 dark:bg-rose-950/60 dark:hover:bg-rose-900/60 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-700 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Retry Failed ({diagnostics.failedCount})</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSyncNow}
              disabled={actionLoading != null}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${actionLoading === 'sync' ? 'animate-spin' : ''}`} />
              <span>{actionLoading === 'sync' ? 'Synchronizing...' : 'Sync Now'}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
