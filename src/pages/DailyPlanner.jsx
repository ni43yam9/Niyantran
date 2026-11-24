import { useState, useMemo, useEffect } from 'react';
import {
  Clock,
  Plus,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Trash2,
  Edit2,
  FastForward,
  CheckCircle2,
  Circle,
  PlayCircle,
  Target,
  ArrowRight,
  RotateCcw,
  AlertTriangle,
  Check,
  ListTodo,
  CalendarPlus,
} from 'lucide-react';
import { Card, CardHeader } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Input, Select } from '../components/common/FormControls';
import { useApp } from '../context/AppContext';
import { getTodayString } from '../utils/dateUtils';
import { timeblockService } from '../services/timeblockService';
import { dailyIntentRepository, timeblockRepository } from '../database';

// Time arithmetic helpers
function parseTimeToMinutes(timeStr) {
  if (!timeStr) return 9 * 60;
  const match = timeStr.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return 9 * 60;
  let hours = parseInt(match[1], 10);
  const mins = parseInt(match[2], 10);
  const meridiem = match[3].toUpperCase();
  if (meridiem === 'PM' && hours !== 12) hours += 12;
  if (meridiem === 'AM' && hours === 12) hours = 0;
  return hours * 60 + mins;
}

function formatMinutesToTime(totalMins) {
  let mins = totalMins % (24 * 60);
  if (mins < 0) mins += 24 * 60;
  const hours24 = Math.floor(mins / 60);
  const minutes = mins % 60;
  const meridiem = hours24 >= 12 ? 'PM' : 'AM';
  const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
  return `${String(hours12).padStart(2, '0')}:${String(minutes).padStart(2, '0')} ${meridiem}`;
}

function offsetDateString(baseDateStr, days) {
  const parts = baseDateStr.split('-').map(Number);
  const d = new Date(parts[0], parts[1] - 1, parts[2]);
  d.setDate(d.getDate() + days);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatFullDate(dateStr) {
  const parts = dateStr.split('-').map(Number);
  const d = new Date(parts[0], parts[1] - 1, parts[2]);
  const isToday = dateStr === getTodayString();
  const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'long' }).format(d);
  const monthDay = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(d);
  return {
    isToday,
    weekday,
    monthDay,
    display: `${isToday ? 'Today • ' : ''}${weekday}, ${monthDay}`,
  };
}

const CATEGORY_COLORS = {
  Coding: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-900/50',
  Academic: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-900/50',
  Health: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50',
  Reading: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50',
  Personal: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900/50',
  General: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
};

const DEFAULT_STARTER_BLOCKS = [
  { id: 'sb_1', time: '07:30 AM', title: 'Morning Mobility & Focus Activation', category: 'Health', durationMinutes: 45, actualDurationMinutes: 45, status: 'Completed' },
  { id: 'sb_2', time: '08:30 AM', title: 'DSA Practice: LeetCode Graph Traversal', category: 'Coding', durationMinutes: 90, actualDurationMinutes: 105, status: 'Completed' },
  { id: 'sb_3', time: '10:30 AM', title: 'Stanford CS229 SVM Dual Derivations', category: 'Academic', durationMinutes: 90, status: 'In Progress' },
  { id: 'sb_4', time: '12:30 PM', title: 'Lunch & Restorative Walk', category: 'Personal', durationMinutes: 60, status: 'Pending', isBreak: true },
  { id: 'sb_5', time: '02:00 PM', title: 'NIYANTRA Full-Stack Component Engineering', category: 'Coding', durationMinutes: 120, status: 'Pending' },
  { id: 'sb_6', time: '04:30 PM', title: 'Read DDIA: Chapter 5 Replication Mechanisms', category: 'Reading', durationMinutes: 60, status: 'Pending' },
  { id: 'sb_7', time: '05:45 PM', title: 'Daily Review, Task Rollover & Reflection', category: 'General', durationMinutes: 30, status: 'Pending' },
];

export function DailyPlanner() {
  const { tasks, toggleTaskCompletion, updateTask } = useApp();

  const [selectedDateStr, setSelectedDateStr] = useState(getTodayString);

  // Daily Primary Intent
  const [dailyIntents, setDailyIntents] = useState(() => {
    try {
      const saved = localStorage.getItem('niyantra_daily_intents');
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return {};
  });

  const [isEditingIntent, setIsEditingIntent] = useState(false);
  const [intentInput, setIntentInput] = useState('');

  // All timeblocks mapped by date
  const [dateBlocksMap, setDateBlocksMap] = useState(() => {
    try {
      const saved = localStorage.getItem('niyantra_daily_timeblocks');
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return {
      [getTodayString()]: DEFAULT_STARTER_BLOCKS,
    };
  });

  // Load timeblocks & intents from IndexedDB on mount or date change, then sync from backend
  useEffect(() => {
    let active = true;

    async function loadClientData() {
      try {
        // Load intents map from IndexedDB
        const intentMap = await dailyIntentRepository.getMap();
        if (active && Object.keys(intentMap).length > 0) {
          setDailyIntents((prev) => ({ ...prev, ...intentMap }));
        }

        // Load timeblocks from IndexedDB for selected date
        const localBlocks = await timeblockRepository.getByDate(selectedDateStr);
        if (active && Array.isArray(localBlocks) && localBlocks.length > 0) {
          setDateBlocksMap((prev) => ({
            ...prev,
            [selectedDateStr]: localBlocks,
          }));
        }
      } catch (err) {
        console.warn('IndexedDB planner load notice:', err);
      }

      // Then attempt backend fetch if online
      try {
        const blocks = await timeblockService.getTimeblocks(selectedDateStr);
        if (active && Array.isArray(blocks) && blocks.length > 0) {
          setDateBlocksMap((prev) => ({
            ...prev,
            [selectedDateStr]: blocks,
          }));
          // Cache backend blocks into IndexedDB
          await timeblockRepository.saveForDate(selectedDateStr, blocks);
        }
      } catch (err) {
        // Fallback gracefully to IndexedDB offline storage
        console.warn('Backend timeblocks fetch fallback:', err);
      }
    }

    loadClientData();
    return () => {
      active = false;
    };
  }, [selectedDateStr]);

  // Current day's blocks
  const currentBlocks = useMemo(() => {
    return dateBlocksMap[selectedDateStr] || [];
  }, [dateBlocksMap, selectedDateStr]);

  // Unfinished / pending blocks for selected day
  const pendingBlocks = useMemo(() => {
    return currentBlocks.filter((b) => b.status !== 'Completed' && !b.isBreak);
  }, [currentBlocks]);

  // Current intent
  const currentIntent = dailyIntents[selectedDateStr] || 'Focus on highest-priority deliverables today';

  // Planned vs Actual productivity metrics for completed blocks on the selected date
  const plannedVsActualDayStats = useMemo(() => {
    const completedWithActual = currentBlocks.filter(
      (b) => b.status === 'Completed' && typeof b.actualDurationMinutes === 'number'
    );
    if (completedWithActual.length === 0) return null;
    const totalPlanned = completedWithActual.reduce((acc, b) => acc + (b.durationMinutes || 60), 0);
    const totalActual = completedWithActual.reduce((acc, b) => acc + b.actualDurationMinutes, 0);
    const variance = totalActual - totalPlanned;
    return {
      totalPlanned,
      totalActual,
      variance,
      isUnderestimated: variance > 0,
      count: completedWithActual.length,
    };
  }, [currentBlocks]);

  // Save changes to localStorage and IndexedDB
  const updateBlocksForDate = (dateStr, newBlocks) => {
    setDateBlocksMap((prev) => {
      const updated = { ...prev, [dateStr]: newBlocks };
      localStorage.setItem('niyantra_daily_timeblocks', JSON.stringify(updated));
      return updated;
    });
    // Persist to IndexedDB
    timeblockRepository.saveForDate(dateStr, newBlocks).catch((err) => {
      console.warn('Failed saving blocks to IndexedDB:', err);
    });
  };

  const handleSaveIntent = () => {
    if (!intentInput.trim()) return;
    const trimmed = intentInput.trim();
    setDailyIntents((prev) => {
      const updated = { ...prev, [selectedDateStr]: trimmed };
      localStorage.setItem('niyantra_daily_intents', JSON.stringify(updated));
      return updated;
    });
    // Persist to IndexedDB
    dailyIntentRepository.save(selectedDateStr, trimmed).catch((err) => {
      console.warn('Failed saving daily intent to IndexedDB:', err);
    });
    setIsEditingIntent(false);
  };

  // Workload Capacity Budget (6.0 hours default limit)
  const DAILY_CAPACITY_LIMIT_MINS = 360;
  const totalPlannedMinutes = useMemo(() => {
    return currentBlocks.reduce((acc, b) => acc + (b.isBreak ? 0 : (b.durationMinutes || 60)), 0);
  }, [currentBlocks]);

  const plannedHours = (totalPlannedMinutes / 60).toFixed(1);
  const capacityPercent = Math.min(Math.round((totalPlannedMinutes / DAILY_CAPACITY_LIMIT_MINS) * 100), 150);
  const isOverbooked = totalPlannedMinutes > DAILY_CAPACITY_LIMIT_MINS;

  // Modal states for manual changes
  const [isBlockModalOpen, setIsBlockModalOpen] = useState(false);
  const [editingBlock, setEditingBlock] = useState(null);
  const [blockForm, setBlockForm] = useState({
    title: '',
    time: '09:00 AM',
    durationMinutes: 60,
    actualDurationMinutes: '',
    category: 'Coding',
    status: 'Pending',
    taskId: '',
  });

  const openAddBlockModal = (initialTask = null) => {
    let nextStartTime = '09:00 AM';
    if (currentBlocks.length > 0) {
      const lastBlock = currentBlocks[currentBlocks.length - 1];
      const endMins = parseTimeToMinutes(lastBlock.time) + (lastBlock.durationMinutes || 60);
      nextStartTime = formatMinutesToTime(endMins);
    }

    if (initialTask) {
      setBlockForm({
        title: initialTask.title,
        time: nextStartTime,
        durationMinutes: initialTask.priority === 'High' ? 90 : 60,
        actualDurationMinutes: '',
        category: initialTask.category || 'Coding',
        status: 'Pending',
        taskId: initialTask.id || '',
      });
    } else {
      setBlockForm({
        title: '',
        time: nextStartTime,
        durationMinutes: 60,
        actualDurationMinutes: '',
        category: 'Coding',
        status: 'Pending',
        taskId: '',
      });
    }
    setEditingBlock(null);
    setIsBlockModalOpen(true);
  };

  const openEditBlockModal = (block) => {
    setEditingBlock(block);
    setBlockForm({
      title: block.title,
      time: block.time,
      durationMinutes: block.durationMinutes || 60,
      actualDurationMinutes: block.actualDurationMinutes ?? '',
      category: block.category || 'General',
      status: block.status || 'Pending',
      taskId: block.taskId || '',
    });
    setIsBlockModalOpen(true);
  };

  const handleSaveBlock = async (e) => {
    e.preventDefault();
    if (!blockForm.title.trim()) return;

    const actualMins =
      blockForm.actualDurationMinutes !== '' && !isNaN(Number(blockForm.actualDurationMinutes))
        ? Math.max(0, Number(blockForm.actualDurationMinutes))
        : null;

    const blockPayload = {
      date: selectedDateStr,
      title: blockForm.title.trim(),
      time: blockForm.time,
      durationMinutes: Number(blockForm.durationMinutes) || 60,
      actualDurationMinutes: actualMins,
      category: blockForm.category,
      status: blockForm.status,
      taskId: blockForm.taskId || null,
      isBreak: blockForm.isBreak || false,
    };

    if (editingBlock) {
      const updated = currentBlocks.map((b) =>
        b.id === editingBlock.id
          ? {
              ...b,
              ...blockPayload,
              id: editingBlock.id,
            }
          : b
      );
      updateBlocksForDate(selectedDateStr, updated);
      setIsBlockModalOpen(false);

      try {
        await timeblockService.updateTimeblock(editingBlock.id, blockPayload);
      } catch (err) {
        console.warn('Backend timeblock update failed, stored locally:', err);
      }
    } else {
      const newId = `blk_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
      const newBlock = {
        id: newId,
        ...blockPayload,
      };
      updateBlocksForDate(selectedDateStr, [...currentBlocks, newBlock]);
      setIsBlockModalOpen(false);

      try {
        const created = await timeblockService.createTimeblock(newBlock);
        if (created && created.id) {
          setDateBlocksMap((prev) => ({
            ...prev,
            [selectedDateStr]: (prev[selectedDateStr] || []).map((b) => (b.id === newId ? created : b)),
          }));
        }
      } catch (err) {
        console.warn('Backend timeblock creation failed, stored locally:', err);
      }
    }
  };

  const handleDeleteBlock = async (blockId) => {
    const updated = currentBlocks.filter((b) => b.id !== blockId);
    updateBlocksForDate(selectedDateStr, updated);
    try {
      await timeblockService.deleteTimeblock(blockId);
    } catch (err) {
      console.warn('Backend timeblock deletion failed, deleted locally:', err);
    }
  };

  // Cycle status: Pending -> In Progress -> Completed -> Pending
  const handleToggleBlockStatus = async (block) => {
    const nextStatus =
      block.status === 'Pending'
        ? 'In Progress'
        : block.status === 'In Progress'
        ? 'Completed'
        : 'Pending';

    let updatedActual = block.actualDurationMinutes;
    if (nextStatus === 'Completed' && (updatedActual === null || updatedActual === undefined)) {
      updatedActual = block.durationMinutes || 60;
    }

    const updated = currentBlocks.map((b) =>
      b.id === block.id ? { ...b, status: nextStatus, actualDurationMinutes: updatedActual } : b
    );
    updateBlocksForDate(selectedDateStr, updated);

    if (block.taskId && nextStatus === 'Completed') {
      const centralTask = tasks.find((t) => t.id === block.taskId);
      if (centralTask && centralTask.status !== 'Completed') {
        toggleTaskCompletion(block.taskId);
      }
    }

    try {
      await timeblockService.updateTimeblock(block.id, {
        date: block.date || selectedDateStr,
        status: nextStatus,
        actualDurationMinutes: updatedActual,
      });
    } catch (err) {
      console.warn('Backend timeblock status update failed:', err);
    }
  };

  // Shift schedule forward by +30m
  const handleShiftScheduleForward = () => {
    const updated = currentBlocks.map((b) => {
      if (b.status === 'Completed') return b;
      const currentMins = parseTimeToMinutes(b.time);
      return {
        ...b,
        time: formatMinutesToTime(currentMins + 30),
      };
    });
    updateBlocksForDate(selectedDateStr, updated);
  };

  // 1-Click Rollover all pending tasks to Tomorrow
  const handleRolloverPendingToTomorrow = () => {
    if (pendingBlocks.length === 0) return;

    const tomorrowStr = offsetDateString(selectedDateStr, 1);
    const tomorrowBlocks = dateBlocksMap[tomorrowStr] || [];

    let nextMins = 9 * 60;
    if (tomorrowBlocks.length > 0) {
      const lastBlock = tomorrowBlocks[tomorrowBlocks.length - 1];
      nextMins = parseTimeToMinutes(lastBlock.time) + (lastBlock.durationMinutes || 60);
    }

    const rolledOver = pendingBlocks.map((b, idx) => {
      const startMins = nextMins + idx * (b.durationMinutes || 60);
      return {
        ...b,
        id: `ro_${Date.now()}_${idx}`,
        time: formatMinutesToTime(startMins),
        status: 'Pending',
      };
    });

    pendingBlocks.forEach((b) => {
      if (b.taskId) {
        const task = tasks.find((t) => t.id === b.taskId);
        if (task && updateTask) {
          updateTask({
            ...task,
            dueDate: tomorrowStr,
            postponeCount: (task.postponeCount || 0) + 1,
          });
        }
      }
    });

    const keptToday = currentBlocks.filter((b) => b.status === 'Completed' || b.isBreak);
    const updatedTomorrowBlocks = [...tomorrowBlocks, ...rolledOver];
    setDateBlocksMap((prev) => {
      const updated = {
        ...prev,
        [selectedDateStr]: keptToday,
        [tomorrowStr]: updatedTomorrowBlocks,
      };
      localStorage.setItem('niyantra_daily_timeblocks', JSON.stringify(updated));
      return updated;
    });
    timeblockRepository.saveForDate(selectedDateStr, keptToday).catch((e) => console.warn(e));
    timeblockRepository.saveForDate(tomorrowStr, updatedTomorrowBlocks).catch((e) => console.warn(e));
  };

  // Postpone single block to tomorrow
  const handlePostponeBlockToTomorrow = (block) => {
    const tomorrowStr = offsetDateString(selectedDateStr, 1);
    const tomorrowBlocks = dateBlocksMap[tomorrowStr] || [];

    let nextMins = 9 * 60;
    if (tomorrowBlocks.length > 0) {
      const lastBlock = tomorrowBlocks[tomorrowBlocks.length - 1];
      nextMins = parseTimeToMinutes(lastBlock.time) + (lastBlock.durationMinutes || 60);
    }

    const newTomorrowBlock = {
      ...block,
      id: `ro_${Date.now()}`,
      time: formatMinutesToTime(nextMins),
      status: 'Pending',
    };

    if (block.taskId) {
      const task = tasks.find((t) => t.id === block.taskId);
      if (task && updateTask) {
        updateTask({
          ...task,
          dueDate: tomorrowStr,
          postponeCount: (task.postponeCount || 0) + 1,
        });
      }
    }

    const updatedTodayBlocks = (dateBlocksMap[selectedDateStr] || []).filter((b) => b.id !== block.id);
    const updatedTomorrowBlocks = [...tomorrowBlocks, newTomorrowBlock];

    setDateBlocksMap((prev) => {
      const updated = {
        ...prev,
        [selectedDateStr]: updatedTodayBlocks,
        [tomorrowStr]: updatedTomorrowBlocks,
      };
      localStorage.setItem('niyantra_daily_timeblocks', JSON.stringify(updated));
      return updated;
    });
    timeblockRepository.saveForDate(selectedDateStr, updatedTodayBlocks).catch((e) => console.warn(e));
    timeblockRepository.saveForDate(tomorrowStr, updatedTomorrowBlocks).catch((e) => console.warn(e));
  };

  // Clear blocks for selected day
  const handleClearDay = () => {
    if (window.confirm('Clear scheduled timeblocks for this day?')) {
      updateBlocksForDate(selectedDateStr, []);
    }
  };

  // 1-Click Auto-Schedule Day
  const handleAutoSchedule = () => {
    const activeTasks = tasks.filter((t) => t.status !== 'Completed');
    const priorityWeight = { High: 3, Medium: 2, Low: 1 };
    const sortedTasks = [...activeTasks].sort((a, b) => {
      const pDiff = (priorityWeight[b.priority] || 1) - (priorityWeight[a.priority] || 1);
      if (pDiff !== 0) return pDiff;
      const aIsToday = a.dueDate === selectedDateStr || a.category === 'Daily';
      const bIsToday = b.dueDate === selectedDateStr || b.category === 'Daily';
      if (aIsToday && !bIsToday) return -1;
      if (!aIsToday && bIsToday) return 1;
      return 0;
    });

    const newBlocks = [];
    let currentMins = 9 * 60;
    let totalFocusMins = 0;
    let lunchScheduled = false;

    if (sortedTasks.length > 0) {
      const t1 = sortedTasks[0];
      const duration = t1.priority === 'High' ? 90 : 60;
      newBlocks.push({
        id: `auto_${Date.now()}_1`,
        taskId: t1.id,
        title: t1.title,
        time: formatMinutesToTime(currentMins),
        durationMinutes: duration,
        category: t1.category || 'Coding',
        status: 'Pending',
      });
      currentMins += duration;
      totalFocusMins += duration;
    }

    if (sortedTasks.length > 1) {
      const t2 = sortedTasks[1];
      const duration = t2.priority === 'High' ? 90 : 60;
      newBlocks.push({
        id: `auto_${Date.now()}_2`,
        taskId: t2.id,
        title: t2.title,
        time: formatMinutesToTime(currentMins),
        durationMinutes: duration,
        category: t2.category || 'Academic',
        status: 'Pending',
      });
      currentMins += duration;
      totalFocusMins += duration;
    }

    if (currentMins >= 12 * 60 + 30 && !lunchScheduled) {
      newBlocks.push({
        id: `auto_${Date.now()}_lunch`,
        title: 'Lunch & Restorative Break',
        time: formatMinutesToTime(currentMins),
        durationMinutes: 45,
        category: 'Personal',
        status: 'Pending',
        isBreak: true,
      });
      currentMins += 45;
      lunchScheduled = true;
    }

    if (sortedTasks.length > 2 && totalFocusMins < DAILY_CAPACITY_LIMIT_MINS) {
      const t3 = sortedTasks[2];
      const duration = 60;
      newBlocks.push({
        id: `auto_${Date.now()}_3`,
        taskId: t3.id,
        title: t3.title,
        time: formatMinutesToTime(currentMins),
        durationMinutes: duration,
        category: t3.category || 'Coding',
        status: 'Pending',
      });
      currentMins += duration;
      totalFocusMins += duration;
    }

    if (!lunchScheduled) {
      newBlocks.push({
        id: `auto_${Date.now()}_lunch`,
        title: 'Lunch & Restorative Break',
        time: formatMinutesToTime(currentMins),
        durationMinutes: 45,
        category: 'Personal',
        status: 'Pending',
        isBreak: true,
      });
      currentMins += 45;
      lunchScheduled = true;
    }

    if (sortedTasks.length > 3 && totalFocusMins < DAILY_CAPACITY_LIMIT_MINS) {
      const t4 = sortedTasks[3];
      const duration = 45;
      newBlocks.push({
        id: `auto_${Date.now()}_4`,
        taskId: t4.id,
        title: t4.title,
        time: formatMinutesToTime(currentMins),
        durationMinutes: duration,
        category: t4.category || 'Reading',
        status: 'Pending',
      });
      currentMins += duration;
      totalFocusMins += duration;
    }

    newBlocks.push({
      id: `auto_${Date.now()}_shutdown`,
      title: 'Daily Review, Task Rollover & Shutdown',
      time: formatMinutesToTime(currentMins),
      durationMinutes: 30,
      category: 'General',
      status: 'Pending',
    });

    updateBlocksForDate(selectedDateStr, newBlocks);
  };

  const scheduledTaskIds = useMemo(() => {
    return new Set(currentBlocks.map((b) => b.taskId).filter(Boolean));
  }, [currentBlocks]);

  const unscheduledActiveTasks = useMemo(() => {
    return tasks.filter((t) => t.status !== 'Completed' && !scheduledTaskIds.has(t.id));
  }, [tasks, scheduledTaskIds]);

  const dateDetails = formatFullDate(selectedDateStr);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Top Bar: Date Navigation & Quick Actions */}
      <div className="glass-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
          {dateDetails.display}
        </h2>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center rounded-lg border border-white/60 dark:border-white/10 bg-white/40 dark:bg-white/5 p-0.5">
            <button
              onClick={() => setSelectedDateStr((curr) => offsetDateString(curr, -1))}
              className="p-1.5 rounded-md hover:bg-white/50 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setSelectedDateStr(getTodayString())}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                dateDetails.isToday
                  ? 'bg-primary-600 dark:bg-primary-500 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:bg-white/50 dark:hover:bg-white/10'
              }`}
            >
              Today
            </button>
            <button
              onClick={() => setSelectedDateStr((curr) => offsetDateString(curr, 1))}
              className="p-1.5 rounded-md hover:bg-white/50 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <Button
            variant="primary"
            size="sm"
            icon={Sparkles}
            onClick={handleAutoSchedule}
            className="shadow-xs text-xs"
          >
            Auto-Schedule
          </Button>

          <Button
            variant="outline"
            size="sm"
            icon={FastForward}
            onClick={handleShiftScheduleForward}
            className="text-xs"
          >
            +30m Shift
          </Button>

          <Button
            variant="outline"
            size="sm"
            icon={Plus}
            onClick={() => openAddBlockModal()}
            className="text-xs"
          >
            Add Block
          </Button>
        </div>
      </div>

      {/* Workload Capacity Bar */}
      <div className="glass-card p-3.5">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-primary-600 dark:text-primary-400" />
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Workload Capacity:
            </span>
            <span className="text-xs font-bold text-slate-900 dark:text-white">
              {plannedHours} / 6.0 hrs
            </span>
          </div>

          {isOverbooked && (
            <div className="flex items-center gap-1.5 text-xs font-bold text-rose-600 dark:text-rose-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Overbooked by {((totalPlannedMinutes - DAILY_CAPACITY_LIMIT_MINS) / 60).toFixed(1)} hrs</span>
            </div>
          )}
        </div>

        <div className="w-full bg-slate-200/50 dark:bg-white/10 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 rounded-full ${
              isOverbooked
                ? 'bg-rose-500'
                : capacityPercent > 80
                ? 'bg-amber-500'
                : 'bg-primary-600 dark:bg-primary-500'
            }`}
            style={{ width: `${Math.min(capacityPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Primary Focus Banner */}
      <div className="p-3 rounded-xl bg-white/40 dark:bg-white/5 border border-white/60 dark:border-white/10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <Target className="w-4 h-4 text-primary-600 dark:text-primary-400 shrink-0" />
          {isEditingIntent ? (
            <div className="flex-1 flex items-center gap-2">
              <input
                type="text"
                value={intentInput}
                onChange={(e) => setIntentInput(e.target.value)}
                placeholder="What is your primary focus today?"
                className="w-full text-xs px-2.5 py-1 rounded-lg border border-white/60 dark:border-white/10 bg-white/60 dark:bg-white/5 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
              <Button size="xs" variant="primary" onClick={handleSaveIntent}>
                Save
              </Button>
              <Button size="xs" variant="ghost" onClick={() => setIsEditingIntent(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <p className="text-xs text-slate-800 dark:text-slate-200 font-medium truncate">
              {currentIntent}
            </p>
          )}
        </div>

        {!isEditingIntent && (
          <button
            onClick={() => {
              setIntentInput(currentIntent);
              setIsEditingIntent(true);
            }}
            className="text-xs text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1 shrink-0 font-medium ml-2"
          >
            <Edit2 className="w-3 h-3" />
            Edit
          </button>
        )}
      </div>

      {/* Planned vs Actual Productivity Banner */}
      {plannedVsActualDayStats && (
        <div className="glass-card p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-2.5">
            <span className="text-base">⏱️</span>
            <div>
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200">
                Planned vs Actual Productivity ({plannedVsActualDayStats.count} completed)
              </h4>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Planned: <span className="font-semibold text-slate-700 dark:text-slate-300">{plannedVsActualDayStats.totalPlanned} mins</span> • Actual: <span className="font-semibold text-slate-700 dark:text-slate-300">{plannedVsActualDayStats.totalActual} mins</span>
              </p>
            </div>
          </div>

          <div>
            {plannedVsActualDayStats.variance > 0 ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200/80 dark:border-amber-800/80">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                Underestimated by +{plannedVsActualDayStats.variance}m ({Math.round((plannedVsActualDayStats.variance / plannedVsActualDayStats.totalPlanned) * 100)}% over)
              </span>
            ) : plannedVsActualDayStats.variance < 0 ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200/80 dark:border-emerald-800/80">
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                Completed faster ({Math.abs(plannedVsActualDayStats.variance)}m ahead of schedule)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-primary-50 dark:bg-primary-950/60 text-primary-700 dark:text-primary-400 border border-primary-200/80 dark:border-primary-800/80">
                Exact match with planned estimation
              </span>
            )}
          </div>
        </div>
      )}

      {/* Main Grid: Hourly Timeline (Left) + Unscheduled Tasks Tray (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Scheduled Hourly Timeline (2 Columns wide) */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader
              title="Daily Schedule Timeline"
              icon={Clock}
              action={
                <div className="flex flex-wrap items-center gap-2">
                  {pendingBlocks.length > 0 && (
                    <Button
                      variant="outline"
                      size="xs"
                      icon={CalendarPlus}
                      onClick={handleRolloverPendingToTomorrow}
                      className="text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-800 hover:bg-amber-50 dark:hover:bg-amber-950/30 text-xs"
                    >
                      Rollover ({pendingBlocks.length})
                    </Button>
                  )}
                  {currentBlocks.length > 0 && (
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={handleClearDay}
                      className="text-slate-400 hover:text-rose-500 text-xs"
                      icon={RotateCcw}
                    >
                      Clear
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    icon={Plus}
                    onClick={() => openAddBlockModal()}
                    className="text-xs"
                  >
                    + Add Block
                  </Button>
                </div>
              }
            />

            {currentBlocks.length === 0 ? (
              <div className="text-center py-10 px-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
                <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  No timeblocks scheduled
                </h4>
                <div className="mt-3 flex justify-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Sparkles}
                    onClick={handleAutoSchedule}
                    className="text-xs"
                  >
                    Auto-Schedule
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 relative before:absolute before:inset-0 before:left-5 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800 pl-2">
                {currentBlocks.map((block) => (
                  <div key={block.id} className="flex items-start gap-4 relative group">
                    <button
                      onClick={() => handleToggleBlockStatus(block)}
                      className={`w-4 h-4 rounded-full border-2 border-white dark:border-[#131B2E] z-10 shrink-0 mt-3.5 transition-transform hover:scale-125 focus:outline-none ${
                        block.status === 'Completed'
                          ? 'bg-emerald-500 ring-2 ring-emerald-100 dark:ring-emerald-950'
                          : block.status === 'In Progress'
                          ? 'bg-indigo-600 ring-2 ring-indigo-100 dark:ring-indigo-950 animate-pulse'
                          : 'bg-slate-300 dark:bg-slate-700 hover:bg-slate-400'
                      }`}
                    />

                    <div
                      className={`flex-1 p-3.5 rounded-xl border transition-all ${
                        block.status === 'Completed'
                          ? 'bg-slate-50/70 dark:bg-slate-900/40 border-slate-200/60 dark:border-slate-800/80 opacity-80'
                          : block.status === 'In Progress'
                          ? 'bg-indigo-50/40 dark:bg-indigo-950/20 border-indigo-200 dark:border-indigo-800/60 shadow-xs'
                          : 'bg-white dark:bg-slate-900/60 border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-slate-600 dark:text-slate-300">
                            {block.time}
                          </span>
                          <span className="text-slate-300 dark:text-slate-700">•</span>
                          <span className="text-xs text-slate-400">
                            Planned: {block.durationMinutes || 60}m
                          </span>
                          {typeof block.actualDurationMinutes === 'number' && (
                            <>
                              <span className="text-slate-300 dark:text-slate-700">•</span>
                              <span
                                className={`text-xs font-semibold ${
                                  block.actualDurationMinutes > (block.durationMinutes || 60)
                                    ? 'text-amber-600 dark:text-amber-400'
                                    : 'text-emerald-600 dark:text-emerald-400'
                                }`}
                              >
                                Actual: {block.actualDurationMinutes}m
                              </span>
                              {block.actualDurationMinutes > (block.durationMinutes || 60) && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                  +{block.actualDurationMinutes - (block.durationMinutes || 60)}m (Underestimated)
                                </span>
                              )}
                            </>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] font-medium px-2 py-0.5 rounded border ${
                              CATEGORY_COLORS[block.category] || CATEGORY_COLORS.General
                            }`}
                          >
                            {block.category}
                          </span>

                          <button
                            onClick={() => handleToggleBlockStatus(block)}
                            className={`text-[10px] font-semibold px-2 py-0.5 rounded flex items-center gap-1 transition-colors ${
                              block.status === 'Completed'
                                ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400'
                                : block.status === 'In Progress'
                                ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                            }`}
                          >
                            {block.status === 'Completed' ? (
                              <CheckCircle2 className="w-3 h-3" />
                            ) : block.status === 'In Progress' ? (
                              <PlayCircle className="w-3 h-3" />
                            ) : (
                              <Circle className="w-3 h-3" />
                            )}
                            {block.status}
                          </button>

                          <div className="flex items-center gap-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {block.status !== 'Completed' && !block.isBreak && (
                              <button
                                onClick={() => handlePostponeBlockToTomorrow(block)}
                                className="p-1 rounded text-slate-400 hover:text-amber-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                              >
                                <CalendarPlus className="w-3 h-3" />
                              </button>
                            )}
                            <button
                              onClick={() => openEditBlockModal(block)}
                              className="p-1 rounded text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={() => handleDeleteBlock(block.id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      </div>

                      <h4
                        className={`font-bold text-sm mt-1 transition-all ${
                          block.status === 'Completed'
                            ? 'line-through text-slate-400 dark:text-slate-500'
                            : 'text-slate-900 dark:text-white'
                        }`}
                      >
                        {block.title}
                      </h4>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Unscheduled Tasks Tray (1 Column wide) */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Active Tasks"
              icon={ListTodo}
            />

            {unscheduledActiveTasks.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-400">
                <Check className="w-5 h-5 text-emerald-500 mx-auto mb-1.5" />
                No unscheduled tasks
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                {unscheduledActiveTasks.map((task) => (
                  <div
                    key={task.id}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 hover:bg-white dark:hover:bg-slate-800/80 transition-colors flex items-center justify-between gap-2 group"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase ${
                            task.priority === 'High'
                              ? 'bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400'
                              : task.priority === 'Medium'
                              ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400'
                              : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400'
                          }`}
                        >
                          {task.priority}
                        </span>
                        <span className="text-[10px] text-slate-400 truncate">
                          {task.category || 'General'}
                        </span>
                      </div>
                      <h5 className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                        {task.title}
                      </h5>
                    </div>

                    <Button
                      size="xs"
                      variant="outline"
                      icon={ArrowRight}
                      onClick={() => openAddBlockModal(task)}
                      className="shrink-0 text-xs px-2 py-1"
                    >
                      + Slot
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Add / Edit Timeblock Modal */}
      <Modal
        isOpen={isBlockModalOpen}
        onClose={() => setIsBlockModalOpen(false)}
        title={editingBlock ? 'Edit Timeblock' : 'Add Timeblock'}
      >
        <form onSubmit={handleSaveBlock} className="space-y-4">
          <Input
            label="Block Title"
            id="blockTitle"
            placeholder="Focus block title"
            value={blockForm.title}
            onChange={(e) => setBlockForm({ ...blockForm, title: e.target.value })}
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Start Time"
              id="blockTime"
              placeholder="09:00 AM"
              value={blockForm.time}
              onChange={(e) => setBlockForm({ ...blockForm, time: e.target.value })}
              required
            />

            <Select
              label="Planned Duration"
              id="blockDuration"
              value={blockForm.durationMinutes}
              onChange={(e) => setBlockForm({ ...blockForm, durationMinutes: Number(e.target.value) })}
              options={[
                { value: 15, label: '15 mins' },
                { value: 30, label: '30 mins' },
                { value: 45, label: '45 mins' },
                { value: 60, label: '60 mins (1 hr)' },
                { value: 90, label: '90 mins (1.5 hrs)' },
                { value: 120, label: '120 mins (2 hrs)' },
                { value: 180, label: '180 mins (3 hrs)' },
              ]}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Category"
              id="blockCategory"
              value={blockForm.category}
              onChange={(e) => setBlockForm({ ...blockForm, category: e.target.value })}
              options={[
                { value: 'Coding', label: 'Coding' },
                { value: 'Academic', label: 'Academic' },
                { value: 'Health', label: 'Health' },
                { value: 'Reading', label: 'Reading' },
                { value: 'Personal', label: 'Personal' },
                { value: 'General', label: 'General' },
              ]}
            />

            <Input
              label="Actual Duration (mins, optional)"
              id="blockActualDuration"
              type="number"
              min="0"
              max="720"
              placeholder="e.g. 90"
              value={blockForm.actualDurationMinutes}
              onChange={(e) => setBlockForm({ ...blockForm, actualDurationMinutes: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Status"
              id="blockStatus"
              value={blockForm.status}
              onChange={(e) => setBlockForm({ ...blockForm, status: e.target.value })}
              options={[
                { value: 'Pending', label: 'Pending' },
                { value: 'In Progress', label: 'In Progress' },
                { value: 'Completed', label: 'Completed' },
              ]}
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsBlockModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingBlock ? 'Save Changes' : 'Add Timeblock'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
