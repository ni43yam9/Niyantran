import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Polyfill localStorage for node/vitest environment
const store = new Map();
const localStorageMock = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, val) => store.set(key, String(val)),
  removeItem: (key) => store.delete(key),
  clear: () => store.clear(),
  get length() {
    return store.size;
  },
};

globalThis.localStorage = localStorageMock;
if (typeof window !== 'undefined') {
  window.localStorage = localStorageMock;
} else {
  globalThis.window = {
    localStorage: localStorageMock,
  };
}

import {
  evaluateImportantDeadlines,
  checkAndDispatchDeadlineNotifications,
  isNotificationSupported,
  getNotificationPermission,
  requestNotificationPermission,
  playNotificationChime,
} from '../src/services/notificationService';
import { getTodayString } from '../src/utils/dateUtils';

function getDateWithOffset(offsetDays) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

describe('Deadline Notification Service', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    const mockNotif = {
      permission: 'default',
      requestPermission: vi.fn().mockResolvedValue('default'),
    };
    window.Notification = mockNotif;
    globalThis.Notification = mockNotif;
  });

  describe('1. Browser API Permission & Capabilities', () => {
    it('detects notification support when window.Notification exists', () => {
      window.Notification = { permission: 'default' };
      expect(isNotificationSupported()).toBe(true);

      const oldNotification = window.Notification;
      delete window.Notification;
      expect(isNotificationSupported()).toBe(false);
      window.Notification = oldNotification;
    });

    it('returns permission string accurately', () => {
      window.Notification = { permission: 'granted' };
      expect(getNotificationPermission()).toBe('granted');

      window.Notification = { permission: 'denied' };
      expect(getNotificationPermission()).toBe('denied');
    });

    it('requests notification permission gracefully', async () => {
      window.Notification = {
        permission: 'default',
        requestPermission: vi.fn().mockResolvedValue('granted'),
      };

      const result = await requestNotificationPermission();
      expect(result).toBe('granted');
      expect(window.Notification.requestPermission).toHaveBeenCalled();
    });

    it('plays notification audio chime without throwing', () => {
      expect(() => playNotificationChime()).not.toThrow();
    });
  });

  describe('2. evaluateImportantDeadlines', () => {
    it('correctly categorizes overdue tasks', () => {
      const tasks = [
        {
          id: 't-overdue-1',
          title: 'Submit Tax Filings',
          dueDate: getDateWithOffset(-2),
          priority: 'High',
          category: 'Finance',
          status: 'In Progress',
        },
      ];

      const notifications = evaluateImportantDeadlines(tasks, []);
      expect(notifications.length).toBe(1);
      expect(notifications[0].urgency).toBe('OVERDUE');
      expect(notifications[0].isCritical).toBe(true);
      expect(notifications[0].message).toContain('Overdue by 2 days');
    });

    it('correctly categorizes due today tasks', () => {
      const tasks = [
        {
          id: 't-today-1',
          title: 'Client Sprint Review',
          dueDate: getTodayString(),
          priority: 'High',
          category: 'Work',
          status: 'Pending',
        },
      ];

      const notifications = evaluateImportantDeadlines(tasks, []);
      expect(notifications.length).toBe(1);
      expect(notifications[0].urgency).toBe('DUE_TODAY');
      expect(notifications[0].message).toBe('Due Today');
      expect(notifications[0].daysOffset).toBe(0);
    });

    it('correctly categorizes due soon tasks within 48 hours for High/Medium priorities', () => {
      const tasks = [
        {
          id: 't-soon-1',
          title: 'Prepare Slide Deck',
          dueDate: getDateWithOffset(1),
          priority: 'High',
          category: 'Work',
          status: 'In Progress',
        },
        {
          id: 't-soon-2',
          title: 'Buy Groceries',
          dueDate: getDateWithOffset(2),
          priority: 'Medium',
          category: 'Personal',
          status: 'Pending',
        },
        {
          id: 't-far-1',
          title: 'Annual Dental Checkup',
          dueDate: getDateWithOffset(10),
          priority: 'Low',
          category: 'Health',
          status: 'Pending',
        },
      ];

      const notifications = evaluateImportantDeadlines(tasks, []);
      expect(notifications.length).toBe(2);
      expect(notifications.some((n) => n.id === 'task-soon-t-soon-1')).toBe(true);
      expect(notifications.some((n) => n.id === 'task-soon-t-soon-2')).toBe(true);
      expect(notifications.some((n) => n.id === 'task-far-t-far-1')).toBe(false);
    });

    it('excludes completed tasks and goals', () => {
      const tasks = [
        {
          id: 't-done-1',
          title: 'Completed Task',
          dueDate: getDateWithOffset(-3),
          priority: 'High',
          status: 'Completed',
        },
      ];
      const goals = [
        {
          id: 'g-done-1',
          title: 'Finished Goal',
          targetDate: getDateWithOffset(-1),
          priority: 'High',
          status: 'Completed',
        },
      ];

      const notifications = evaluateImportantDeadlines(tasks, goals);
      expect(notifications.length).toBe(0);
    });

    it('correctly evaluates goals with overdue and due today target dates', () => {
      const goals = [
        {
          id: 'g-overdue-1',
          title: 'Launch SaaS MVP',
          targetDate: getDateWithOffset(-5),
          priority: 'High',
          category: 'Career',
          status: 'In Progress',
        },
        {
          id: 'g-today-1',
          title: 'Complete 10k Run Challenge',
          targetDate: getTodayString(),
          priority: 'High',
          category: 'Fitness',
          status: 'In Progress',
        },
      ];

      const notifications = evaluateImportantDeadlines([], goals);
      expect(notifications.length).toBe(2);
      expect(notifications.some((n) => n.urgency === 'OVERDUE' && n.type === 'goal')).toBe(true);
      expect(notifications.some((n) => n.urgency === 'DUE_TODAY' && n.type === 'goal')).toBe(true);
    });

    it('prioritizes critical notifications first', () => {
      const tasks = [
        {
          id: 't-low-soon',
          title: 'Casual Reading',
          dueDate: getDateWithOffset(2),
          priority: 'Medium',
          status: 'Pending',
        },
        {
          id: 't-high-overdue',
          title: 'Critical Server Patch',
          dueDate: getDateWithOffset(-4),
          priority: 'High',
          status: 'Pending',
        },
      ];

      const notifications = evaluateImportantDeadlines(tasks, []);
      expect(notifications[0].id).toBe('task-overdue-t-high-overdue');
      expect(notifications[0].isCritical).toBe(true);
    });
  });

  describe('3. checkAndDispatchDeadlineNotifications & Deduplication', () => {
    it('does not dispatch notifications if permission is not granted', async () => {
      window.Notification = {
        permission: 'default',
      };

      const tasks = [
        {
          id: 't-overdue-1',
          title: 'Critical Urgent Task',
          dueDate: getDateWithOffset(-1),
          priority: 'High',
          status: 'Pending',
        },
      ];

      const result = await checkAndDispatchDeadlineNotifications(tasks, []);
      expect(result.dispatchedCount).toBe(0);
      expect(result.reason).toBe('permission_not_granted');
    });

    it('dispatches and deduplicates notifications when permission is granted', async () => {
      const mockNotification = vi.fn();
      mockNotification.permission = 'granted';
      window.Notification = mockNotification;

      const tasks = [
        {
          id: 't-today-test',
          title: 'Important System Review',
          dueDate: getTodayString(),
          priority: 'High',
          category: 'Operations',
          status: 'Pending',
        },
      ];

      // First run should dispatch 1 notification
      const result1 = await checkAndDispatchDeadlineNotifications(tasks, []);
      expect(result1.dispatchedCount).toBe(1);

      // Second run immediately on same day should deduplicate and dispatch 0
      const result2 = await checkAndDispatchDeadlineNotifications(tasks, []);
      expect(result2.dispatchedCount).toBe(0);
    });

    it('prunes old dispatch records from localStorage', async () => {
      const mockNotification = vi.fn();
      mockNotification.permission = 'granted';
      window.Notification = mockNotification;

      // Seed an old timestamp (> 10 days ago)
      const oldTimestamp = Date.now() - 10 * 24 * 60 * 60 * 1000;
      localStorage.setItem(
        'niyantra_notified_deadlines',
        JSON.stringify({
          'ancient-task-2025-01-01': oldTimestamp,
        })
      );

      await checkAndDispatchDeadlineNotifications([], []);

      const stored = JSON.parse(localStorage.getItem('niyantra_notified_deadlines') || '{}');
      expect(stored['ancient-task-2025-01-01']).toBeUndefined();
    });
  });
});
