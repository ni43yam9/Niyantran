/**
 * NIYANTRA Design Tokens & Theme Constants
 * Tagline: "I for N@49_89#41_84@73"
 * Centralized design system definitions for light and dark themes.
 */

export const THEME_CONFIG = {
  name: 'NIYANTRA',
  tagline: 'I for N@49_89#41_84@73',
  version: '1.0.0 (Phase 1)',
};

// Priority design tokens
export const PRIORITY_CONFIG = {
  High: {
    label: 'High',
    color: '#EF4444',
    badge: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50',
    dot: 'bg-rose-500',
    iconColor: 'text-rose-500',
  },
  Medium: {
    label: 'Medium',
    color: '#F59E0B',
    badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50',
    dot: 'bg-amber-500',
    iconColor: 'text-amber-500',
  },
  Low: {
    label: 'Low',
    color: '#10B981',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50',
    dot: 'bg-emerald-500',
    iconColor: 'text-emerald-500',
  },
};

// Status design tokens
export const STATUS_CONFIG = {
  Pending: {
    label: 'Pending',
    badge: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    dot: 'bg-slate-400',
  },
  'In Progress': {
    label: 'In Progress',
    badge: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900/50',
    dot: 'bg-blue-500',
  },
  Completed: {
    label: 'Completed',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50',
    dot: 'bg-emerald-500',
  },
  Overdue: {
    label: 'Overdue',
    badge: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50',
    dot: 'bg-rose-500',
  },
};

// Task Type design tokens
export const TASK_TYPES = [
  { id: 'Daily', label: 'Daily', badge: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-900/50' },
  { id: 'Short-Term', label: 'Short-Term', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-900/50' },
  { id: 'Long-Term', label: 'Long-Term', badge: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-900/50' },
  { id: 'One-Time', label: 'One-Time', badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50' },
  { id: 'Occasional', label: 'Occasional', badge: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-900/50' },
];

// Goal Type tokens
export const GOAL_TYPES = [
  { id: 'Short-Term', label: 'Short-Term Goal', badge: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-900/50' },
  { id: 'Long-Term', label: 'Long-Term Goal', badge: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-900/50' },
];

// Category badges
export const CATEGORY_CONFIG = {
  Academic: {
    label: 'Academic',
    badge: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/50',
  },
  Coding: {
    label: 'Coding & Tech',
    badge: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:border-violet-800/50',
  },
  Career: {
    label: 'Career & Research',
    badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50',
  },
  Personal: {
    label: 'Personal',
    badge: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
  },
  Health: {
    label: 'Health & Fitness',
    badge: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/50',
  },
  Reading: {
    label: 'Reading & Learning',
    badge: 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-950/40 dark:text-cyan-300 dark:border-cyan-800/50',
  },
};
