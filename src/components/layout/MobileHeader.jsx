import { Plus, Moon, Sun } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';
import { THEME_CONFIG } from '../../constants/theme';

export function MobileHeader() {
  const { theme, toggleTheme } = useTheme();
  const { openAddTaskModal, user } = useApp();

  return (
    <header className="md:hidden sticky top-0 z-30 bg-white/95 dark:bg-[#111827]/95 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-base shadow-sm shrink-0">
          N
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h1 className="font-extrabold text-sm tracking-tight text-slate-900 dark:text-white">
              {THEME_CONFIG.name}
            </h1>
            <span className="text-[9px] uppercase font-semibold px-1 py-0.2 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              v1.0
            </span>
          </div>
          <p className="text-[9px] text-slate-400 dark:text-slate-500 font-mono truncate max-w-[150px]">
            {THEME_CONFIG.tagline}
          </p>
        </div>
      </div>

      {/* Right Quick Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Quick Add Button */}
        <button
          type="button"
          onClick={() => openAddTaskModal()}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-indigo-600 active:bg-indigo-700 text-white text-xs font-semibold shadow-xs"
          aria-label="Add Task"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Task</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 active:scale-95 transition-transform"
          aria-label="Toggle theme"
        >
          {theme === 'light' ? (
            <Moon className="w-4 h-4 text-slate-600" />
          ) : (
            <Sun className="w-4 h-4 text-amber-400" />
          )}
        </button>

        {/* User avatar indicator */}
        <div className="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold text-xs flex items-center justify-center border border-slate-300 dark:border-slate-700">
          {user.name.charAt(0)}
        </div>
      </div>
    </header>
  );
}
