/**
 * NIYANTRA Date Utilities
 * Ensures dynamic date evaluation without hardcoded calendar freezes.
 */

export function getTodayString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function isDateToday(dateStr) {
  if (!dateStr) return false;
  return dateStr === getTodayString();
}

export function isDateOverdue(dueDateStr, isCompleted = false) {
  if (!dueDateStr || isCompleted) return false;
  return dueDateStr < getTodayString();
}

export function getDaysRemaining(targetDateStr) {
  if (!targetDateStr) return 0;
  const target = new Date(targetDateStr);
  const today = new Date(getTodayString());
  const diffTime = target - today;
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

export function formatFriendlyDate(dateStr) {
  if (!dateStr) return '';
  const today = getTodayString();
  if (dateStr === today) return 'Today';
  
  const target = new Date(dateStr + 'T00:00:00');
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(target);
}

/**
 * Dynamic Task Urgency Calculator (⚡ Due Soon)
 * Rules:
 * - Deadline within 48 hours (diffDays 0 to 2) -> '⚡ Due Soon' or '⚡ Due Today'
 * - Deadline in the past (diffDays < 0) -> 'Overdue'
 * - Never shows on completed tasks
 * - Does NOT alter underlying task priority
 */
export function getTaskUrgency(dueDateStr, isCompleted = false) {
  if (!dueDateStr || isCompleted) {
    return { isUrgent: false, isOverdue: false, isDueSoon: false, isDueToday: false, label: null, badgeClass: null };
  }

  const diffDays = getDaysRemaining(dueDateStr);

  if (diffDays < 0) {
    return {
      isUrgent: true,
      isOverdue: true,
      isDueSoon: false,
      isDueToday: false,
      label: 'Overdue',
      badgeClass: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50',
    };
  }

  if (diffDays === 0) {
    return {
      isUrgent: true,
      isOverdue: false,
      isDueSoon: true,
      isDueToday: true,
      label: '⚡ Due Today',
      badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50',
    };
  }

  if (diffDays <= 2) {
    return {
      isUrgent: true,
      isOverdue: false,
      isDueSoon: true,
      isDueToday: false,
      label: '⚡ Due Soon',
      badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50',
    };
  }

  return { isUrgent: false, isOverdue: false, isDueSoon: false, isDueToday: false, label: null, badgeClass: null };
}
