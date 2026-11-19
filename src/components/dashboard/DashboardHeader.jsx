import { Plus, Sparkles, Calendar as CalendarIcon, Clock } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Button } from '../common/Button';

export function DashboardHeader() {
  const { user, openAddTaskModal } = useApp();

  // Dynamic greeting based on time of day
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const formattedDate = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date());

  const motivationalQuotes = [
    '“Consistency over intensity. Small daily disciplined actions compound into extraordinary achievements.”',
    '“Master your daily execution to transform your long-term goals into reality.”',
    '“Focus on the process, calibrate your priorities, and let momentum carry you forward.”',
  ];

  return (
    <div className="bg-gradient-to-r from-white via-indigo-50/20 to-white dark:from-[#111827] dark:via-indigo-950/20 dark:to-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-card transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
            <CalendarIcon className="w-3.5 h-3.5" />
            <span>{formattedDate}</span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
              <Clock className="w-3 h-3" />
              <span>Academic & Personal Focus</span>
            </span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            {getGreeting()}, <span className="text-indigo-600 dark:text-indigo-400">{user.name}</span>
          </h2>

          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 italic max-w-2xl flex items-start gap-1.5 pt-1">
            <Sparkles className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <span>{motivationalQuotes[0]}</span>
          </p>
        </div>

        {/* Quick Add Button */}
        <div className="shrink-0 flex items-center gap-2 pt-2 sm:pt-0">
          <Button
            variant="primary"
            size="md"
            icon={Plus}
            onClick={() => openAddTaskModal()}
            className="w-full sm:w-auto shadow-md shadow-indigo-500/20"
          >
            Quick Add Task
          </Button>
        </div>
      </div>
    </div>
  );
}
