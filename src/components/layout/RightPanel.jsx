import { useState } from 'react';
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  Sparkles,
  X,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { ProgressBar } from '../common/ProgressBar';
import { PRIORITY_CONFIG } from '../../constants/theme';

export function RightPanel({ onClose }) {
  const { upcomingDeadlines, topPriorities } = useApp();
  const [currentDate, setCurrentDate] = useState(() => new Date());

  // Calendar calculations
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayIndex = new Date(year, month, 1).getDay();

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const days = [];
  for (let i = 0; i < firstDayIndex; i++) {
    days.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    days.push(d);
  }

  const todayNow = new Date();
  const isToday = (day) => {
    return (
      day === todayNow.getDate() &&
      month === todayNow.getMonth() &&
      year === todayNow.getFullYear()
    );
  };

  return (
    <aside className="w-80 shrink-0 glass-sidebar border-l border-r-0 border-white/60 dark:border-white/10 p-5 space-y-6 overflow-y-auto h-screen sticky top-0 hidden xl:block select-none">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/60 dark:border-white/10">
        <div className="flex items-center gap-2">
          <CalendarIcon className="w-4 h-4 text-[#568B75] dark:text-[#75B798]" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
            Agenda & Priorities
          </h2>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-white/40 dark:hover:bg-white/10 transition-colors"
            title="Hide right panel"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 1. Mini Calendar */}
      <div className="glass-card p-3.5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
            {monthNames[month]} {year}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={prevMonth}
              className="p-1 rounded hover:bg-white dark:hover:bg-slate-800 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
              aria-label="Previous month"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={nextMonth}
              className="p-1 rounded hover:bg-white dark:hover:bg-slate-800 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
              aria-label="Next month"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Days of week header */}
        <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold text-slate-400 dark:text-slate-500 mb-1.5">
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
            <span key={d}>{d}</span>
          ))}
        </div>

        {/* Day grid */}
        <div className="grid grid-cols-7 gap-1 text-center text-xs">
          {days.map((d, index) => {
            if (!d) {
              return <div key={`empty-${index}`} className="h-7 w-7" />;
            }
            const today = isToday(d);
            const hasDeadlines = d === 14 || d === 18 || d === 20 || d === 22;
            return (
              <button
                key={`day-${d}`}
                type="button"
                className={`h-7 w-7 mx-auto rounded-lg flex flex-col items-center justify-center font-medium transition-all text-xs relative ${
                  today
                    ? 'bg-[#568B75] dark:bg-[#75B798] text-white dark:text-[#101C18] font-bold shadow-xs'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-white/40 dark:hover:bg-white/10'
                }`}
              >
                <span>{d}</span>
                {hasDeadlines && !today && (
                  <span className="w-1 h-1 rounded-full bg-rose-500 absolute bottom-0.5" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Upcoming Deadlines */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-[#DC6B6B] dark:text-[#F08080]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Upcoming Deadlines
            </h3>
          </div>
          <span className="text-[10px] font-semibold text-slate-400">
            {upcomingDeadlines.length} items
          </span>
        </div>

        <div className="space-y-2">
          {upcomingDeadlines.map((item) => (
            <div
              key={item.id}
              className={`p-2.5 rounded-xl border text-xs transition-colors ${
                item.isOverdue
                  ? 'bg-[#DC6B6B]/15 border-[#DC6B6B]/30 text-slate-800 dark:text-slate-200'
                  : 'glass-card'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span
                  className={`font-semibold line-clamp-1 ${
                    item.isOverdue
                      ? 'text-rose-700 dark:text-rose-300'
                      : 'text-slate-800 dark:text-slate-200'
                  }`}
                >
                  {item.title}
                </span>
                {item.isOverdue ? (
                  <span className="shrink-0 text-[10px] font-bold text-rose-600 dark:text-rose-400 uppercase tracking-tight">
                    Overdue
                  </span>
                ) : (
                  <span className="shrink-0 text-[10px] text-slate-400">
                    {item.date}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-100 dark:border-slate-800/60">
                <span className="text-[10px] text-slate-500 dark:text-slate-400">
                  {item.category}
                </span>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.2 rounded ${
                    PRIORITY_CONFIG[item.priority]?.badge || ''
                  }`}
                >
                  {item.priority}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Top Priorities */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Flag className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Top Priorities
            </h3>
          </div>
          <Sparkles className="w-3.5 h-3.5 text-amber-500" />
        </div>

        <div className="space-y-2.5">
          {topPriorities.map((p) => (
            <div
              key={p.id}
              className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/60 shadow-2xs space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100 leading-snug">
                  {p.title}
                </h4>
                <span
                  className={`text-[9px] uppercase tracking-wide font-bold px-1.5 py-0.2 rounded shrink-0 ${
                    PRIORITY_CONFIG[p.priority]?.badge || ''
                  }`}
                >
                  {p.priority}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-1">
                {p.reason}
              </p>
              <div className="pt-1">
                <ProgressBar
                  value={p.progress}
                  size="sm"
                  color={p.progress > 70 ? 'emerald' : 'indigo'}
                  showLabel={false}
                />
                <div className="flex justify-between items-center text-[10px] text-slate-400 dark:text-slate-500 mt-1">
                  <span>{p.category}</span>
                  <span className="font-medium text-slate-600 dark:text-slate-300">
                    {p.progress}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
