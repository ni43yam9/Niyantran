import {
  Clock,
  CheckSquare,
  Edit3,
  Trash2,
  Plus,
  Sparkles,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';
import { ProgressBar } from '../common/ProgressBar';
import { PRIORITY_CONFIG, STATUS_CONFIG } from '../../constants/theme';
import { useApp } from '../../context/AppContext';
import { getDaysRemaining } from '../../utils/dateUtils';

export function GoalCard({ goal, onEdit, onDelete }) {
  const { tasks, openAddTaskModal } = useApp();

  // Find linked tasks for this goal
  const linkedTasks = tasks.filter((t) => t.associatedGoalId === goal.id);
  const completedLinkedTasks = linkedTasks.filter((t) => t.status === 'Completed').length;
  const totalLinked = linkedTasks.length > 0 ? linkedTasks.length : (goal.totalTasks || 0);
  const completedCount = linkedTasks.length > 0 ? completedLinkedTasks : (goal.completedTasks || 0);

  const priorityInfo = PRIORITY_CONFIG[goal.priority] || PRIORITY_CONFIG.High;
  const statusInfo = STATUS_CONFIG[goal.status] || STATUS_CONFIG['In Progress'];

  // Days remaining calculation
  const diffDays = getDaysRemaining(goal.targetDate);

  const isShortTerm = goal.type === 'Short-Term';

  return (
    <Card hover className="flex flex-col justify-between space-y-4">
      <div className="space-y-3">
        {/* Header / Badges */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Goal Type badge */}
            <Badge
              size="sm"
              className={
                isShortTerm
                  ? 'bg-primary-50 text-primary-700 border-primary-200/60 dark:bg-primary-950/40 dark:text-primary-300 dark:border-primary-800/40'
                  : 'bg-accent-50 text-accent-700 border-accent-200/60 dark:bg-accent-950/40 dark:text-accent-300 dark:border-accent-800/40'
              }
            >
              {isShortTerm ? '⚡ Short-Term Goal' : '🎯 Long-Term Goal'}
            </Badge>

            {/* Category */}
            <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-white/40 dark:bg-white/5 px-2 py-0.5 rounded border border-white/60 dark:border-white/10">
              {goal.category}
            </span>

            {/* Priority */}
            <Badge
              size="sm"
              className={priorityInfo.badge}
              dot
              dotColor={priorityInfo.dot}
            >
              {goal.priority}
            </Badge>
          </div>

          {/* Action options */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => onEdit(goal)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-white/40 dark:hover:bg-white/5 transition-colors"
              title="Edit goal"
            >
              <Edit3 className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => onDelete(goal.id)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50/50 dark:hover:bg-rose-950/30 transition-colors"
              title="Delete goal"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Goal Title */}
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white leading-snug">
            {goal.title}
          </h3>
          {goal.description && (
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              {goal.description}
            </p>
          )}
        </div>

        {/* Key Milestone Pill */}
        {goal.keyMilestone && (
          <div className="p-2.5 rounded-xl bg-white/40 dark:bg-white/5 border border-white/60 dark:border-white/10 flex items-start gap-2 text-xs">
            <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Milestone:
              </span>{' '}
              <span className="text-slate-500 dark:text-slate-400">
                {goal.keyMilestone}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Progress & Metadata Section */}
      <div className="space-y-3 pt-2 border-t border-white/60 dark:border-white/10">
        {/* Progress Bar with label */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <span>Goal Progress</span>
              <span className="text-[10px] text-slate-400">
                ({goal.progress}%)
              </span>
            </span>
            <Badge
              size="sm"
              className={statusInfo.badge}
              dot
              dotColor={statusInfo.dot}
            >
              {goal.status}
            </Badge>
          </div>
          <ProgressBar
            value={goal.progress}
            size="md"
            color={goal.progress > 70 ? 'emerald' : isShortTerm ? 'indigo' : 'blue'}
          />
        </div>

        {/* Associated Tasks & Timeline */}
        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
          {/* Associated Tasks count */}
          <div className="p-2 rounded-lg bg-white/40 dark:bg-white/5 border border-white/60 dark:border-white/10">
            <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <CheckSquare className="w-3.5 h-3.5 text-primary-600 dark:text-primary-400" />
              <span className="text-[11px] font-medium">Tasks</span>
            </div>
            <p className="font-bold text-slate-800 dark:text-slate-200 mt-0.5">
              {completedCount} / {totalLinked} Completed
            </p>
          </div>

          {/* Timeline / Target Date */}
          <div className="p-2 rounded-lg bg-white/40 dark:bg-white/5 border border-white/60 dark:border-white/10">
            <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-[11px] font-medium">Target Date</span>
            </div>
            <p className="font-bold text-slate-800 dark:text-slate-200 mt-0.5 truncate">
              {goal.targetDate}{' '}
              {diffDays > 0 ? (
                <span className="text-[10px] font-normal text-slate-400">
                  ({diffDays}d left)
                </span>
              ) : null}
            </p>
          </div>
        </div>

        {/* Add task to this goal shortcut */}
        <button
          type="button"
          onClick={() =>
            openAddTaskModal({
              associatedGoalId: goal.id,
              category: goal.category === 'Technical' ? 'Coding' : goal.category,
            })
          }
          className="w-full py-1.5 px-3 rounded-lg border border-dashed border-white/60 dark:border-white/10 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-primary-600 hover:border-primary-400 dark:hover:text-primary-400 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add linked task</span>
        </button>
      </div>
    </Card>
  );
}
