import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  CheckSquare,
  Target,
  CalendarCheck2,
  Menu,
  X,
  CalendarDays,
  Flame,
  Hourglass,
  BarChart3,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';

export function MobileBottomNav() {
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const { tasks } = useApp();
  const pendingCount = tasks.filter((t) => t.status !== 'Completed').length;

  const mainTabs = [
    { id: 'dashboard', label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { id: 'tasks', label: 'Tasks', path: '/tasks', icon: CheckSquare, badge: pendingCount },
    { id: 'goals', label: 'Goals', path: '/goals', icon: Target },
    { id: 'planner', label: 'Planner', path: '/planner', icon: CalendarCheck2 },
  ];

  const moreTabs = [
    { id: 'calendar', label: 'Calendar', path: '/calendar', icon: CalendarDays },
    { id: 'habits', label: 'Habits', path: '/habits', icon: Flame },
    { id: 'focus', label: 'Focus Mode', path: '/focus', icon: Hourglass },
    { id: 'analytics', label: 'Analytics', path: '/analytics', icon: BarChart3 },
  ];

  return (
    <>
      {/* Slide-up Sheet for "More" Navigation */}
      {isMoreOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex flex-col justify-end">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMoreOpen(false)}
          />
          <div className="relative glass-modal rounded-t-3xl border-t border-white/60 dark:border-white/10 p-5 shadow-2xl z-50 animate-in slide-in-from-bottom duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-white/50 dark:border-white/10">
              <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                Additional Modules
              </span>
              <button
                type="button"
                onClick={() => setIsMoreOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-white/40 dark:hover:bg-white/10"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2.5 py-4">
              {moreTabs.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    onClick={() => setIsMoreOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 p-3 rounded-2xl text-sm font-medium transition-colors ${
                        isActive
                          ? 'glass-nav-active font-semibold'
                          : 'glass-card text-slate-700 dark:text-slate-300'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4 text-[#568B75] dark:text-[#75B798] shrink-0" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Persistent Bottom Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 glass-header border-t border-white/60 dark:border-white/10 px-2 py-1 flex items-center justify-around select-none">
        {mainTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <NavLink
              key={tab.id}
              to={tab.path}
              end={tab.path === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center flex-1 py-1.5 px-1 rounded-xl text-[10px] font-medium transition-all relative ${
                  isActive
                    ? 'text-[#568B75] dark:text-[#75B798] font-bold'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`
              }
            >
              <div className="relative">
                <Icon className="w-5 h-5" />
                {tab.badge !== undefined && tab.badge > 0 && (
                  <span className="absolute -top-1.5 -right-2 bg-indigo-600 text-white text-[9px] font-bold h-4 w-4 rounded-full flex items-center justify-center border-2 border-white dark:border-[#111827]">
                    {tab.badge > 9 ? '9+' : tab.badge}
                  </span>
                )}
              </div>
              <span className="mt-1 leading-none">{tab.label}</span>
            </NavLink>
          );
        })}

        {/* More Button */}
        <button
          type="button"
          onClick={() => setIsMoreOpen(!isMoreOpen)}
          className={`flex flex-col items-center justify-center flex-1 py-1.5 px-1 rounded-xl text-[10px] font-medium transition-colors ${
            isMoreOpen
              ? 'text-indigo-600 dark:text-indigo-400 font-semibold'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          <Menu className="w-5 h-5" />
          <span className="mt-1 leading-none">More</span>
        </button>
      </nav>
    </>
  );
}
