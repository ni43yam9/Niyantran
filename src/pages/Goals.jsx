import { useState, useMemo } from 'react';
import {
  Target,
  Plus,
  Zap,
  Compass,
  TrendingUp,
  Trash2,
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { GoalCard } from '../components/goals/GoalCard';
import { Modal } from '../components/common/Modal';
import { Button } from '../components/common/Button';

export function Goals() {
  const { goals, deleteGoal, openAddGoalModal } = useApp();

  const [activeTab, setActiveTab] = useState('All');
  const [deletingGoalId, setDeletingGoalId] = useState(null);

  // Metrics
  const shortTermGoals = goals.filter((g) => g.type === 'Short-Term');
  const longTermGoals = goals.filter((g) => g.type === 'Long-Term');
  const avgProgress =
    goals.length > 0
      ? Math.round(goals.reduce((acc, g) => acc + (g.progress || 0), 0) / goals.length)
      : 0;

  // Filtered goals based on horizon card selection
  const filteredGoals = useMemo(() => {
    return goals.filter((goal) => {
      if (activeTab === 'Short-Term' && goal.type !== 'Short-Term') return false;
      if (activeTab === 'Long-Term' && goal.type !== 'Long-Term') return false;
      return true;
    });
  }, [goals, activeTab]);

  const handleConfirmDelete = () => {
    if (deletingGoalId) {
      deleteGoal(deletingGoalId);
      setDeletingGoalId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Strategic Summary Cards with Add Goal button adjacent */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {/* Total Goals (All) */}
        <div
          onClick={() => setActiveTab('All')}
          className={`glass-card p-4.5 cursor-pointer transition-all hover:scale-[1.01] ${
            activeTab === 'All'
              ? 'border-primary-500 ring-2 ring-primary-500/20 dark:ring-primary-400/30'
              : 'hover:border-primary-300 dark:hover:border-primary-700'
          }`}
          title="Click to view All Goals"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Goals
            </span>
            <div className="p-2 rounded-xl bg-primary-100/60 dark:bg-primary-950/60 text-primary-600 dark:text-primary-400">
              <Target className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white mt-1">
            {goals.length}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">Active personal roadmap</p>
        </div>

        {/* Short-Term Goals */}
        <div
          onClick={() => setActiveTab(activeTab === 'Short-Term' ? 'All' : 'Short-Term')}
          className={`glass-card p-4.5 cursor-pointer transition-all hover:scale-[1.01] ${
            activeTab === 'Short-Term'
              ? 'border-primary-500 ring-2 ring-primary-500/20 dark:ring-primary-400/30'
              : 'hover:border-primary-300 dark:hover:border-primary-700'
          }`}
          title="Click to filter Short-Term Goals"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Short-Term
            </span>
            <div className="p-2 rounded-xl bg-primary-100/60 dark:bg-primary-950/60 text-primary-600 dark:text-primary-400">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-primary-600 dark:text-primary-400 mt-1">
            {shortTermGoals.length}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">Tactical 1-3 month goals</p>
        </div>

        {/* Long-Term Goals */}
        <div
          onClick={() => setActiveTab(activeTab === 'Long-Term' ? 'All' : 'Long-Term')}
          className={`glass-card p-4.5 cursor-pointer transition-all hover:scale-[1.01] ${
            activeTab === 'Long-Term'
              ? 'border-accent-500 ring-2 ring-accent-500/20 dark:ring-accent-400/30'
              : 'hover:border-accent-300 dark:hover:border-accent-700'
          }`}
          title="Click to filter Long-Term Goals"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Long-Term
            </span>
            <div className="p-2 rounded-xl bg-accent-100/60 dark:bg-accent-950/60 text-accent-700 dark:text-accent-300">
              <Compass className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-accent-700 dark:text-accent-300 mt-1">
            {longTermGoals.length}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">Strategic yearly visions</p>
        </div>

        {/* Average Progress */}
        <div className="glass-card p-4.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Avg. Completion
            </span>
            <div className="p-2 rounded-xl bg-emerald-100/60 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl sm:text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
            {avgProgress}%
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">Continuous compounding</p>
        </div>

        {/* 5. Add New Goal Card (adjacent to the 4 boxes) */}
        <button
          type="button"
          onClick={() => openAddGoalModal()}
          className="bg-gradient-to-br from-[#568B75] to-[#3E6857] hover:from-[#4C7C68] hover:to-[#345849] active:from-[#3E6857] active:to-[#2B473B] dark:from-[#75B798] dark:to-[#4A886D] dark:hover:from-[#84C3A5] dark:hover:to-[#579B7D] text-white rounded-2xl p-4.5 shadow-md shadow-primary-900/10 flex flex-col justify-between cursor-pointer transition-all hover:scale-[1.02] border border-white/20 group text-left min-h-[110px]"
          title="Create a new goal"
        >
          <div className="flex items-center justify-between w-full">
            <span className="text-xs font-bold uppercase tracking-wider text-white/90">
              New Target
            </span>
            <div className="p-2 rounded-xl bg-white/20 text-white group-hover:rotate-90 transition-transform duration-300">
              <Plus className="w-4 h-4" />
            </div>
          </div>
          <div>
            <p className="text-base sm:text-lg font-extrabold text-white leading-tight">
              Add Goal
            </p>
            <p className="text-xs text-white/80 mt-1">Set strategic ambition</p>
          </div>
        </button>
      </div>

      {/* Goals Cards Grid directly below */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredGoals.length === 0 ? (
          <div className="lg:col-span-2 text-center py-16 glass-card p-6">
            <Target className="w-10 h-10 mx-auto text-slate-400 dark:text-slate-500 mb-3" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
              No goals found
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto mt-1 mb-5">
              {activeTab === 'All'
                ? 'No goals created yet. Set your ambitions by defining a new goal.'
                : `No ${activeTab} goals found. Click another card above to view goals.`}
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={() => openAddGoalModal()}
            >
              Add New Goal
            </Button>
          </div>
        ) : (
          filteredGoals.map((goal) => (
            <GoalCard
              key={goal.id}
              goal={goal}
              onEdit={openAddGoalModal}
              onDelete={(id) => setDeletingGoalId(id)}
            />
          ))
        )}
      </div>

      {/* Delete Goal Modal */}
      <Modal
        isOpen={Boolean(deletingGoalId)}
        onClose={() => setDeletingGoalId(null)}
        title="Delete Goal"
        subtitle="This action will remove the goal and unbind linked tasks"
        size="sm"
        footer={
          <>
            <Button
              variant="outline"
              size="md"
              onClick={() => setDeletingGoalId(null)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="md"
              icon={Trash2}
              onClick={handleConfirmDelete}
            >
              Delete Goal
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Are you sure you want to delete this goal? Linked tasks will become standalone and remain intact in your task list.
        </p>
      </Modal>
    </div>
  );
}
