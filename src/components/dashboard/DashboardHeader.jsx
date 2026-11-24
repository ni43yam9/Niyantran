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
    <div className="glass-silver-gradient backdrop-blur-xl rounded-2xl p-5 sm:p-6 transition-all relative overflow-hidden group">
      {/* Decorative ambient silver-emerald shimmer blobs for high contrast */}
      <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-gradient-to-br from-[#568B75]/25 dark:from-[#75B798]/20 to-transparent blur-2xl pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-44 h-44 rounded-full bg-gradient-to-tr from-slate-200/50 dark:from-white/10 to-transparent blur-2xl pointer-events-none" />

      <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#568B75] dark:text-[#75B798]">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10 shadow-2xs">
              <CalendarIcon className="w-3.5 h-3.5" />
              <span>{formattedDate}</span>
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
              <Clock className="w-3 h-3" />
              <span>Academic & Personal Focus</span>
            </span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            {getGreeting()}, <span className="text-[#568B75] dark:text-[#75B798]">{user.name}</span>
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
            className="w-full sm:w-auto shadow-md shadow-[#568B75]/25 dark:shadow-[#75B798]/25"
          >
            Quick Add Task
          </Button>
        </div>
      </div>
    </div>
  );
}
