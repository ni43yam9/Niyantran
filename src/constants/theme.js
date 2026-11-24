/**
 * NIYANTRA Design Tokens & Theme Constants
 * Themes: Sage Serenity (Light) + Forest Glass (Dark)
 * Centralized design system definitions with glassmorphism support.
 */

export const THEME_CONFIG = {
  name: 'NIYANTRAN',
  tagline: 'I for N@49_89#41_84@73',
  version: '2.0.0 (Phase 10K)',
  palette: {
    light: {
      name: 'Sage Serenity',
      bgMain: '#E4EEE7',
      gradient1: '#C9DFD1',
      gradient2: '#DDE9E0',
      primary: '#568B75',
      accent: '#A3C9A8',
      textMain: '#243C32',
      textSecondary: '#718579',
      glassCard: 'rgba(255, 255, 255, 0.52)',
      glassBorder: 'rgba(255, 255, 255, 0.70)',
    },
    dark: {
      name: 'Forest Glass',
      bgMain: '#101C18',
      gradient1: '#1C3930',
      gradient2: '#172B25',
      primary: '#75B798',
      accent: '#A3D9B1',
      textMain: '#E8F3EC',
      textSecondary: '#9BB3A5',
      glassCard: 'rgba(255, 255, 255, 0.065)',
      glassBorder: 'rgba(255, 255, 255, 0.12)',
    },
  },
};

// Priority design tokens with exact theme values
export const PRIORITY_CONFIG = {
  High: {
    label: 'High',
    colorLight: '#DC6B6B',
    colorDark: '#F08080',
    color: '#DC6B6B',
    badge: 'bg-[#DC6B6B]/15 text-[#8F3131] border-[#DC6B6B]/30 dark:bg-[#F08080]/15 dark:text-[#F08080] dark:border-[#F08080]/30',
    dot: 'bg-[#DC6B6B] dark:bg-[#F08080]',
    iconColor: 'text-[#DC6B6B] dark:text-[#F08080]',
  },
  Medium: {
    label: 'Medium',
    colorLight: '#D69A50',
    colorDark: '#E8B76C',
    color: '#D69A50',
    badge: 'bg-[#D69A50]/15 text-[#8F591E] border-[#D69A50]/30 dark:bg-[#E8B76C]/15 dark:text-[#E8B76C] dark:border-[#E8B76C]/30',
    dot: 'bg-[#D69A50] dark:bg-[#E8B76C]',
    iconColor: 'text-[#D69A50] dark:text-[#E8B76C]',
  },
  Low: {
    label: 'Low',
    colorLight: '#7295B5',
    colorDark: '#82B4D8',
    color: '#7295B5',
    badge: 'bg-[#7295B5]/15 text-[#3D6385] border-[#7295B5]/30 dark:bg-[#82B4D8]/15 dark:text-[#82B4D8] dark:border-[#82B4D8]/30',
    dot: 'bg-[#7295B5] dark:bg-[#82B4D8]',
    iconColor: 'text-[#7295B5] dark:text-[#82B4D8]',
  },
};

// Status design tokens with exact theme values
export const STATUS_CONFIG = {
  Pending: {
    label: 'Pending',
    badge: 'bg-white/40 text-[#718579] border-white/60 dark:bg-white/5 dark:text-[#9BB3A5] dark:border-white/10',
    dot: 'bg-[#718579] dark:bg-[#9BB3A5]',
  },
  'In Progress': {
    label: 'In Progress',
    badge: 'bg-[#568B75]/15 text-[#243C32] border-[#568B75]/30 dark:bg-[#75B798]/15 dark:text-[#A3D9B1] dark:border-[#75B798]/30',
    dot: 'bg-[#568B75] dark:bg-[#75B798]',
  },
  Completed: {
    label: 'Completed',
    colorLight: '#568B75',
    colorDark: '#75B798',
    badge: 'bg-[#568B75]/20 text-[#243C32] border-[#568B75]/40 dark:bg-[#75B798]/20 dark:text-[#75B798] dark:border-[#75B798]/40',
    dot: 'bg-[#568B75] dark:bg-[#75B798]',
  },
  Overdue: {
    label: 'Overdue',
    badge: 'bg-[#DC6B6B]/20 text-[#8F3131] border-[#DC6B6B]/35 dark:bg-[#F08080]/20 dark:text-[#F08080] dark:border-[#F08080]/35',
    dot: 'bg-[#DC6B6B] dark:bg-[#F08080]',
  },
};

// Task Type design tokens
export const TASK_TYPES = [
  { id: 'Daily', label: 'Daily', badge: 'bg-[#568B75]/10 text-[#395E4E] border-[#568B75]/25 dark:bg-[#75B798]/10 dark:text-[#A3D9B1] dark:border-[#75B798]/25' },
  { id: 'Short-Term', label: 'Short-Term', badge: 'bg-[#A3C9A8]/30 text-[#243C32] border-[#A3C9A8]/40 dark:bg-[#A3D9B1]/15 dark:text-[#E8F3EC] dark:border-[#A3D9B1]/30' },
  { id: 'Long-Term', label: 'Long-Term', badge: 'bg-[#7295B5]/15 text-[#3D6385] border-[#7295B5]/30 dark:bg-[#82B4D8]/15 dark:text-[#82B4D8] dark:border-[#82B4D8]/30' },
  { id: 'One-Time', label: 'One-Time', badge: 'bg-[#D69A50]/15 text-[#8F591E] border-[#D69A50]/30 dark:bg-[#E8B76C]/15 dark:text-[#E8B76C] dark:border-[#E8B76C]/30' },
  { id: 'Occasional', label: 'Occasional', badge: 'bg-white/40 text-[#506558] border-white/60 dark:bg-white/5 dark:text-[#9BB3A5] dark:border-white/10' },
];

// Goal Type tokens
export const GOAL_TYPES = [
  { id: 'Short-Term', label: 'Short-Term Goal', badge: 'bg-[#568B75]/15 text-[#243C32] border-[#568B75]/30 dark:bg-[#75B798]/15 dark:text-[#A3D9B1] dark:border-[#75B798]/30' },
  { id: 'Long-Term', label: 'Long-Term Goal', badge: 'bg-[#A3C9A8]/30 text-[#243C32] border-[#A3C9A8]/45 dark:bg-[#A3D9B1]/15 dark:text-[#E8F3EC] dark:border-[#A3D9B1]/30' },
];

// Category badges
export const CATEGORY_CONFIG = {
  Academic: {
    label: 'Academic',
    badge: 'bg-[#7295B5]/15 text-[#3D6385] border-[#7295B5]/30 dark:bg-[#82B4D8]/15 dark:text-[#82B4D8] dark:border-[#82B4D8]/30',
  },
  Coding: {
    label: 'Coding & Tech',
    badge: 'bg-[#568B75]/15 text-[#243C32] border-[#568B75]/30 dark:bg-[#75B798]/15 dark:text-[#75B798] dark:border-[#75B798]/30',
  },
  Career: {
    label: 'Career & Research',
    badge: 'bg-[#4D9673]/15 text-[#2D5A45] border-[#4D9673]/30 dark:bg-[#75C69A]/15 dark:text-[#75C69A] dark:border-[#75C69A]/30',
  },
  Personal: {
    label: 'Personal',
    badge: 'bg-white/40 text-[#506558] border-white/60 dark:bg-white/5 dark:text-[#9BB3A5] dark:border-white/10',
  },
  Health: {
    label: 'Health & Fitness',
    badge: 'bg-[#D69A50]/15 text-[#8F591E] border-[#D69A50]/30 dark:bg-[#E8B76C]/15 dark:text-[#E8B76C] dark:border-[#E8B76C]/30',
  },
  Reading: {
    label: 'Reading & Learning',
    badge: 'bg-[#A3C9A8]/30 text-[#243C32] border-[#A3C9A8]/40 dark:bg-[#A3D9B1]/15 dark:text-[#E8F3EC] dark:border-[#A3D9B1]/30',
  },
};
