import { useState } from 'react';
import { Plus, Bell, Target, RefreshCw, Cloud, CloudOff, CheckCircle, AlertTriangle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { useSyncStatus } from '../../sync';
import { Button } from '../common/Button';
import { ConflictResolutionModal } from '../common/ConflictResolutionModal';
import { SyncDiagnosticsModal } from '../common/SyncDiagnosticsModal';

export function Navbar({ title, subtitle }) {
  const [isConflictModalOpen, setIsConflictModalOpen] = useState(false);
  const [isDiagnosticsModalOpen, setIsDiagnosticsModalOpen] = useState(false);
  const {
    openAddTaskModal,
    openAddGoalModal,
    openNotificationCenter,
    unreadNotificationCount = 0,
  } = useApp();

  const {
    syncState,
    pendingCount,
    failedCount,
    conflictCount,
    isOnline,
    isSyncing,
    statusLabel,
    lastSuccessfulSyncAt,
    syncNow,
  } = useSyncStatus();

  return (
    <header className="hidden md:flex items-center justify-between px-6 py-3.5 border-b border-slate-200 dark:border-slate-800/80 bg-white/90 dark:bg-[#111827]/90 backdrop-blur-md sticky top-0 z-20">
      {/* Title & Context */}
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight leading-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {subtitle}
          </p>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* Phase 10H Conflict Notification Pill */}
        {conflictCount > 0 && (
          <button
            type="button"
            onClick={() => setIsConflictModalOpen(true)}
            title={`${conflictCount} synchronization conflict(s) detected. Click to resolve.`}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/60 transition-colors cursor-pointer shadow-xs animate-pulse"
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span>{conflictCount} Conflict{conflictCount > 1 ? 's' : ''}</span>
          </button>
        )}

        {/* Phase 10G & 10I Multi-Device Synchronization Status Badge */}
        <button
          type="button"
          onClick={() => setIsDiagnosticsModalOpen(true)}
          title={
            syncState === 'OFFLINE'
              ? 'Offline mode: local changes stored in IndexedDB. Click for diagnostics.'
              : syncState === 'SYNCING'
              ? 'Synchronizing changes across devices... Click for diagnostics.'
              : syncState === 'ERROR'
              ? `Sync Error (${failedCount} failed). Click for diagnostics & retry.`
              : syncState === 'PENDING'
              ? `${pendingCount} local change(s) waiting to upload. Click for diagnostics & sync.`
              : `All devices synchronized. Last sync: ${lastSuccessfulSyncAt ? new Date(lastSuccessfulSyncAt).toLocaleTimeString() : 'Recently'}. Click for diagnostics.`
          }
          className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium border transition-colors cursor-pointer ${
            syncState === 'SYNCED'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60 hover:bg-emerald-100'
              : syncState === 'SYNCING'
              ? 'bg-[#568B75]/15 dark:bg-[#75B798]/20 text-[#568B75] dark:text-[#75B798] border-[#568B75]/30 dark:border-[#75B798]/30'
              : syncState === 'PENDING'
              ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/60 hover:bg-amber-100'
              : syncState === 'ERROR'
              ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-900/60 hover:bg-rose-100'
              : 'bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-200'
          }`}
        >
          {syncState === 'SYNCING' ? (
            <RefreshCw className="w-3 h-3 text-[#568B75] dark:text-[#75B798] animate-spin" />
          ) : syncState === 'SYNCED' ? (
            <CheckCircle className="w-3 h-3 text-emerald-500" />
          ) : syncState === 'OFFLINE' ? (
            <CloudOff className="w-3 h-3 text-slate-400" />
          ) : (
            <Cloud className="w-3 h-3 text-amber-500" />
          )}
          <span>{statusLabel}</span>
        </button>

        <Button
          variant="outline"
          size="sm"
          icon={Target}
          onClick={() => openAddGoalModal()}
          className="hidden sm:inline-flex"
        >
          New Goal
        </Button>

        <Button
          variant="primary"
          size="sm"
          icon={Plus}
          onClick={() => openAddTaskModal()}
        >
          New Task
        </Button>

        {/* Notifications Icon */}
        <button
          type="button"
          onClick={openNotificationCenter}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200 transition-colors relative cursor-pointer"
          title="Important Deadline Notifications"
          aria-label="Important Deadline Notifications"
        >
          <Bell className="w-4 h-4" />
          {unreadNotificationCount > 0 ? (
            <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center leading-none shadow-xs">
              {unreadNotificationCount > 99 ? '99+' : unreadNotificationCount}
            </span>
          ) : (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#568B75] dark:bg-[#75B798]" />
          )}
        </button>
      </div>

      {/* Phase 10H Conflict Resolution Modal */}
      <ConflictResolutionModal
        isOpen={isConflictModalOpen}
        onClose={() => setIsConflictModalOpen(false)}
      />

      {/* Phase 10I Sync & Storage Diagnostics Modal */}
      <SyncDiagnosticsModal
        isOpen={isDiagnosticsModalOpen}
        onClose={() => setIsDiagnosticsModalOpen(false)}
      />
    </header>
  );
}
