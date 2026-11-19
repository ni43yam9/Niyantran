import {
  CheckCircle2,
  Circle,
  Calendar,
  Clock,
  Target,
  Edit3,
  Trash2,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { PRIORITY_CONFIG, STATUS_CONFIG, CATEGORY_CONFIG } from '../../constants/theme';
import { isDateOverdue, getTaskUrgency } from '../../utils/dateUtils';

export function TaskCard({ task, onToggleComplete, onEdit, onDelete }) {
  const isCompleted = task.status === 'Completed';
  const isOverdue = isDateOverdue(task.dueDate, isCompleted);
  const urgency = getTaskUrgency(task.dueDate, isCompleted);

  const priorityInfo = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.Medium;
  const statusInfo = isOverdue
    ? STATUS_CONFIG.Overdue
    : STATUS_CONFIG[task.status] || STATUS_CONFIG.Pending;
  const categoryInfo = CATEGORY_CONFIG[task.category] || CATEGORY_CONFIG.Personal;

  return (
    <div
      className={`group relative rounded-xl border p-4 sm:p-5 transition-all duration-200 ${
        isCompleted
          ? 'bg-slate-50/50 dark:bg-slate-900/30 border-slate-200/60 dark:border-slate-800/60 opacity-80'
          : isOverdue
          ? 'bg-rose-50/20 dark:bg-rose-950/10 border-rose-200/80 dark:border-rose-900/40 hover:border-rose-300 shadow-card'
          : 'bg-white dark:bg-[#131B2E] border-slate-200/90 dark:border-slate-800/80 hover:border-indigo-200 dark:hover:border-indigo-900/60 hover:shadow-card-hover'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Checkbox and Content */}
        <div className="flex items-start gap-3.5 min-w-0 flex-1">
          {/* Checkbox */}
          <button
            type="button"
            onClick={() => onToggleComplete(task.id)}
            className="mt-0.5 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors shrink-0 cursor-pointer"
            aria-label={isCompleted ? 'Mark pending' : 'Mark completed'}
          >
            {isCompleted ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-500 fill-emerald-50 dark:fill-emerald-950" />
            ) : (
              <Circle className="w-5 h-5" />
            )}
          </button>

          {/* Details */}
          <div className="min-w-0 flex-1 space-y-2">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3
                  className={`text-base font-bold leading-tight ${
                    isCompleted
                      ? 'line-through text-slate-400 dark:text-slate-500'
                      : 'text-slate-900 dark:text-slate-100'
                  }`}
                >
                  {task.title}
                </h3>
              </div>
              {task.description && (
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                  {task.description}
                </p>
              )}
            </div>

            {/* Badges / Metadata row */}
            <div className="flex items-center gap-2 flex-wrap text-xs pt-1">
              {/* Priority */}
              <Badge
                size="sm"
                className={priorityInfo.badge}
                dot
                dotColor={priorityInfo.dot}
              >
                {task.priority} Priority
              </Badge>

              {/* Status */}
              <Badge
                size="sm"
                className={statusInfo.badge}
                dot
                dotColor={statusInfo.dot}
              >
                {isOverdue ? 'Overdue' : task.status}
              </Badge>

              {/* Category */}
              <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${categoryInfo.badge}`}>
                {task.category}
              </span>

              {/* Task Type */}
              <span className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-2.5 py-0.5 rounded-full border border-indigo-200/50 dark:border-indigo-800/50">
                {task.taskType}
              </span>

              {/* ⚡ Due Soon Dynamic Badge */}
              {urgency.label && !isOverdue && (
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border flex items-center gap-1 ${urgency.badgeClass}`}>
                  <span>⚡</span>
                  <span>{urgency.label}</span>
                </span>
              )}
            </div>

            {/* Timeline Dates & Associated Goal */}
            <div className="flex items-center gap-4 flex-wrap text-xs text-slate-500 dark:text-slate-400 pt-1">
              {/* Start Date */}
              {task.startDate && (
                <div className="flex items-center gap-1.5" title="Start date">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Start: {task.startDate}</span>
                </div>
              )}

              {/* Due Date */}
              {task.dueDate && (
                <div
                  className={`flex items-center gap-1.5 font-medium ${
                    isOverdue
                      ? 'text-rose-600 dark:text-rose-400 font-semibold'
                      : 'text-slate-600 dark:text-slate-300'
                  }`}
                  title="Due date"
                >
                  <Clock className="w-3.5 h-3.5" />
                  <span>Due: {task.dueDate}</span>
                </div>
              )}

              {/* Associated Goal */}
              {task.associatedGoalTitle && (
                <div
                  className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400 bg-indigo-50/60 dark:bg-indigo-950/40 px-2 py-0.5 rounded-md border border-indigo-200/40 dark:border-indigo-800/40 font-medium truncate max-w-xs"
                  title={`Linked Goal: ${task.associatedGoalTitle}`}
                >
                  <Target className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">Goal: {task.associatedGoalTitle}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons: Edit, Delete */}
        <div className="flex items-center gap-1 shrink-0 opacity-80 sm:opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            onClick={() => onEdit(task)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Edit task"
          >
            <Edit3 className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onDelete(task.id)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
            title="Delete task"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
