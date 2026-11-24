/**
 * NIYANTRA Notification Service
 * Handles browser desktop notifications, sound alerts, and deadline evaluation.
 */

import { getTodayString, getDaysRemaining } from '../utils/dateUtils';

const NOTIFIED_DEADLINES_STORAGE_KEY = 'niyantra_notified_deadlines';

/**
 * Check if the browser supports Notification API
 */
export function isNotificationSupported() {
  return typeof window !== 'undefined' && Boolean(window.Notification);
}

/**
 * Get current browser notification permission
 * Returns 'granted', 'denied', 'default', or 'unsupported'
 */
export function getNotificationPermission() {
  if (!isNotificationSupported()) return 'unsupported';
  return window.Notification.permission;
}

/**
 * Request notification permission from the user
 */
export async function requestNotificationPermission() {
  if (!isNotificationSupported()) return 'unsupported';
  try {
    const permission = await window.Notification.requestPermission();
    return permission;
  } catch (error) {
    console.error('[NotificationService] Error requesting permission:', error);
    return window.Notification.permission;
  }
}

/**
 * Play a gentle, crisp dual-tone audio chime using the Web Audio API
 */
export function playNotificationChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    // Dual-tone harmonic chime: D5 (587.3 Hz) to A5 (880 Hz)
    osc.frequency.setValueAtTime(587.33, now);
    osc.frequency.exponentialRampToValueAtTime(880.0, now + 0.12);

    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.45);
  } catch {
    // Non-fatal if audio context is blocked by user gesture policy
  }
}

/**
 * Send a native browser desktop notification with fallback
 */
export async function sendNativeNotification(title, options = {}) {
  if (!isNotificationSupported() || window.Notification.permission !== 'granted') {
    return null;
  }

  const defaultOptions = {
    icon: '/logo.png',
    badge: '/favicon.png',
    vibrate: [200, 100, 200],
    ...options,
  };

  try {
    playNotificationChime();

    // Prefer service worker showNotification if available (works on mobile/PWA)
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.ready;
      if (registration && registration.showNotification) {
        return await registration.showNotification(title, defaultOptions);
      }
    }

    return new window.Notification(title, defaultOptions);
  } catch (error) {
    console.error('[NotificationService] Failed to display native notification:', error);
    try {
      return new window.Notification(title, defaultOptions);
    } catch {
      return null;
    }
  }
}

/**
 * Evaluates tasks and goals to extract important deadlines
 * Returns prioritized list of active deadline notifications
 */
export function evaluateImportantDeadlines(tasks = [], goals = []) {
  const notifications = [];
  const today = getTodayString();

  // 1. Evaluate Tasks
  tasks.forEach((task) => {
    if (task.status === 'Completed' || !task.dueDate) return;

    const diffDays = getDaysRemaining(task.dueDate);

    if (diffDays < 0) {
      // Overdue
      const daysOverdue = Math.abs(diffDays);
      notifications.push({
        id: `task-overdue-${task.id}`,
        sourceId: task.id,
        type: 'task',
        urgency: 'OVERDUE',
        priority: task.priority || 'Medium',
        title: task.title,
        dueDate: task.dueDate,
        category: task.category || 'General',
        message: `Overdue by ${daysOverdue} day${daysOverdue > 1 ? 's' : ''}`,
        isCritical: task.priority === 'High' || daysOverdue >= 3,
        daysOffset: diffDays,
      });
    } else if (diffDays === 0) {
      // Due Today
      notifications.push({
        id: `task-today-${task.id}`,
        sourceId: task.id,
        type: 'task',
        urgency: 'DUE_TODAY',
        priority: task.priority || 'Medium',
        title: task.title,
        dueDate: task.dueDate,
        category: task.category || 'General',
        message: 'Due Today',
        isCritical: task.priority === 'High',
        daysOffset: 0,
      });
    } else if (diffDays <= 2 && (task.priority === 'High' || task.priority === 'Medium')) {
      // Due Soon (Within 48 hours for High/Medium priorities)
      notifications.push({
        id: `task-soon-${task.id}`,
        sourceId: task.id,
        type: 'task',
        urgency: 'DUE_SOON',
        priority: task.priority || 'Medium',
        title: task.title,
        dueDate: task.dueDate,
        category: task.category || 'General',
        message: diffDays === 1 ? 'Due Tomorrow' : `Due in ${diffDays} days`,
        isCritical: task.priority === 'High' && diffDays === 1,
        daysOffset: diffDays,
      });
    }
  });

  // 2. Evaluate Goals with targetDate
  goals.forEach((goal) => {
    if (goal.status === 'Completed' || !goal.targetDate) return;

    const diffDays = getDaysRemaining(goal.targetDate);

    if (diffDays < 0) {
      const daysOverdue = Math.abs(diffDays);
      notifications.push({
        id: `goal-overdue-${goal.id}`,
        sourceId: goal.id,
        type: 'goal',
        urgency: 'OVERDUE',
        priority: goal.priority || 'High',
        title: goal.title,
        dueDate: goal.targetDate,
        category: goal.category || 'Goal',
        message: `Milestone target missed by ${daysOverdue} day${daysOverdue > 1 ? 's' : ''}`,
        isCritical: true,
        daysOffset: diffDays,
      });
    } else if (diffDays === 0) {
      notifications.push({
        id: `goal-today-${goal.id}`,
        sourceId: goal.id,
        type: 'goal',
        urgency: 'DUE_TODAY',
        priority: goal.priority || 'High',
        title: goal.title,
        dueDate: goal.targetDate,
        category: goal.category || 'Goal',
        message: 'Milestone target date is Today',
        isCritical: true,
        daysOffset: 0,
      });
    } else if (diffDays <= 3 && goal.priority === 'High') {
      notifications.push({
        id: `goal-soon-${goal.id}`,
        sourceId: goal.id,
        type: 'goal',
        urgency: 'DUE_SOON',
        priority: goal.priority || 'High',
        title: goal.title,
        dueDate: goal.targetDate,
        category: goal.category || 'Goal',
        message: `Milestone due in ${diffDays} day${diffDays > 1 ? 's' : ''}`,
        isCritical: diffDays === 1,
        daysOffset: diffDays,
      });
    }
  });

  // Urgency ranking: OVERDUE Critical > DUE_TODAY Critical > OVERDUE > DUE_TODAY > DUE_SOON
  return notifications.sort((a, b) => {
    if (a.isCritical !== b.isCritical) return a.isCritical ? -1 : 1;
    if (a.daysOffset !== b.daysOffset) return a.daysOffset - b.daysOffset;
    if (a.priority === 'High' && b.priority !== 'High') return -1;
    if (b.priority === 'High' && a.priority !== 'High') return 1;
    return a.title.localeCompare(b.title);
  });
}

/**
 * Automatically evaluates deadlines and triggers browser notifications
 * for new or urgent deadlines that have not been notified today.
 */
export async function checkAndDispatchDeadlineNotifications(tasks = [], goals = []) {
  if (getNotificationPermission() !== 'granted') {
    return { dispatchedCount: 0, reason: 'permission_not_granted' };
  }

  const notifications = evaluateImportantDeadlines(tasks, goals);
  const today = getTodayString();

  let sentRecord = {};
  try {
    const raw = localStorage.getItem(NOTIFIED_DEADLINES_STORAGE_KEY);
    if (raw) sentRecord = JSON.parse(raw);
  } catch {
    sentRecord = {};
  }

  let dispatchedCount = 0;

  for (const item of notifications) {
    // Only dispatch native browser alert for Overdue, Due Today, or High-Priority Due Tomorrow
    const isAlertWorthy =
      item.urgency === 'OVERDUE' ||
      item.urgency === 'DUE_TODAY' ||
      (item.urgency === 'DUE_SOON' && item.isCritical);

    if (!isAlertWorthy) continue;

    // Deduplication key per item, urgency, and day
    const dedupKey = `${item.id}-${today}`;
    if (sentRecord[dedupKey]) continue;

    let alertTitle = '';
    if (item.urgency === 'OVERDUE') {
      alertTitle = `🚨 Overdue Deadline: ${item.title}`;
    } else if (item.urgency === 'DUE_TODAY') {
      alertTitle = `⚠️ Due Today: ${item.title}`;
    } else {
      alertTitle = `⚡ High Priority Deadline Tomorrow: ${item.title}`;
    }

    await sendNativeNotification(alertTitle, {
      body: `${item.message} • ${item.category} (${item.priority} Priority)`,
      tag: dedupKey,
      data: { sourceId: item.sourceId, type: item.type },
    });

    sentRecord[dedupKey] = Date.now();
    dispatchedCount++;
  }

  // Prune storage records older than 7 days
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const prunedRecord = {};
  Object.entries(sentRecord).forEach(([k, timestamp]) => {
    if (timestamp > sevenDaysAgo) {
      prunedRecord[k] = timestamp;
    }
  });

  try {
    localStorage.setItem(NOTIFIED_DEADLINES_STORAGE_KEY, JSON.stringify(prunedRecord));
  } catch {
    // Non-fatal if localStorage quota is tight
  }

  return { dispatchedCount, notifications };
}
