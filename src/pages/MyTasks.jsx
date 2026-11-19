import { useState, useEffect, useMemo } from 'react';
import {
  Plus,
  Trash2,
  ListFilter,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { TaskCard } from '../components/tasks/TaskCard';
import { TaskFilters } from '../components/tasks/TaskFilters';
import { Modal } from '../components/common/Modal';
import { Button } from '../components/common/Button';
import { getTodayString, isDateOverdue } from '../utils/dateUtils';

export function MyTasks() {
  const {
    tasks,
    toggleTaskCompletion,
    deleteTask,
    openAddTaskModal,
    globalSearchQuery,
    setGlobalSearchQuery,
  } = useApp();

  const [activeTab, setActiveTab] = useState('All Tasks');
  const [searchQuery, setSearchQuery] = useState(globalSearchQuery || '');
  const [selectedCategory, setSelectedCategory] = useState('All Categories');
  const [selectedPriority, setSelectedPriority] = useState('All Priorities');
  const [sortBy, setSortBy] = useState('dueDateAsc');
  const [deletingTaskId, setDeletingTaskId] = useState(null);

  const todayStr = getTodayString();

  // Keep local search and global search in sync if global search changes
  useEffect(() => {
    if (globalSearchQuery !== undefined) {
      setSearchQuery(globalSearchQuery);
    }
  }, [globalSearchQuery]);

  const handleSearchChange = (val) => {
    setSearchQuery(val);
    setGlobalSearchQuery(val);
  };

  // Compute tab counts dynamically
  const tabCounts = useMemo(() => {
    return {
      'All Tasks': tasks.length,
      Today: tasks.filter((t) => t.isToday || t.dueDate === todayStr).length,
      Upcoming: tasks.filter((t) => t.status !== 'Completed' && t.dueDate > todayStr).length,
      Daily: tasks.filter((t) => t.taskType === 'Daily').length,
      'Short-Term': tasks.filter((t) => t.taskType === 'Short-Term').length,
      'Long-Term': tasks.filter((t) => t.taskType === 'Long-Term').length,
      Occasional: tasks.filter((t) => t.taskType === 'Occasional').length,
      Completed: tasks.filter((t) => t.status === 'Completed').length,
      Overdue: tasks.filter((t) => isDateOverdue(t.dueDate, t.status === 'Completed')).length,
    };
  }, [tasks, todayStr]);

  // Filter tasks based on activeTab, search, category, priority
  const filteredTasks = useMemo(() => {
    return tasks
      .filter((task) => {
        // Tab filtering
        if (activeTab === 'Today') {
          if (!task.isToday && task.dueDate !== todayStr) return false;
        } else if (activeTab === 'Upcoming') {
          if (task.status === 'Completed' || task.dueDate <= todayStr) return false;
        } else if (activeTab === 'Daily') {
          if (task.taskType !== 'Daily') return false;
        } else if (activeTab === 'Short-Term') {
          if (task.taskType !== 'Short-Term') return false;
        } else if (activeTab === 'Long-Term') {
          if (task.taskType !== 'Long-Term') return false;
        } else if (activeTab === 'Occasional') {
          if (task.taskType !== 'Occasional') return false;
        } else if (activeTab === 'Completed') {
          if (task.status !== 'Completed') return false;
        } else if (activeTab === 'Overdue') {
          if (!isDateOverdue(task.dueDate, task.status === 'Completed')) return false;
        }

        // Search filtering
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchTitle = task.title.toLowerCase().includes(q);
          const matchDesc = (task.description || '').toLowerCase().includes(q);
          const matchGoal = (task.associatedGoalTitle || '').toLowerCase().includes(q);
          if (!matchTitle && !matchDesc && !matchGoal) return false;
        }

        // Category filtering
        if (selectedCategory !== 'All Categories' && task.category !== selectedCategory) {
          return false;
        }

        // Priority filtering
        if (selectedPriority !== 'All Priorities' && task.priority !== selectedPriority) {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        // Sorting logic
        if (sortBy === 'dueDateAsc') {
          return (a.dueDate || '').localeCompare(b.dueDate || '');
        }
        if (sortBy === 'dueDateDesc') {
          return (b.dueDate || '').localeCompare(a.dueDate || '');
        }
        if (sortBy === 'priorityHigh') {
          const score = { High: 3, Medium: 2, Low: 1 };
          return (score[b.priority] || 0) - (score[a.priority] || 0);
        }
        if (sortBy === 'priorityLow') {
          const score = { High: 3, Medium: 2, Low: 1 };
          return (score[a.priority] || 0) - (score[b.priority] || 0);
        }
        if (sortBy === 'titleAsc') {
          return a.title.localeCompare(b.title);
        }
        if (sortBy === 'titleDesc') {
          return b.title.localeCompare(a.title);
        }
        return 0;
      });
  }, [tasks, activeTab, searchQuery, selectedCategory, selectedPriority, sortBy, todayStr]);

  const hasActiveFilters =
    searchQuery.trim() !== '' ||
    selectedCategory !== 'All Categories' ||
    selectedPriority !== 'All Priorities' ||
    activeTab !== 'All Tasks';

  const handleClearFilters = () => {
    setActiveTab('All Tasks');
    setSearchQuery('');
    setSelectedCategory('All Categories');
    setSelectedPriority('All Priorities');
    setSortBy('dueDateAsc');
  };

  const handleConfirmDelete = () => {
    if (deletingTaskId) {
      deleteTask(deletingTaskId);
      setDeletingTaskId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Filters, Tabs & Search */}
      <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 sm:p-5 shadow-card">
        <TaskFilters
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          searchQuery={searchQuery}
          onSearchChange={handleSearchChange}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          selectedPriority={selectedPriority}
          onPriorityChange={setSelectedPriority}
          sortBy={sortBy}
          onSortChange={setSortBy}
          onClearFilters={handleClearFilters}
          hasActiveFilters={hasActiveFilters}
          tabCounts={tabCounts}
          onAddNew={() => openAddTaskModal()}
        />
      </div>

      {/* Task List */}
      <div className="space-y-3">
        {filteredTasks.length === 0 ? (
          <div className="text-center py-16 bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-2xs">
            <ListFilter className="w-10 h-10 mx-auto text-slate-400 dark:text-slate-600 mb-3" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
              No tasks found
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto mt-1 mb-5">
              No tasks match your current filter criteria or tab selection. Try resetting filters or create a new task.
            </p>
            <div className="flex items-center justify-center gap-3">
              {hasActiveFilters && (
                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                  Reset All Filters
                </Button>
              )}
              <Button
                variant="primary"
                size="sm"
                icon={Plus}
                onClick={() => openAddTaskModal()}
              >
                Create Task
              </Button>
            </div>
          </div>
        ) : (
          filteredTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onToggleComplete={toggleTaskCompletion}
              onEdit={openAddTaskModal}
              onDelete={(id) => setDeletingTaskId(id)}
            />
          ))
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingTaskId)}
        onClose={() => setDeletingTaskId(null)}
        title="Delete Task"
        subtitle="This action will remove the task from your board"
        size="sm"
        footer={
          <>
            <Button
              variant="outline"
              size="md"
              onClick={() => setDeletingTaskId(null)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="md"
              icon={Trash2}
              onClick={handleConfirmDelete}
            >
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Are you sure you want to delete this task? Associated goal metrics may adjust accordingly.
        </p>
      </Modal>
    </div>
  );
}
