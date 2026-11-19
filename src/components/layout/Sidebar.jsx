import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  CheckSquare,
  Target,
  CalendarCheck2,
  CalendarDays,
  Flame,
  Hourglass,
  BarChart3,
  Sparkles,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Plus,
  Bell,
  PanelRight,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';
import { THEME_CONFIG } from '../../constants/theme';

export function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  const {
    user,
    isSidebarCollapsed,
    setIsSidebarCollapsed,
    tasks,
    openAddTaskModal,
    openAddGoalModal,
    isBackendOnline,
    isSyncing,
    syncWithBackend,
    isRightPanelOpen,
    setIsRightPanelOpen,
  } = useApp();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { id: 'tasks', label: 'My Tasks', path: '/tasks', icon: CheckSquare, badge: tasks.filter(t => t.status !== 'Completed').length },
    { id: 'goals', label: 'Goals', path: '/goals', icon: Target },
    { id: 'planner', label: 'Daily Planner', path: '/planner', icon: CalendarCheck2 },
    { id: 'calendar', label: 'Calendar', path: '/calendar', icon: CalendarDays },
    { id: 'habits', label: 'Habits', path: '/habits', icon: Flame },
    { id: 'focus', label: 'Focus Mode', path: '/focus', icon: Hourglass },
    { id: 'analytics', label: 'Analytics', path: '/analytics', icon: BarChart3 },
    { id: 'recommendations', label: 'Recommendations', path: '/recommendations', icon: Sparkles },
  ];

  return (
    <aside
      className={`hidden md:flex flex-col border-r border-slate-200 dark:border-slate-800/80 bg-white dark:bg-[#111827] h-screen sticky top-0 transition-all duration-300 select-none z-30 ${
        isSidebarCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="p-4.5 border-b border-slate-100 dark:border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          {/* Logo icon */}
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-indigo-700 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20 shrink-0">
            <span className="text-xl tracking-wider">N</span>
          </div>

          {!isSidebarCollapsed && (
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-base tracking-tight text-slate-900 dark:text-white">
                  {THEME_CONFIG.name}
                </span>
                <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60">
                  v1.0
                </span>
              </div>
              <p
                className="text-[10px] text-slate-400 dark:text-slate-500 font-mono tracking-tight truncate mt-0.5"
                title={THEME_CONFIG.tagline}
              >
                {THEME_CONFIG.tagline}
              </p>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          type="button"
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isSidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Quick Action Creation Buttons */}
      <div className="p-3 pb-1 space-y-1.5">
        <button
          type="button"
          onClick={() => openAddTaskModal()}
          className={`w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:from-indigo-700 active:to-indigo-800 text-white font-semibold shadow-sm shadow-indigo-500/20 transition-all cursor-pointer ${
            isSidebarCollapsed ? 'p-2.5' : 'px-3 py-2 text-xs'
          }`}
          title="Create New Task"
        >
          <Plus className="w-4 h-4 shrink-0" />
          {!isSidebarCollapsed && <span>New Task</span>}
        </button>

        {!isSidebarCollapsed && (
          <button
            type="button"
            onClick={() => openAddGoalModal()}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/80 text-slate-700 dark:text-slate-300 font-medium text-xs transition-colors cursor-pointer"
            title="Create New Goal"
          >
            <Target className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
            <span>New Goal</span>
          </button>
        )}
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 px-3 py-3 space-y-1 overflow-y-auto no-scrollbar">
        {!isSidebarCollapsed && (
          <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Workspace
          </p>
        )}
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group relative ${
                  isActive
                    ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-semibold shadow-2xs'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-200'
                } ${isSidebarCollapsed ? 'justify-center px-2' : ''}`
              }
              title={isSidebarCollapsed ? item.label : undefined}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`w-5 h-5 shrink-0 transition-colors ${
                      isActive
                        ? 'text-indigo-600 dark:text-indigo-400'
                        : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300'
                    }`}
                  />
                  {!isSidebarCollapsed && (
                    <span className="truncate flex-1">{item.label}</span>
                  )}
                  {!isSidebarCollapsed && item.badge !== undefined && item.badge > 0 && (
                    <span className="ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200/50 dark:border-slate-700/50">
                      {item.badge}
                    </span>
                  )}
                  {isSidebarCollapsed && item.badge !== undefined && item.badge > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-600 dark:bg-indigo-400" />
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom Section: Backend Status, Utility Tools & User Profile */}
      <div className="p-3 border-t border-slate-100 dark:border-slate-800/80 space-y-2 bg-slate-50/40 dark:bg-slate-900/30">
        {/* Backend Status Indicator */}
        <button
          type="button"
          onClick={() => syncWithBackend()}
          title={
            isBackendOnline
              ? 'Backend Online (SQLite) - Click to re-sync'
              : 'Backend Offline (Using localStorage fallback) - Click to reconnect'
          }
          className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-colors cursor-pointer ${
            isSidebarCollapsed ? 'justify-center px-1.5' : ''
          } ${
            isBackendOnline
              ? 'bg-emerald-50/80 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200/80 dark:border-emerald-800/60'
              : 'bg-amber-50/80 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200/80 dark:border-amber-800/60'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              isBackendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
            }`}
          />
          {!isSidebarCollapsed && (
            <span className="truncate text-[11px]">
              {isSyncing ? 'Syncing...' : isBackendOnline ? 'API Connected' : 'Local Offline'}
            </span>
          )}
        </button>

        {/* Utility Controls: Theme, Notifications, Agenda Panel */}
        <div className="flex items-center gap-1">
          {/* Theme Toggle Button */}
          <button
            type="button"
            onClick={toggleTheme}
            className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-slate-200 transition-colors cursor-pointer ${
              isSidebarCollapsed ? 'justify-center px-1' : ''
            }`}
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? (
              <Moon className="w-4 h-4 shrink-0 text-slate-500" />
            ) : (
              <Sun className="w-4 h-4 shrink-0 text-amber-400" />
            )}
            {!isSidebarCollapsed && (
              <span className="truncate">{theme === 'light' ? 'Dark' : 'Light'}</span>
            )}
          </button>

          {/* Notifications Icon */}
          <button
            type="button"
            className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-slate-200 transition-colors relative"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-indigo-600" />
          </button>

          {/* Toggle Right Panel (Desktop) */}
          <button
            type="button"
            onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
            className={`p-1.5 rounded-lg border transition-colors hidden xl:flex ${
              isRightPanelOpen
                ? 'border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400'
                : 'border-slate-200/80 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
            title={isRightPanelOpen ? 'Collapse side panel' : 'Expand side panel'}
          >
            <PanelRight className="w-4 h-4" />
          </button>
        </div>

        {/* User Profile */}
        <div
          className={`flex items-center gap-2.5 p-2 rounded-xl bg-white dark:bg-[#161F30] border border-slate-200/80 dark:border-slate-800 shadow-2xs ${
            isSidebarCollapsed ? 'justify-center' : ''
          }`}
          title={isSidebarCollapsed ? `${user.name} (${user.role})` : undefined}
        >
          <div className="w-8 h-8 rounded-lg bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold text-xs flex items-center justify-center shrink-0 border border-indigo-200/60 dark:border-indigo-800/60">
            {user.name.charAt(0)}
          </div>
          {!isSidebarCollapsed && (
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                {user.name}
              </p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 truncate">
                {user.role}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
