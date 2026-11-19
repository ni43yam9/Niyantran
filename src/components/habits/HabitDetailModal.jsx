import { useState, useMemo } from 'react';
import {
  Flame,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  AlertCircle,
  Calendar as CalendarIcon,
  Award,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { useTheme } from '../../context/ThemeContext';
import { getTodayString } from '../../utils/dateUtils';

export function HabitDetailModal({
  isOpen,
  onClose,
  habit,
  onToggleDate,
}) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // Navigation for the full calendar view
  const [viewDate, setViewDate] = useState(() => new Date());

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth(); // 0-indexed

  const monthName = viewDate.toLocaleString('en-US', { month: 'long' });
  const todayStr = getTodayString();

  const prevMonth = () => {
    setViewDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setViewDate(new Date(year, month + 1, 1));
  };

  const resetToCurrentMonth = () => {
    setViewDate(new Date());
  };

  // Generate calendar days for the viewed month
  const calendarDays = useMemo(() => {
    const firstDayOfMonth = new Date(year, month, 1);
    const lastDayOfMonth = new Date(year, month + 1, 0);
    const totalDays = lastDayOfMonth.getDate();

    // Monday-based start index (0 = Mon, ..., 6 = Sun)
    const firstDayIndex = (firstDayOfMonth.getDay() + 6) % 7;

    const days = [];

    // Leading padding from previous month
    for (let i = 0; i < firstDayIndex; i++) {
      days.push({ isPadding: true, key: `pad-${i}` });
    }

    // Days in current month
    for (let d = 1; d <= totalDays; d++) {
      const mStr = String(month + 1).padStart(2, '0');
      const dStr = String(d).padStart(2, '0');
      const dateStr = `${year}-${mStr}-${dStr}`;

      days.push({
        isPadding: false,
        dayNumber: d,
        dateStr,
        isPast: dateStr < todayStr,
        isToday: dateStr === todayStr,
        isFuture: dateStr > todayStr,
        key: dateStr,
      });
    }

    return days;
  }, [year, month, todayStr]);

  // Aggregate completion statistics
  const stats = useMemo(() => {
    if (!habit) {
      return {
        completedInMonth: 0,
        missedInMonth: 0,
        monthRate: 0,
        totalCompletedAllTime: 0,
        bestDay: 'N/A',
        worstDay: 'N/A',
      };
    }

    const completedDates = habit.completedDates || {};
    const totalCompletedAllTime = Object.keys(completedDates).length;

    let completedInMonth = 0;
    let missedInMonth = 0;

    calendarDays.forEach((day) => {
      if (day.isPadding) return;
      const isDone = Boolean(completedDates[day.dateStr]);
      if (isDone) {
        completedInMonth++;
      } else if (day.isPast) {
        missedInMonth++;
      }
    });

    const elapsedDays = completedInMonth + missedInMonth;
    const monthRate =
      elapsedDays > 0 ? Math.round((completedInMonth / elapsedDays) * 100) : 0;

    return {
      completedInMonth,
      missedInMonth,
      monthRate,
      totalCompletedAllTime,
    };
  }, [habit, calendarDays]);

  // Day-of-Week breakdown: "how many days I complete, which day I can't do"
  const dayOfWeekData = useMemo(() => {
    if (!habit) return [];
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const completedDates = habit.completedDates || {};

    const breakdown = dayNames.map((name, idx) => {
      // Find all past or today days in this month matching this weekday
      const daysForWeekday = calendarDays.filter((d) => {
        if (d.isPadding || d.isFuture) return false;
        const dateObj = new Date(`${d.dateStr}T00:00:00`);
        const dayIdx = (dateObj.getDay() + 6) % 7;
        return dayIdx === idx;
      });

      let completedCount = 0;
      let missedCount = 0;

      daysForWeekday.forEach((d) => {
        if (completedDates[d.dateStr]) {
          completedCount++;
        } else if (d.isPast) {
          missedCount++;
        }
      });

      return {
        day: name,
        Completed: completedCount,
        Missed: missedCount,
      };
    });

    return breakdown;
  }, [habit, calendarDays]);

  // Behavioral insight from the breakdown
  const insight = useMemo(() => {
    if (!dayOfWeekData.length) return null;

    let maxCompleted = -1;
    let bestDay = '';
    let maxMissed = -1;
    let hardestDay = '';

    dayOfWeekData.forEach((item) => {
      if (item.Completed > maxCompleted) {
        maxCompleted = item.Completed;
        bestDay = item.day;
      }
      if (item.Missed > maxMissed) {
        maxMissed = item.Missed;
        hardestDay = item.day;
      }
    });

    if (maxCompleted === 0 && maxMissed === 0) {
      return 'No historical logs recorded for this month yet. Check off today to begin logging data!';
    }

    return (
      <>
        Consistency is highest on{' '}
        <span className="font-bold text-emerald-600 dark:text-emerald-400">
          {bestDay}s
        </span>{' '}
        ({maxCompleted} logged). Most missed targets occur on{' '}
        <span className="font-bold text-rose-500 dark:text-rose-400">
          {hardestDay}s
        </span>{' '}
        ({maxMissed} missed).
      </>
    );
  }, [dayOfWeekData]);

  if (!isOpen || !habit) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={habit.name}
      subtitle={`Habit Performance & Historical Calendar Tracker • ${habit.target}`}
      size="2xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Interactive: Click any date to toggle completion</span>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* 1. Metric Overview Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs">
            <div className="flex items-center justify-between text-xs text-slate-500 font-semibold uppercase tracking-wider">
              <span>Current Streak</span>
              <Flame className="w-4 h-4 text-amber-500 fill-amber-500" />
            </div>
            <p className="text-xl sm:text-2xl font-extrabold text-amber-600 dark:text-amber-400 mt-1">
              {habit.streak || 0} <span className="text-xs font-normal text-slate-400">days</span>
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Consecutive consistency</p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs">
            <div className="flex items-center justify-between text-xs text-slate-500 font-semibold uppercase tracking-wider">
              <span>Completed Days</span>
              <Check className="w-4 h-4 text-emerald-500" />
            </div>
            <p className="text-xl sm:text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
              {stats.completedInMonth}{' '}
              <span className="text-xs font-normal text-slate-400">
                ({stats.totalCompletedAllTime} all-time)
              </span>
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Logged this month</p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs">
            <div className="flex items-center justify-between text-xs text-slate-500 font-semibold uppercase tracking-wider">
              <span>Missed Days</span>
              <X className="w-4 h-4 text-rose-500" />
            </div>
            <p className="text-xl sm:text-2xl font-extrabold text-rose-500 dark:text-rose-400 mt-1">
              {stats.missedInMonth}{' '}
              <span className="text-xs font-normal text-slate-400">days</span>
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">Auto-crossed in {monthName}</p>
          </div>

          <div className="bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs">
            <div className="flex items-center justify-between text-xs text-slate-500 font-semibold uppercase tracking-wider">
              <span>Success Rate</span>
              <TrendingUp className="w-4 h-4 text-indigo-500" />
            </div>
            <p className="text-xl sm:text-2xl font-extrabold text-indigo-600 dark:text-indigo-400 mt-1">
              {stats.monthRate}%
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">{monthName} reliability</p>
          </div>
        </div>

        {/* 2. Completion vs. Missed Chart by Day of Week */}
        <div className="bg-white dark:bg-[#111827] border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-2xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Award className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <h3 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Completion vs. Missed by Day of Week
              </h3>
            </div>
            <span className="text-xs text-slate-400">
              {monthName} {year}
            </span>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 mb-4">
            Highlights which days you reliably complete this habit and which days you struggle.
          </p>

          <div className="h-52 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={dayOfWeekData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={isDark ? '#1E293B' : '#F1F5F9'}
                />
                <XAxis
                  dataKey="day"
                  stroke={isDark ? '#94A3B8' : '#64748B'}
                  fontSize={11}
                  tickLine={false}
                />
                <YAxis
                  stroke={isDark ? '#94A3B8' : '#64748B'}
                  fontSize={11}
                  allowDecimals={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#0F172A' : '#FFFFFF',
                    borderColor: isDark ? '#334155' : '#E2E8F0',
                    borderRadius: '0.75rem',
                    fontSize: '12px',
                  }}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: '11px', paddingBottom: '8px' }}
                />
                <Bar
                  dataKey="Completed"
                  fill="#10B981"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="Missed"
                  fill="#F43F5E"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {insight && (
            <div className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/70 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
              <div>{insight}</div>
            </div>
          )}
        </div>

        {/* 3. Whole Month Calendar of Tick and Cross */}
        <div className="bg-white dark:bg-[#111827] border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-2xs space-y-4">
          {/* Calendar Header with Navigation */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <CalendarIcon className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <h3 className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Full Calendar View (Tick & Cross Matrix)
              </h3>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={prevMonth}
                className="p-1 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="Previous month"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="text-xs font-bold text-slate-800 dark:text-slate-200 min-w-[120px] text-center">
                {monthName} {year}
              </span>

              <button
                type="button"
                onClick={nextMonth}
                className="p-1 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="Next month"
              >
                <ChevronRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={resetToCurrentMonth}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
              >
                Today
              </button>
            </div>
          </div>

          {/* 7-Column Day-of-Week Labels */}
          <div className="grid grid-cols-7 gap-1.5 sm:gap-2 text-center">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
              <span
                key={day}
                className="text-[11px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 pb-1"
              >
                {day}
              </span>
            ))}
          </div>

          {/* Calendar Grid Cells */}
          <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
            {calendarDays.map((day) => {
              if (day.isPadding) {
                return (
                  <div
                    key={day.key}
                    className="h-10 sm:h-12 rounded-xl bg-slate-50/30 dark:bg-slate-900/10 border border-transparent"
                  />
                );
              }

              const isDone = Boolean(
                habit.completedDates && habit.completedDates[day.dateStr]
              );
              const isMissed = !isDone && day.isPast;
              const isTodayPending = !isDone && day.isToday;

              return (
                <button
                  key={day.key}
                  type="button"
                  onClick={() => onToggleDate(habit.id, day.dateStr)}
                  className={`h-11 sm:h-13 rounded-xl p-1 flex flex-col items-center justify-between border transition-all cursor-pointer relative group ${
                    isDone
                      ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800/80 hover:bg-emerald-100'
                      : isMissed
                      ? 'bg-rose-50/70 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900/60 hover:bg-rose-100/80'
                      : isTodayPending
                      ? 'bg-white dark:bg-slate-800 border-2 border-indigo-500 shadow-sm ring-2 ring-indigo-500/20'
                      : 'bg-slate-50/50 dark:bg-slate-900/30 border-slate-200/70 dark:border-slate-800 hover:border-slate-300'
                  }`}
                  title={`${day.dateStr} - Click to toggle completion`}
                >
                  {/* Date number */}
                  <span
                    className={`text-[10px] font-mono leading-none ${
                      day.isToday
                        ? 'font-bold px-1.5 py-0.5 rounded-full bg-indigo-600 text-white'
                        : isDone
                        ? 'font-semibold text-emerald-700 dark:text-emerald-400'
                        : isMissed
                        ? 'font-semibold text-rose-600 dark:text-rose-400'
                        : 'text-slate-400 dark:text-slate-500'
                    }`}
                  >
                    {day.dayNumber}
                  </span>

                  {/* Icon status indicator */}
                  <div className="flex items-center justify-center my-auto">
                    {isDone ? (
                      <span className="w-5 h-5 rounded-lg bg-emerald-500 text-white flex items-center justify-center shadow-xs">
                        <Check className="w-3 h-3 stroke-[3]" />
                      </span>
                    ) : isMissed ? (
                      <span className="w-5 h-5 rounded-lg bg-rose-500/15 text-rose-600 dark:text-rose-400 flex items-center justify-center">
                        <X className="w-3.5 h-3.5 stroke-[3]" />
                      </span>
                    ) : isTodayPending ? (
                      <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
                    ) : (
                      <span className="text-[10px] text-slate-300 dark:text-slate-700">•</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Calendar Status Legend */}
          <div className="flex items-center justify-center gap-4 text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800 flex-wrap">
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-md bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">✓</span>
              <span>Completed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-md bg-rose-50 dark:bg-rose-950/50 text-rose-500 border border-rose-200 dark:border-rose-900/60 flex items-center justify-center text-[10px] font-bold">✕</span>
              <span>Missed (Auto-crossed)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-md bg-white dark:bg-slate-800 border-2 border-indigo-500 flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
              </span>
              <span>Today</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-md bg-slate-50 dark:bg-slate-800 text-slate-400 flex items-center justify-center text-[10px]">•</span>
              <span>Upcoming</span>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
