import {
  CheckCircle2,
  Circle,
  Clock,
  ArrowRight,
  Flag,
  Target,
  Plus,
  Calendar,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { Card, CardHeader } from '../common/Card';
import { Badge } from '../common/Badge';
import { ProgressBar } from '../common/ProgressBar';
import { PRIORITY_CONFIG } from '../../constants/theme';
import { getTodayString } from '../../utils/dateUtils';

export function TodayOverview() {
  const {
    tasks,
    toggleTaskCompletion,
    openAddTaskModal,
    upcomingDeadlines,
    topPriorities,
    isRightPanelOpen,
  } = useApp();

  const todayStr = getTodayString();
  const todayTasks = tasks.filter((t) => t.isToday || t.dueDate === todayStr);
  const completedToday = todayTasks.filter((t) => t.status === 'Completed').length;
  const progressPercent =
    todayTasks.length > 0 ? Math.round((completedToday / todayTasks.length) * 100) : 0;

  return (
    <div className={`grid grid-cols-1 ${isRightPanelOpen ? 'lg:grid-cols-3 xl:grid-cols-1' : 'lg:grid-cols-3'} gap-6`}>
      {/* Today's Tasks Section */}
      <div className={isRightPanelOpen ? 'lg:col-span-2 xl:col-span-1' : 'lg:col-span-2'}>
        <Card className="h-full flex flex-col">
          <CardHeader
            title="Today's Execution Agenda"
            subtitle={`${todayTasks.length} deliverables scheduled for today`}
            icon={Calendar}
            action={
              <Link
                to="/tasks"
                className="text-xs font-semibold text-[#568B75] dark:text-[#75B798] hover:text-[#467360] dark:hover:text-[#A3D9B1] flex items-center gap-1 transition-colors"
              >
                <span>View All Tasks</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            }
          />

          {/* Today's Progress Bar Banner */}
          <div className="p-4 rounded-2xl glass-card mb-4 space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-slate-700 dark:text-slate-300">
                Daily Completion Progress
              </span>
              <span className="text-[#568B75] dark:text-[#75B798]">
                {completedToday} of {todayTasks.length} Completed ({progressPercent}%)
              </span>
            </div>
            <ProgressBar
              value={progressPercent}
              color={progressPercent === 100 ? 'emerald' : 'indigo'}
              size="md"
            />
          </div>

          {/* Today's Task Items */}
          <div className="space-y-2.5 flex-1">
            {todayTasks.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-[#568B75] opacity-60" />
                <p className="text-sm font-medium">All tasks for today are completed!</p>
              </div>
            ) : (
              todayTasks.map((task) => {
                const isCompleted = task.status === 'Completed';
                const priorityInfo = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.Medium;

                return (
                  <div
                    key={task.id}
                    className={`group flex items-start justify-between gap-3 p-3 rounded-2xl transition-all duration-200 ${
                      isCompleted
                        ? 'glass-card border-[#568B75]/30 opacity-75'
                        : 'glass-card glass-card-hover'
                    }`}
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      {/* Interactive completion toggle */}
                      <button
                        type="button"
                        onClick={() => toggleTaskCompletion(task.id)}
                        className="mt-0.5 text-slate-400 hover:text-[#568B75] dark:hover:text-[#75B798] transition-colors shrink-0 cursor-pointer"
                        aria-label={isCompleted ? 'Mark pending' : 'Mark completed'}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="w-5 h-5 text-[#568B75] dark:text-[#75B798] fill-[#568B75]/20 dark:fill-[#75B798]/20" />
                        ) : (
                          <Circle className="w-5 h-5" />
                        )}
                      </button>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4
                            className={`text-sm font-semibold truncate ${
                              isCompleted
                                ? 'line-through text-slate-400 dark:text-slate-500'
                                : 'text-slate-900 dark:text-slate-100'
                            }`}
                          >
                            {task.title}
                          </h4>
                        </div>

                        {task.description && (
                          <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1 mt-0.5">
                            {task.description}
                          </p>
                        )}

                        {/* Badges / metadata */}
                        <div className="flex items-center gap-2 mt-2 flex-wrap text-xs">
                          {/* Priority badge */}
                          <Badge
                            size="sm"
                            className={priorityInfo.badge}
                            dot
                            dotColor={priorityInfo.dot}
                          >
                            {task.priority}
                          </Badge>

                          {/* Category badge */}
                          <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                            {task.category}
                          </span>

                          {/* Task type badge */}
                          <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                            {task.taskType}
                          </span>

                          {/* Associated Goal link */}
                          {task.associatedGoalTitle && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 dark:text-indigo-400 truncate max-w-[200px]">
                              <Target className="w-3 h-3 shrink-0" />
                              <span className="truncate">{task.associatedGoalTitle}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Quick add prompt at bottom */}
          <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80">
            <button
              type="button"
              onClick={() => openAddTaskModal({ isToday: true })}
              className="w-full py-2 px-3 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Add another task for today</span>
            </button>
          </div>
        </Card>
      </div>

      {/* Priorities & Deadlines Card (Integrated on mobile & tablet, hidden on xl when RightPanel is active) */}
      <div className={`space-y-6 ${isRightPanelOpen ? 'xl:hidden' : ''}`}>
        {/* Today's Priorities */}
        <Card>
          <CardHeader
            title="Strategic Priorities"
            subtitle="High-impact focus areas"
            icon={Flag}
          />
          <div className="space-y-3">
            {topPriorities.map((item) => (
              <div
                key={item.id}
                className="p-3 rounded-xl bg-slate-50/70 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 space-y-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                    {item.title}
                  </h4>
                  <span
                    className={`text-[9px] font-bold uppercase px-1.5 py-0.2 rounded shrink-0 ${
                      PRIORITY_CONFIG[item.priority]?.badge || ''
                    }`}
                  >
                    {item.priority}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-1">
                  {item.reason}
                </p>
                <div className="pt-1">
                  <ProgressBar value={item.progress} size="sm" color="indigo" />
                  <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                    <span>{item.category}</span>
                    <span className="font-medium text-slate-600 dark:text-slate-300">
                      {item.progress}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Upcoming Deadlines */}
        <Card>
          <CardHeader
            title="Upcoming Deadlines"
            subtitle="Academic & project delivery dates"
            icon={Clock}
          />
          <div className="space-y-2">
            {upcomingDeadlines.slice(0, 3).map((item) => (
              <div
                key={item.id}
                className={`p-2.5 rounded-xl border text-xs flex items-center justify-between gap-2 ${
                  item.isOverdue
                    ? 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/40 text-rose-700 dark:text-rose-300'
                    : 'bg-slate-50/70 dark:bg-slate-900/50 border-slate-200/80 dark:border-slate-800 text-slate-800 dark:text-slate-200'
                }`}
              >
                <div className="min-w-0">
                  <p className="font-semibold truncate">{item.title}</p>
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                    {item.category}
                  </p>
                </div>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded shrink-0 ${
                    item.isOverdue
                      ? 'bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300 uppercase'
                      : 'bg-slate-200/60 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  {item.date}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
