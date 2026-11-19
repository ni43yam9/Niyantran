import { useState, useMemo } from 'react';
import {
  Flame,
  Check,
  X,
  Plus,
  Trophy,
  Sparkles,
  Trash2,
  Target,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Card, CardHeader } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Input } from '../components/common/FormControls';
import { HabitDetailModal } from '../components/habits/HabitDetailModal';
import { useApp } from '../context/AppContext';
import { getTodayString } from '../utils/dateUtils';

// Calculate Monday of the week for a given offset (0 = current week, -1 = last week, etc.)
function getWeekStartDate(weekOffset = 0) {
  const now = new Date();
  now.setDate(now.getDate() + weekOffset * 7);
  const dayOfWeek = (now.getDay() + 6) % 7; // Mon=0 ... Sun=6
  const monday = new Date(now);
  monday.setDate(now.getDate() - dayOfWeek);
  monday.setHours(0, 0, 0, 0);
  return monday;
}

// Generate the 7 days (Mon-Sun) of the active week with date metadata
function getWeekDays(weekOffset = 0) {
  const monday = getWeekStartDate(weekOffset);
  const todayStr = getTodayString();
  const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return dayLabels.map((name, idx) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + idx);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const dateStr = `${year}-${month}-${day}`;

    return {
      name,
      idx,
      dateStr,
      dayNumber: d.getDate(),
      monthShort: d.toLocaleString('en-US', { month: 'short' }),
      isPast: dateStr < todayStr,
      isToday: dateStr === todayStr,
      isFuture: dateStr > todayStr,
    };
  });
}

export function Habits() {
  const { habits, toggleHabit, addHabit, deleteHabit } = useApp();
  const [weekOffset, setWeekOffset] = useState(0);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    target: '',
    streak: 0,
  });
  const [errors, setErrors] = useState({});
  const [selectedHabitId, setSelectedHabitId] = useState(null);

  const selectedHabit = useMemo(
    () => habits.find((h) => h.id === selectedHabitId) || null,
    [habits, selectedHabitId]
  );

  const activeWeekDays = useMemo(() => getWeekDays(weekOffset), [weekOffset]);

  const weekRangeLabel = useMemo(() => {
    const start = activeWeekDays[0];
    const end = activeWeekDays[6];
    return `${start.monthShort} ${start.dayNumber} – ${end.monthShort} ${end.dayNumber}`;
  }, [activeWeekDays]);

  // Dynamic streak calculation based on actual consecutive completion dates
  const calculateHabitStreak = (completedDates = {}, baseStreak = 0) => {
    const todayStr = getTodayString();
    let currentStreak = 0;
    let checkDate = new Date();

    if (completedDates[todayStr]) {
      currentStreak++;
      checkDate.setDate(checkDate.getDate() - 1);
    } else {
      checkDate.setDate(checkDate.getDate() - 1);
    }

    while (true) {
      const y = checkDate.getFullYear();
      const m = String(checkDate.getMonth() + 1).padStart(2, '0');
      const d = String(checkDate.getDate()).padStart(2, '0');
      const str = `${y}-${m}-${d}`;
      if (completedDates[str]) {
        currentStreak++;
        checkDate.setDate(checkDate.getDate() - 1);
      } else {
        break;
      }
    }

    if (currentStreak > 0 && baseStreak > 0) {
      return Math.max(currentStreak, baseStreak);
    }
    return currentStreak;
  };

  // Dynamic calculations for summary banner
  const { consistencyPct } = useMemo(() => {
    if (habits.length === 0) {
      return { consistencyPct: 0 };
    }

    let checks = 0;
    let elapsedDays = 0;
    activeWeekDays.forEach((day) => {
      if (day.isPast || day.isToday) {
        elapsedDays++;
      }
    });
    const divisorDays = elapsedDays > 0 ? elapsedDays : 7;
    const slots = habits.length * divisorDays;

    habits.forEach((h) => {
      activeWeekDays.forEach((day) => {
        if (h.completedDates && h.completedDates[day.dateStr]) {
          checks++;
        }
      });
    });

    const pct = slots > 0 ? Math.min(100, Math.round((checks / slots) * 100)) : 0;
    return {
      consistencyPct: pct,
    };
  }, [habits, activeWeekDays]);

  const toggleDateCheck = (habitId, dateStr) => {
    toggleHabit(habitId, dateStr);
  };

  const handleOpenModal = () => {
    setFormData({
      name: '',
      target: 'Daily',
      streak: 0,
    });
    setErrors({});
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setErrors({});
  };

  const handleFormChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const handleCreateHabit = (e) => {
    e.preventDefault();
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Habit name is required';
    } else if (formData.name.trim().length > 80) {
      newErrors.name = 'Habit name must be under 80 characters';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const streakVal = Math.max(0, parseInt(formData.streak, 10) || 0);
    const newHabit = {
      id: `h-${Date.now()}`,
      name: formData.name.trim(),
      target: formData.target.trim() || 'Daily',
      streak: streakVal,
      baseStreak: streakVal,
      completedDates: {},
      weekly: [0, 0, 0, 0, 0, 0, 0],
    };

    addHabit(newHabit);
    handleCloseModal();
  };

  const handleDeleteHabit = (habitId) => {
    deleteHabit(habitId);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Habit Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4.5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Weekly Consistency
            </span>
            <Trophy className="w-5 h-5 text-indigo-500" />
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-indigo-600 dark:text-indigo-400 mt-1">
            {consistencyPct}%
          </p>
        </div>

        <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4.5 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Monitored Rituals
            </span>
            <Sparkles className="w-5 h-5 text-emerald-500" />
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
            {habits.length}
          </p>
        </div>
      </div>

      {/* Habits List & Tracker */}
      <Card>
        <CardHeader
          title="Habit Architecture & Consistency Matrix"
          icon={Flame}
          action={
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={handleOpenModal}
            >
              New Habit
            </Button>
          }
        />

        {/* Week Navigator & Status Legend */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-4 border-b border-slate-100 dark:border-slate-800/80">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setWeekOffset((prev) => prev - 1)}
                className="p-1 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="Previous week"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setWeekOffset(0)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors cursor-pointer ${
                  weekOffset === 0
                    ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800/60'
                    : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                This Week
              </button>
              <button
                type="button"
                onClick={() => setWeekOffset((prev) => prev + 1)}
                className="p-1 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="Next week"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
              {weekRangeLabel}
            </span>
          </div>

          {/* Status Legend */}
          <div className="flex items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400 flex-wrap">
            <div className="flex items-center gap-1">
              <span className="w-3.5 h-3.5 rounded bg-emerald-500 text-white flex items-center justify-center text-[9px] font-bold">✓</span>
              <span>Done</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-3.5 h-3.5 rounded bg-rose-50 dark:bg-rose-950/50 text-rose-500 border border-rose-200 dark:border-rose-900/60 flex items-center justify-center text-[9px] font-bold">✕</span>
              <span>Missed</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-3.5 h-3.5 rounded bg-white dark:bg-slate-800 border-2 border-indigo-500 flex items-center justify-center">
                <span className="w-1 h-1 rounded-full bg-indigo-500" />
              </span>
              <span>Today</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-3.5 h-3.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center text-[10px]">•</span>
              <span>Upcoming</span>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {habits.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl p-6">
              <Flame className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                No Habits Tracked Yet
              </h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
                Build high-performance consistency by creating daily academic, health, or coding disciplines.
              </p>
              <Button variant="primary" size="sm" icon={Plus} onClick={handleOpenModal}>
                Create First Habit
              </Button>
            </div>
          ) : (
            habits.map((habit) => (
              <div
                key={habit.id}
                onClick={() => setSelectedHabitId(habit.id)}
                className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all hover:border-indigo-300 dark:hover:border-indigo-800/80 hover:bg-white dark:hover:bg-slate-900/70 cursor-pointer group"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="font-bold text-sm text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                      {habit.name}
                    </h4>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50">
                      {habit.target}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1 text-xs text-amber-600 dark:text-amber-400 font-semibold">
                    <Flame className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
                    <span>{calculateHabitStreak(habit.completedDates, habit.baseStreak || habit.streak || 0)} day streak</span>
                  </div>
                </div>

                <div
                  className="flex items-center justify-between md:justify-end gap-3"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Dynamic 7-day calendar matrix */}
                  <div className="flex items-center gap-1.5 sm:gap-2">
                    {activeWeekDays.map((day) => {
                      const isDone = Boolean(habit.completedDates && habit.completedDates[day.dateStr]);
                      const isMissed = !isDone && day.isPast;
                      const isTodayPending = !isDone && day.isToday;

                      return (
                        <div key={day.dateStr} className="text-center">
                          <div className="mb-1 flex flex-col items-center">
                            <span
                              className={`text-[10px] font-mono leading-tight ${
                                day.isToday
                                  ? 'font-bold text-indigo-600 dark:text-indigo-400'
                                  : 'text-slate-400 dark:text-slate-500'
                              }`}
                            >
                              {day.name}
                            </span>
                            <span
                              className={`text-[9px] font-semibold leading-tight ${
                                day.isToday
                                  ? 'px-1 rounded bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 font-bold'
                                  : 'text-slate-400 dark:text-slate-500'
                              }`}
                            >
                              {day.dayNumber}
                            </span>
                          </div>

                          <button
                            type="button"
                            onClick={() => toggleDateCheck(habit.id, day.dateStr)}
                            className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
                              isDone
                                ? 'bg-emerald-500 text-white shadow-xs border border-emerald-500 hover:bg-emerald-600 active:scale-95'
                                : isMissed
                                ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-500 dark:text-rose-400 border border-rose-200 dark:border-rose-900/60 hover:bg-rose-100 dark:hover:bg-rose-900/50 shadow-xs'
                                : isTodayPending
                                ? 'bg-white dark:bg-slate-800 border-2 border-indigo-500 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 shadow-sm ring-2 ring-indigo-500/20'
                                : 'bg-slate-50/70 dark:bg-slate-800/40 border border-dashed border-slate-200 dark:border-slate-800 text-slate-300 dark:text-slate-600 hover:border-slate-400 dark:hover:border-slate-600'
                            }`}
                            title={isDone ? 'Completed' : isMissed ? 'Missed' : day.isToday ? 'Today' : 'Upcoming'}
                          >
                            {isDone ? (
                              <Check className="w-3.5 h-3.5 sm:w-4 sm:h-4 stroke-[3]" />
                            ) : isMissed ? (
                              <X className="w-3.5 h-3.5 sm:w-4 sm:h-4 stroke-[3]" />
                            ) : isTodayPending ? (
                              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                            ) : (
                              <span className="text-[10px] font-bold text-slate-300 dark:text-slate-600">•</span>
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>

                  {/* Delete Button */}
                  <button
                    type="button"
                    onClick={() => handleDeleteHabit(habit.id)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                    title="Delete habit"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* New Habit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title="Create New Habit"
        subtitle="Define a recurring discipline to monitor daily consistency"
        size="md"
        footer={
          <div className="flex items-center justify-end gap-2.5">
            <Button variant="outline" size="sm" onClick={handleCloseModal}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" icon={Plus} onClick={handleCreateHabit}>
              Save Habit
            </Button>
          </div>
        }
      >
        <form onSubmit={handleCreateHabit} className="space-y-4">
          <Input
            id="habit-name"
            label="Habit Name"
            placeholder="e.g. Solve 2 LeetCode Problems, Morning Workout, Read 20 Pages"
            value={formData.name}
            onChange={(e) => handleFormChange('name', e.target.value)}
            error={errors.name}
            required
            autoFocus
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              id="habit-target"
              label="Frequency / Target"
              placeholder="e.g. Daily, 45 mins, 20 pages"
              value={formData.target}
              onChange={(e) => handleFormChange('target', e.target.value)}
              helperText="Repetition goal or duration target"
              icon={Target}
            />

            <Input
              id="habit-streak"
              type="number"
              label="Starting Streak (Days)"
              placeholder="0"
              min="0"
              value={formData.streak}
              onChange={(e) => handleFormChange('streak', e.target.value)}
              helperText="Current active streak if continuing"
              icon={Flame}
            />
          </div>
        </form>
      </Modal>

      {/* Habit Performance Chart & Full Month Calendar Modal */}
      <HabitDetailModal
        isOpen={Boolean(selectedHabit)}
        onClose={() => setSelectedHabitId(null)}
        habit={selectedHabit}
        onToggleDate={toggleDateCheck}
      />
    </div>
  );
}
