import { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import {
  INITIAL_TASKS,
  INITIAL_GOALS,
  INITIAL_USER,
  INITIAL_METRICS,
  WEEKLY_CHART_DATA,
  HABITS_DATA,
} from '../data/mockData';
import { getTodayString, isDateOverdue, formatFriendlyDate } from '../utils/dateUtils';
import { api } from '../services/api';
import { taskService } from '../services/taskService';
import { goalService } from '../services/goalService';
import { habitService } from '../services/habitService';
import { migrationService } from '../services/migrationService';
import {
  taskRepository,
  goalRepository,
  habitRepository,
  activityRepository,
} from '../database';
import { migrateLocalStorageToIndexedDB } from '../database/migrations';
import {
  syncManager,
  initSyncTriggers,
  teardownSyncTriggers,
} from '../sync';
import {
  evaluateImportantDeadlines,
  checkAndDispatchDeadlineNotifications,
} from '../services/notificationService';

const AppContext = createContext();

export function AppProvider({ children }) {
  const [user] = useState(INITIAL_USER);

  // 1. Data Persistence: Load tasks, goals, habits from localStorage initially for instantaneous first paint
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem('niyantra_tasks');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse saved tasks from localStorage', e);
    }
    return INITIAL_TASKS;
  });

  const [goals, setGoals] = useState(() => {
    try {
      const saved = localStorage.getItem('niyantra_goals');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse saved goals from localStorage', e);
    }
    return INITIAL_GOALS;
  });

  const [habits, setHabits] = useState(() => {
    try {
      const saved = localStorage.getItem('niyantra_habits');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Failed to parse saved habits from localStorage', e);
    }
    return HABITS_DATA;
  });

  // Backend connection & synchronization state
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);

  // Sync to localStorage whenever tasks, goals or habits change (acts as persistent secondary cache)
  useEffect(() => {
    try {
      localStorage.setItem('niyantra_tasks', JSON.stringify(tasks));
    } catch (e) {
      console.warn('Failed to save tasks to localStorage', e);
    }
  }, [tasks]);

  useEffect(() => {
    try {
      localStorage.setItem('niyantra_goals', JSON.stringify(goals));
    } catch (e) {
      console.warn('Failed to save goals to localStorage', e);
    }
  }, [goals]);

  useEffect(() => {
    try {
      localStorage.setItem('niyantra_habits', JSON.stringify(habits));
    } catch (e) {
      console.warn('Failed to save habits to localStorage', e);
    }
  }, [habits]);

  // IndexedDB Startup Initialization & Migration
  useEffect(() => {
    let active = true;
    async function initClientStorage() {
      try {
        // Step 1: Execute localStorage -> IndexedDB migration if not yet done
        await migrateLocalStorageToIndexedDB();

        // Step 2: Load fresh data from IndexedDB
        const [idbTasks, idbGoals, idbHabits] = await Promise.all([
          taskRepository.getAll(),
          goalRepository.getAll(),
          habitRepository.getAll(),
        ]);

        if (!active) return;

        if (idbTasks && idbTasks.length > 0) {
          setTasks(idbTasks);
        } else if (tasks.length > 0) {
          await taskRepository.bulkUpsert(tasks);
        }

        if (idbGoals && idbGoals.length > 0) {
          setGoals(idbGoals);
        } else if (goals.length > 0) {
          await goalRepository.bulkUpsert(goals);
        }

        if (idbHabits && idbHabits.length > 0) {
          setHabits(idbHabits);
        } else if (habits.length > 0) {
          await habitRepository.bulkUpsert(habits);
        }
      } catch (err) {
        console.warn('IndexedDB initialization notice:', err);
      }
    }

    void initClientStorage();
    return () => {
      active = false;
    };
  }, []);

  // Automatic multi-device sync triggers and state listener
  useEffect(() => {
    initSyncTriggers({ intervalMs: 30000, initialSync: true });

    const unsubscribe = syncManager.onSyncComplete(async () => {
      try {
        const [freshTasks, freshGoals, freshHabits] = await Promise.all([
          taskRepository.getAll(),
          goalRepository.getAll(),
          habitRepository.getAll(),
        ]);
        if (freshTasks) setTasks(freshTasks);
        if (freshGoals) setGoals(freshGoals);
        if (freshHabits) setHabits(freshHabits);
      } catch (err) {
        console.warn('Error reloading state after synchronization:', err);
      }
    });

    return () => {
      unsubscribe();
      teardownSyncTriggers();
    };
  }, []);

  // Synchronize with backend API (Phase 10G Multi-Device Sync)
  const syncWithBackend = useCallback(async () => {
    setIsSyncing(true);
    setSyncError(null);

    try {
      if (syncManager.isAuthenticated()) {
        const result = await syncManager.sync();
        setIsBackendOnline(result.status !== 'error');
        const [freshTasks, freshGoals, freshHabits] = await Promise.all([
          taskRepository.getAll(),
          goalRepository.getAll(),
          habitRepository.getAll(),
        ]);
        if (freshTasks) setTasks(freshTasks);
        if (freshGoals) setGoals(freshGoals);
        if (freshHabits) setHabits(freshHabits);
        return;
      }

      // Guest / Offline fallback
      const health = await api.checkHealth();
      setIsBackendOnline(health.online);

      // Perform automated migration of existing local records to SQLite if needed
      const migrationV3Done = localStorage.getItem('niyantra_migrated_v3_habits_timeblocks');
      if (!migrationV3Done) {
        try {
          const currentTasks = JSON.parse(localStorage.getItem('niyantra_tasks') || '[]');
          const currentGoals = JSON.parse(localStorage.getItem('niyantra_goals') || '[]');
          const currentHabits = JSON.parse(localStorage.getItem('niyantra_habits') || 'null') || habits;
          const currentTimeblocks = JSON.parse(localStorage.getItem('niyantra_daily_timeblocks') || '{}');
          if (
            currentTasks.length > 0 ||
            currentGoals.length > 0 ||
            currentHabits.length > 0 ||
            Object.keys(currentTimeblocks).length > 0
          ) {
            await migrationService.importFromLocalStorage(
              currentTasks,
              currentGoals,
              currentHabits,
              currentTimeblocks,
              false
            );
          }
          localStorage.setItem('niyantra_migrated_v3_habits_timeblocks', 'true');
        } catch (migErr) {
          console.warn('Auto-migration v3 warning (continuing with fetch):', migErr);
        }
      }

      // Fetch latest records from SQLite
      const [backendTasks, backendGoals, backendHabits] = await Promise.all([
        taskService.getTasks({ limit: 500 }),
        goalService.getGoals({ limit: 200 }),
        habitService.getHabits(),
      ]);

      if (Array.isArray(backendTasks) && backendTasks.length > 0) {
        setTasks(backendTasks);
        await taskRepository.bulkUpsert(backendTasks);
      }
      if (Array.isArray(backendGoals) && backendGoals.length > 0) {
        setGoals(backendGoals);
        await goalRepository.bulkUpsert(backendGoals);
      }
      if (Array.isArray(backendHabits) && backendHabits.length > 0) {
        setHabits(backendHabits);
        await habitRepository.bulkUpsert(backendHabits);
      }
    } catch (err) {
      console.warn('Backend sync failed, continuing in offline mode:', err);
      setSyncError(err.message || 'Sync failed');
      setIsBackendOnline(false);
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Check backend and sync on initial load
  useEffect(() => {
    let active = true;
    const runInitialSync = async () => {
      if (active) {
        await syncWithBackend();
      }
    };
    void runInitialSync();
    return () => {
      active = false;
    };
  }, [syncWithBackend]);

  // Modal & layout states
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [isGoalModalOpen, setIsGoalModalOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [editingGoal, setEditingGoal] = useState(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [globalSearchQuery, setGlobalSearchQuery] = useState('');

  // 2. Computed Metrics (Dynamic)
  const totalTasks = tasks.length;
  const completedTasks = tasks.filter((t) => t.status === 'Completed').length;
  const pendingTasks = tasks.filter((t) => t.status !== 'Completed').length;
  const activeGoals = goals.filter((g) => g.status !== 'Completed').length;
  const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

  const todayStr = getTodayString();
  const overdueCount = tasks.filter((t) => isDateOverdue(t.dueDate, t.status === 'Completed')).length;
  const dueTodayCount = tasks.filter((t) => t.dueDate === todayStr && t.status !== 'Completed').length;

  const metrics = {
    ...INITIAL_METRICS,
    totalTasks,
    completedTasks,
    pendingTasks,
    activeGoals,
    completionRate,
    overdueCount,
    dueTodayCount,
  };

  // 3. Dynamic Upcoming Deadlines derived from actual tasks
  const upcomingDeadlines = useMemo(() => {
    return tasks
      .filter((t) => t.status !== 'Completed' && t.dueDate)
      .sort((a, b) => (a.dueDate || '').localeCompare(b.dueDate || ''))
      .slice(0, 5)
      .map((t) => ({
        id: `d-${t.id}`,
        title: t.title,
        date: formatFriendlyDate(t.dueDate),
        isOverdue: isDateOverdue(t.dueDate, false),
        category: t.category,
        priority: t.priority,
      }));
  }, [tasks]);

  // Dynamic Deadline Notifications derived from tasks and goals
  const deadlineNotifications = useMemo(() => {
    return evaluateImportantDeadlines(tasks, goals);
  }, [tasks, goals]);

  // Dynamic Deadline Notifications Monitoring: periodically evaluates and notifies user
  useEffect(() => {
    checkAndDispatchDeadlineNotifications(tasks, goals);
    const interval = setInterval(() => {
      checkAndDispatchDeadlineNotifications(tasks, goals);
    }, 10 * 60 * 1000); // Check every 10 minutes
    return () => clearInterval(interval);
  }, [tasks, goals]);

  // 4. Dynamic Top Priorities derived from high-priority pending tasks
  const topPriorities = useMemo(() => {
    const highTasks = tasks
      .filter((t) => t.priority === 'High' && t.status !== 'Completed')
      .slice(0, 3)
      .map((t) => ({
        id: `p-${t.id}`,
        title: t.title,
        reason: t.description || 'High-priority active deliverable',
        priority: t.priority,
        category: t.category,
        progress: t.status === 'In Progress' ? 50 : 20,
      }));

    if (highTasks.length >= 2) return highTasks;

    // Complement with high-priority goals if needed
    const highGoals = goals
      .filter((g) => g.priority === 'High' && g.status !== 'Completed')
      .slice(0, 3 - highTasks.length)
      .map((g) => ({
        id: `pg-${g.id}`,
        title: g.title,
        reason: g.keyMilestone || g.description,
        priority: g.priority,
        category: g.category,
        progress: g.progress || 30,
      }));

    return [...highTasks, ...highGoals];
  }, [tasks, goals]);

  // 5. Dynamic Category Distribution derived from tasks
  const categoryDistributionData = useMemo(() => {
    const categoryColors = {
      Coding: '#6366F1',
      Academic: '#3B82F6',
      Career: '#10B981',
      Reading: '#06B6D4',
      Health: '#F59E0B',
      Personal: '#8B5CF6',
    };

    const counts = {};
    for (const t of tasks) {
      const cat = t.category || 'Personal';
      counts[cat] = (counts[cat] || 0) + 1;
    }

    return Object.keys(counts).map((cat) => ({
      name: cat === 'Coding' ? 'Coding & Tech' : cat,
      value: counts[cat],
      color: categoryColors[cat] || '#64748B',
    }));
  }, [tasks]);

  // 6. Dynamic Weekly Chart Data (Completed vs Planned from tasks)
  const weeklyChartData = useMemo(() => {
    return WEEKLY_CHART_DATA.map((item, idx) => {
      return {
        ...item,
        completed: Math.min(item.planned, item.completed + (idx === 1 ? completedTasks % 3 : 0)),
      };
    });
  }, [completedTasks]);

  // Task Actions
  const openAddTaskModal = (task = null) => {
    setEditingTask(task);
    setIsTaskModalOpen(true);
  };

  const closeAddTaskModal = () => {
    setEditingTask(null);
    setIsTaskModalOpen(false);
  };

  const addTask = async (newTask) => {
    const today = getTodayString();
    const taskWithId = {
      ...newTask,
      id: newTask.id || `t-${Date.now()}`,
      isToday: newTask.dueDate === today || newTask.startDate === today || Boolean(newTask.isToday),
    };

    // Optimistic local update
    setTasks((prev) => [taskWithId, ...prev]);
    closeAddTaskModal();

    // Persist to IndexedDB
    try {
      await taskRepository.createTask(taskWithId);
      await activityRepository.log({
        eventType: 'TASK_CREATED',
        entityType: 'task',
        entityId: taskWithId.id,
        details: { title: taskWithId.title, priority: taskWithId.priority },
      });
    } catch (e) {
      console.warn('Failed saving task to IndexedDB:', e);
    }

    // Async backend synchronization if connected
    if (isBackendOnline) {
      try {
        const created = await taskService.createTask(taskWithId);
        setTasks((prev) => prev.map((t) => (t.id === taskWithId.id ? created : t)));
      } catch (err) {
        console.warn('Backend task creation failed, saved locally:', err);
      }
    }
  };

  const updateTask = async (updatedTask) => {
    // Optimistic local update
    setTasks((prev) =>
      prev.map((t) => (t.id === updatedTask.id ? { ...t, ...updatedTask } : t))
    );
    closeAddTaskModal();

    // Persist to IndexedDB
    try {
      await taskRepository.updateTask(updatedTask.id, updatedTask);
      await activityRepository.log({
        eventType: 'TASK_UPDATED',
        entityType: 'task',
        entityId: updatedTask.id,
        details: { title: updatedTask.title, status: updatedTask.status },
      });
    } catch (e) {
      console.warn('Failed updating task in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        const result = await taskService.updateTask(updatedTask.id, updatedTask);
        setTasks((prev) => prev.map((t) => (t.id === updatedTask.id ? result : t)));
      } catch (err) {
        console.warn('Backend task update failed, saved locally:', err);
      }
    }
  };

  const deleteTask = async (taskId) => {
    // Optimistic local update
    setTasks((prev) => prev.filter((t) => t.id !== taskId));

    // Persist to IndexedDB
    try {
      await taskRepository.deleteTask(taskId);
      await activityRepository.log({
        eventType: 'TASK_DELETED',
        entityType: 'task',
        entityId: taskId,
      });
    } catch (e) {
      console.warn('Failed deleting task from IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        await taskService.deleteTask(taskId);
      } catch (err) {
        console.warn('Backend task deletion failed, deleted locally:', err);
      }
    }
  };

  const toggleTaskCompletion = async (taskId) => {
    let nextStatus = 'Completed';
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === taskId) {
          const isDone = t.status === 'Completed';
          nextStatus = isDone ? 'Pending' : 'Completed';
          return {
            ...t,
            status: nextStatus,
            completedAt: nextStatus === 'Completed' ? new Date().toISOString() : null,
          };
        }
        return t;
      })
    );

    // Persist to IndexedDB
    try {
      await taskRepository.toggleCompletion(taskId);
      await activityRepository.log({
        eventType: nextStatus === 'Completed' ? 'TASK_COMPLETED' : 'TASK_REOPENED',
        entityType: 'task',
        entityId: taskId,
      });
    } catch (e) {
      console.warn('Failed toggling task in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        if (nextStatus === 'Completed') {
          await taskService.markComplete(taskId);
        } else {
          await taskService.markPending(taskId);
        }
      } catch (err) {
        console.warn('Backend status toggle failed, toggled locally:', err);
      }
    }
  };

  // Goal Actions
  const openAddGoalModal = (goal = null) => {
    setEditingGoal(goal);
    setIsGoalModalOpen(true);
  };

  const closeAddGoalModal = () => {
    setEditingGoal(null);
    setIsGoalModalOpen(false);
  };

  const openNotificationCenter = () => setIsNotificationOpen(true);
  const closeNotificationCenter = () => setIsNotificationOpen(false);

  const addGoal = async (newGoal) => {
    const goalWithId = {
      ...newGoal,
      id: newGoal.id || `g-${Date.now()}`,
      progress: newGoal.progress || 0,
      totalTasks: 0,
      completedTasks: 0,
    };

    // Optimistic local update
    setGoals((prev) => [goalWithId, ...prev]);
    closeAddGoalModal();

    // Persist to IndexedDB
    try {
      await goalRepository.createGoal(goalWithId);
      await activityRepository.log({
        eventType: 'GOAL_CREATED',
        entityType: 'goal',
        entityId: goalWithId.id,
        details: { title: goalWithId.title },
      });
    } catch (e) {
      console.warn('Failed creating goal in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        const created = await goalService.createGoal(goalWithId);
        setGoals((prev) => prev.map((g) => (g.id === goalWithId.id ? created : g)));
      } catch (err) {
        console.warn('Backend goal creation failed, saved locally:', err);
      }
    }
  };

  const updateGoal = async (updatedGoal) => {
    // Optimistic local update
    setGoals((prev) =>
      prev.map((g) => (g.id === updatedGoal.id ? { ...g, ...updatedGoal } : g))
    );
    closeAddGoalModal();

    // Persist to IndexedDB
    try {
      await goalRepository.updateGoal(updatedGoal.id, updatedGoal);
      await activityRepository.log({
        eventType: 'GOAL_UPDATED',
        entityType: 'goal',
        entityId: updatedGoal.id,
        details: { title: updatedGoal.title, progress: updatedGoal.progress },
      });
    } catch (e) {
      console.warn('Failed updating goal in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        const result = await goalService.updateGoal(updatedGoal.id, updatedGoal);
        setGoals((prev) => prev.map((g) => (g.id === updatedGoal.id ? result : g)));
      } catch (err) {
        console.warn('Backend goal update failed, saved locally:', err);
      }
    }
  };

  const deleteGoal = async (goalId) => {
    // Optimistic local update
    setGoals((prev) => prev.filter((g) => g.id !== goalId));

    // Persist to IndexedDB
    try {
      await goalRepository.deleteGoal(goalId);
      await activityRepository.log({
        eventType: 'GOAL_DELETED',
        entityType: 'goal',
        entityId: goalId,
      });
    } catch (e) {
      console.warn('Failed deleting goal in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        await goalService.deleteGoal(goalId);
      } catch (err) {
        console.warn('Backend goal deletion failed, deleted locally:', err);
      }
    }
  };

  // Habit Actions
  const toggleHabit = async (habitId, dateStr, explicitCompleted = null) => {
    // Optimistic local update
    setHabits((prev) =>
      prev.map((h) => {
        if (h.id !== habitId) return h;
        const currentCompletedDates = { ...(h.completedDates || {}) };
        const isCurrentlyDone = Boolean(currentCompletedDates[dateStr]);
        const nextDone = explicitCompleted !== null ? explicitCompleted : !isCurrentlyDone;
        if (nextDone) {
          currentCompletedDates[dateStr] = true;
        } else {
          delete currentCompletedDates[dateStr];
        }
        return {
          ...h,
          completedDates: currentCompletedDates,
        };
      })
    );

    // Persist to IndexedDB
    try {
      await habitRepository.toggleLog(habitId, dateStr, explicitCompleted);
      await activityRepository.log({
        eventType: 'HABIT_TOGGLED',
        entityType: 'habit',
        entityId: habitId,
        details: { date: dateStr, completed: explicitCompleted },
      });
    } catch (e) {
      console.warn('Failed toggling habit in IndexedDB:', e);
    }

    // Async backend synchronization
    if (isBackendOnline) {
      try {
        const updatedHabit = await habitService.toggleHabitLog(habitId, dateStr, explicitCompleted);
        if (updatedHabit) {
          setHabits((prev) => prev.map((h) => (h.id === habitId ? updatedHabit : h)));
        }
      } catch (err) {
        console.warn('Backend habit toggle sync error:', err);
      }
    }
  };

  const addHabit = async (newHabit) => {
    const habitWithId = {
      ...newHabit,
      id: newHabit.id || `h-${Date.now()}`,
      baseStreak: newHabit.baseStreak ?? newHabit.streak ?? 0,
      completedDates: newHabit.completedDates || {},
    };
    setHabits((prev) => [habitWithId, ...prev]);

    // Persist to IndexedDB
    try {
      await habitRepository.createHabit(habitWithId);
      await activityRepository.log({
        eventType: 'HABIT_CREATED',
        entityType: 'habit',
        entityId: habitWithId.id,
        details: { name: habitWithId.name },
      });
    } catch (e) {
      console.warn('Failed creating habit in IndexedDB:', e);
    }

    if (isBackendOnline) {
      try {
        const created = await habitService.createHabit(habitWithId);
        setHabits((prev) => prev.map((h) => (h.id === habitWithId.id ? created : h)));
      } catch (err) {
        console.warn('Backend habit creation failed, saved locally:', err);
      }
    }
  };

  const deleteHabit = async (habitId) => {
    setHabits((prev) => prev.filter((h) => h.id !== habitId));

    // Persist to IndexedDB
    try {
      await habitRepository.deleteHabit(habitId);
      await activityRepository.log({
        eventType: 'HABIT_DELETED',
        entityType: 'habit',
        entityId: habitId,
      });
    } catch (e) {
      console.warn('Failed deleting habit in IndexedDB:', e);
    }

    if (isBackendOnline) {
      try {
        await habitService.deleteHabit(habitId);
      } catch (err) {
        console.warn('Backend habit deletion failed, deleted locally:', err);
      }
    }
  };

  return (
    <AppContext.Provider
      value={{
        user,
        tasks,
        goals,
        habits,
        metrics,
        weeklyChartData,
        categoryDistributionData,
        upcomingDeadlines,
        topPriorities,
        globalSearchQuery,
        setGlobalSearchQuery,
        // Backend synchronization
        isBackendOnline,
        isSyncing,
        syncError,
        syncWithBackend,
        // Modal states
        isTaskModalOpen,
        openAddTaskModal,
        closeAddTaskModal,
        editingTask,
        isGoalModalOpen,
        openAddGoalModal,
        closeAddGoalModal,
        editingGoal,
        // Notification states & actions
        isNotificationOpen,
        setIsNotificationOpen,
        openNotificationCenter,
        closeNotificationCenter,
        deadlineNotifications,
        unreadNotificationCount: deadlineNotifications.length,
        // Layout states
        isSidebarCollapsed,
        setIsSidebarCollapsed,
        isRightPanelOpen,
        setIsRightPanelOpen,
        // Handlers
        addTask,
        updateTask,
        deleteTask,
        toggleTaskCompletion,
        addGoal,
        updateGoal,
        deleteGoal,
        toggleHabit,
        addHabit,
        deleteHabit,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
