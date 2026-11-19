import { CheckCircle2, Clock, CheckSquare, Target, TrendingUp, AlertTriangle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Card } from '../common/Card';

export function OverviewCards() {
  const { metrics } = useApp();

  const cards = [
    {
      id: 'total-tasks',
      title: 'Total Tasks',
      value: metrics.totalTasks,
      subtitle: 'Across all horizons',
      trend: '+4 added this week',
      trendType: 'positive',
      icon: CheckSquare,
      iconColor: 'text-indigo-600 dark:text-indigo-400',
      iconBg: 'bg-indigo-50 dark:bg-indigo-950/50',
      borderAccent: 'hover:border-indigo-300 dark:hover:border-indigo-800',
    },
    {
      id: 'completed-tasks',
      title: 'Completed Tasks',
      value: metrics.completedTasks,
      subtitle: `${metrics.completionRate}% completion rate`,
      trend: '+6 done this week',
      trendType: 'positive',
      icon: CheckCircle2,
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/50',
      borderAccent: 'hover:border-emerald-300 dark:hover:border-emerald-800',
    },
    {
      id: 'pending-tasks',
      title: 'Pending Tasks',
      value: metrics.pendingTasks,
      subtitle: `${metrics.dueTodayCount || 0} due today • ${metrics.overdueCount || 0} overdue`,
      trend: metrics.overdueCount > 0 ? `${metrics.overdueCount} overdue` : 'On schedule',
      trendType: metrics.overdueCount > 0 ? 'warning' : 'positive',
      icon: Clock,
      iconColor: 'text-amber-600 dark:text-amber-400',
      iconBg: 'bg-amber-50 dark:bg-amber-950/50',
      borderAccent: 'hover:border-amber-300 dark:hover:border-amber-800',
    },
    {
      id: 'active-goals',
      title: 'Active Goals',
      value: metrics.activeGoals,
      subtitle: `${metrics.activeGoals} strategic roadmaps`,
      trend: 'Compounding daily',
      trendType: 'positive',
      icon: Target,
      iconColor: 'text-purple-600 dark:text-purple-400',
      iconBg: 'bg-purple-50 dark:bg-purple-950/50',
      borderAccent: 'hover:border-purple-300 dark:hover:border-purple-800',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <Card
            key={card.id}
            hover
            className={`transition-all duration-200 ${card.borderAccent}`}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  {card.title}
                </p>
                <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1">
                  {card.value}
                </h3>
              </div>
              <div className={`p-2.5 rounded-xl ${card.iconBg} ${card.iconColor} shrink-0`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400 font-medium">
                {card.subtitle}
              </span>
              <span
                className={`inline-flex items-center gap-1 font-semibold text-[11px] ${
                  card.trendType === 'warning'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-emerald-600 dark:text-emerald-400'
                }`}
              >
                {card.trendType === 'warning' ? (
                  <AlertTriangle className="w-3 h-3" />
                ) : (
                  <TrendingUp className="w-3 h-3" />
                )}
                {card.trend}
              </span>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
