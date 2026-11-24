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
  Bell,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useApp } from '../../context/AppContext';
import { THEME_CONFIG } from '../../constants/theme';

export function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  const {
    isSidebarCollapsed,
    setIsSidebarCollapsed,
    tasks,
    isBackendOnline,
    isSyncing,
    syncWithBackend,
    openNotificationCenter,
    unreadNotificationCount = 0,
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
      className={`hidden md:flex flex-col glass-sidebar h-screen sticky top-0 transition-all duration-300 select-none z-30 ${isSidebarCollapsed ? 'w-20' : 'w-72'
        }`}
    >
      {/* Brand Header */}
      <div className="p-4 border-b border-white/60 dark:border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          {/* Logo icon */}
          <div className="w-13 h-13 flex items-center justify-center shrink-0">
            <img
              src="/logo.png"
              alt="NIYANTRAN Logo"
              className="w-12 h-12 object-contain drop-shadow-md select-none"
              draggable={false}
            />
          </div>

          {!isSidebarCollapsed && (
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="app-brand-title font-sora text-2xl font-[700] tracking-[-1.5px] text-[#243C32] dark:text-[#E8F3EC] leading-tight">
                  {THEME_CONFIG.name}
                </span>
              </div>
              <p
                className="text-[11.5px] font-mono tracking-tight text-[#718579] dark:text-[#9BB3A5] mt-1 font-semibold whitespace-nowrap select-all"
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
          className="p-1.5 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0 ml-1"
          title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isSidebarCollapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
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
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group relative ${isActive
                  ? 'glass-nav-active font-semibold shadow-2xs'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/5 hover:text-slate-900 dark:hover:text-slate-200'
                } ${isSidebarCollapsed ? 'justify-center px-2' : ''}`
              }
              title={isSidebarCollapsed ? item.label : undefined}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`w-5 h-5 shrink-0 transition-colors ${isActive
                      ? 'text-[#568B75] dark:text-[#75B798]'
                      : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300'
                      }`}
                  />
                  {!isSidebarCollapsed && (
                    <span className="truncate flex-1">{item.label}</span>
                  )}
                  {!isSidebarCollapsed && item.badge !== undefined && item.badge > 0 && (
                    <span className="ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white/50 dark:bg-white/10 text-slate-600 dark:text-slate-400 border border-white/60 dark:border-white/10">
                      {item.badge}
                    </span>
                  )}
                  {isSidebarCollapsed && item.badge !== undefined && item.badge > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#568B75] dark:bg-[#75B798]" />
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
          className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-colors cursor-pointer ${isSidebarCollapsed ? 'justify-center px-1.5' : ''
            } ${isBackendOnline
              ? 'bg-emerald-50/80 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200/80 dark:border-emerald-800/60'
              : 'bg-amber-50/80 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200/80 dark:border-amber-800/60'
            }`}
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${isBackendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
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
            className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-slate-200 transition-colors cursor-pointer ${isSidebarCollapsed ? 'justify-center px-1' : ''
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
            onClick={openNotificationCenter}
            className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-slate-200 transition-colors relative cursor-pointer"
            title="Important Deadline Notifications"
            aria-label="Important Deadline Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadNotificationCount > 0 ? (
              <span className="absolute -top-1 -right-1 min-w-[15px] h-3.5 px-1 rounded-full bg-rose-500 text-white text-[8.5px] font-bold flex items-center justify-center leading-none shadow-xs">
                {unreadNotificationCount > 99 ? '99+' : unreadNotificationCount}
              </span>
            ) : (
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-[#568B75] dark:bg-[#75B798]" />
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}
