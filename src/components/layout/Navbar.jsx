import { Plus, Bell, PanelRight, Target } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Button } from '../common/Button';

export function Navbar({ title, subtitle }) {
  const {
    openAddTaskModal,
    openAddGoalModal,
    isRightPanelOpen,
    setIsRightPanelOpen,
    isBackendOnline,
    isSyncing,
    syncWithBackend,
  } = useApp();

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
        {/* Backend Status Indicator */}
        <button
          type="button"
          onClick={() => syncWithBackend()}
          title={isBackendOnline ? 'Backend Online (SQLite) - Click to re-sync' : 'Backend Offline (Using localStorage fallback) - Click to reconnect'}
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors cursor-pointer ${
            isBackendOnline
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
              : 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800/60'
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${isBackendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span>{isSyncing ? 'Syncing...' : isBackendOnline ? 'API Connected' : 'Local Offline'}</span>
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
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200 transition-colors relative"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-600" />
        </button>

        {/* Toggle Right Panel (Desktop) */}
        <button
          type="button"
          onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
          className={`p-2 rounded-xl border transition-colors hidden xl:flex ${
            isRightPanelOpen
              ? 'border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400'
              : 'border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
          title={isRightPanelOpen ? 'Collapse side panel' : 'Expand side panel'}
        >
          <PanelRight className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
