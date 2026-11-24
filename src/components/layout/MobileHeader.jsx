import { useState } from 'react';
import { Plus, Moon, Sun, AlertTriangle, Bell } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';
import { THEME_CONFIG } from '../../constants/theme';
import { useSyncStatus } from '../../sync';
import { ConflictResolutionModal } from '../common/ConflictResolutionModal';

export function MobileHeader() {
  const [isConflictModalOpen, setIsConflictModalOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { openAddTaskModal, user, openNotificationCenter, unreadNotificationCount = 0 } = useApp();
  const { conflictCount } = useSyncStatus();

  return (
    <header className="md:hidden sticky top-0 z-30 glass-header px-4 py-3 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-10 h-10 flex items-center justify-center shrink-0">
          <img
            src="/logo.png"
            alt="NIYANTRAN Logo"
            className="w-9 h-9 object-contain drop-shadow-sm select-none"
            draggable={false}
          />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h1 className="app-brand-title font-sora text-lg font-[700] tracking-[-1.5px] text-[#243C32] dark:text-[#E8F3EC] leading-tight">
              {THEME_CONFIG.name}
            </h1>
          </div>
          <p className="text-[10.5px] text-[#718579] dark:text-[#9BB3A5] font-mono tracking-tight whitespace-nowrap mt-0.5 font-semibold">
            {THEME_CONFIG.tagline}
          </p>
        </div>
      </div>

      {/* Right Quick Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Phase 10H Conflict Notification Button */}
        {conflictCount > 0 && (
          <button
            type="button"
            onClick={() => setIsConflictModalOpen(true)}
            className="p-1.5 rounded-lg text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800"
            title={`${conflictCount} conflict(s) detected. Click to resolve.`}
          >
            <AlertTriangle className="w-4 h-4 text-amber-500 animate-pulse" />
          </button>
        )}

        {/* Quick Add Button */}
        <button
          type="button"
          onClick={() => openAddTaskModal()}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-[#568B75] active:bg-[#467360] dark:bg-[#75B798] dark:active:bg-[#568B75] text-white dark:text-[#101C18] text-xs font-semibold shadow-xs"
          aria-label="Add Task"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Task</span>
        </button>

        {/* Deadline Notifications Button */}
        <button
          type="button"
          onClick={openNotificationCenter}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/10 active:scale-95 transition-transform relative cursor-pointer"
          aria-label="Important Deadline Notifications"
          title="Important Deadline Notifications"
        >
          <Bell className="w-4 h-4" />
          {unreadNotificationCount > 0 && (
            <span className="absolute top-0.5 right-0.5 min-w-[15px] h-3.5 px-0.5 rounded-full bg-rose-500 text-white text-[8px] font-bold flex items-center justify-center leading-none shadow-xs">
              {unreadNotificationCount > 99 ? '99+' : unreadNotificationCount}
            </span>
          )}
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/10 active:scale-95 transition-transform"
          aria-label="Toggle theme"
        >
          {theme === 'light' ? (
            <Moon className="w-4 h-4 text-slate-600" />
          ) : (
            <Sun className="w-4 h-4 text-amber-400" />
          )}
        </button>

        {/* User avatar indicator */}
        <div className="w-7 h-7 rounded-full bg-[#568B75]/20 dark:bg-[#75B798]/20 text-[#243C32] dark:text-[#75B798] font-bold text-xs flex items-center justify-center border border-[#568B75]/30 dark:border-[#75B798]/30">
          {user.name.charAt(0)}
        </div>
      </div>

      {/* Phase 10H Mobile Conflict Resolution Modal */}
      <ConflictResolutionModal
        isOpen={isConflictModalOpen}
        onClose={() => setIsConflictModalOpen(false)}
      />
    </header>
  );
}
