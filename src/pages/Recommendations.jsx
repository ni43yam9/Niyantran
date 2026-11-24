import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Clock,
  Target,
  Flame,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  SlidersHorizontal,
  Check,
  X,
  Lightbulb,
  ShieldAlert,
} from 'lucide-react';
import { recommendationService } from '../services/recommendationService';
import { Badge } from '../components/common/Badge';
import { useApp } from '../context/AppContext';

export function Recommendations() {
  const { isBackendOnline, syncWithBackend } = useApp();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [activeStatus, setActiveStatus] = useState('PENDING');
  const [actionInProgress, setActionInProgress] = useState({});

  const loadRecommendations = useCallback(async (statusToFetch = activeStatus) => {
    try {
      setLoading(true);
      const res = await recommendationService.getRecommendations({
        status: statusToFetch,
      });
      if (res) {
        setSummary(res);
      }
    } catch (err) {
      console.warn('Failed to load recommendations:', err);
    } finally {
      setLoading(false);
    }
  }, [activeStatus]);

  useEffect(() => {
    loadRecommendations(activeStatus);
  }, [loadRecommendations, activeStatus]);

  const handleGenerate = async () => {
    try {
      setRefreshing(true);
      const res = await recommendationService.generateRecommendations();
      if (res) {
        setSummary(res);
      }
    } catch (err) {
      console.error('Failed to generate recommendations:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleAccept = async (rec) => {
    try {
      setActionInProgress((prev) => ({ ...prev, [rec.id]: 'accept' }));
      const updated = await recommendationService.acceptRecommendation(rec.id);
      if (updated) {
        // Sync app state if a task was rescheduled
        if (rec.action_type === 'RESCHEDULE_TASK') {
          await syncWithBackend();
        }
        await loadRecommendations(activeStatus);
      }
    } catch (err) {
      console.error('Failed to accept recommendation:', err);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [rec.id]: null }));
    }
  };

  const handleDismiss = async (recId) => {
    try {
      setActionInProgress((prev) => ({ ...prev, [recId]: 'dismiss' }));
      const updated = await recommendationService.dismissRecommendation(recId);
      if (updated) {
        await loadRecommendations(activeStatus);
      }
    } catch (err) {
      console.error('Failed to dismiss recommendation:', err);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [recId]: null }));
    }
  };

  const handleComplete = async (recId) => {
    try {
      setActionInProgress((prev) => ({ ...prev, [recId]: 'complete' }));
      const updated = await recommendationService.completeRecommendation(recId);
      if (updated) {
        await loadRecommendations(activeStatus);
      }
    } catch (err) {
      console.error('Failed to complete recommendation:', err);
    } finally {
      setActionInProgress((prev) => ({ ...prev, [recId]: null }));
    }
  };

  // Filter items based on activeFilter
  const filteredItems = useMemo(() => {
    if (!summary?.items) return [];
    if (activeFilter === 'ALL') return summary.items;
    if (activeFilter === 'RISK_PRIO') {
      return summary.items.filter((r) => r.type === 'DEADLINE_RISK' || r.type === 'PRIORITIZATION');
    }
    if (activeFilter === 'WORKLOAD') {
      return summary.items.filter((r) => r.type === 'WORKLOAD_BALANCE');
    }
    if (activeFilter === 'GOALS') {
      return summary.items.filter((r) => r.type === 'GOAL_PROGRESS');
    }
    if (activeFilter === 'HABITS') {
      return summary.items.filter((r) => r.type === 'HABIT_IMPROVEMENT');
    }
    return summary.items;
  }, [summary, activeFilter]);

  const getTypeBadge = (type) => {
    switch (type) {
      case 'DEADLINE_RISK':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50">
            <AlertTriangle className="w-3 h-3" />
            Deadline Risk
          </span>
        );
      case 'WORKLOAD_BALANCE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-900/50">
            <SlidersHorizontal className="w-3 h-3" />
            Workload Balance
          </span>
        );
      case 'PRIORITIZATION':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-900/50">
            <Sparkles className="w-3 h-3" />
            Focus Priority
          </span>
        );
      case 'GOAL_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-900/50">
            <Target className="w-3 h-3" />
            Goal Momentum
          </span>
        );
      case 'HABIT_IMPROVEMENT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50">
            <Flame className="w-3 h-3" />
            Habit Reinforcement
          </span>
        );
      default:
        return <Badge variant="outline">{type}</Badge>;
    }
  };

  const getPriorityBadge = (prio) => {
    if (prio === 'HIGH') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900/60">
          HIGH
        </span>
      );
    }
    if (prio === 'MEDIUM') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/60">
          MED
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
        LOW
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-5 rounded-2xl glass-silver-gradient backdrop-blur-xl relative overflow-hidden group">
        <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-gradient-to-br from-[#568B75]/25 dark:from-[#75B798]/20 to-transparent blur-2xl pointer-events-none" />
        <div className="absolute -bottom-10 -left-10 w-44 h-44 rounded-full bg-gradient-to-tr from-slate-200/50 dark:from-white/10 to-transparent blur-2xl pointer-events-none" />

        <div className="relative z-10 flex items-start gap-3.5">
          <div className="p-2.5 rounded-xl bg-[#568B75] dark:bg-[#75B798] text-white dark:text-[#101C18] shadow-md shadow-emerald-900/15">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                Intelligent Productivity Recommendations
              </h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-[#568B75]/15 dark:bg-[#75B798]/20 text-[#568B75] dark:text-[#75B798] border border-[#568B75]/30 dark:border-[#75B798]/30">
                Phase 4
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
              Deterministic, explainable intelligence derived from your completion velocity, estimation variance, daily workload capacity, habit streaks, and goal horizons.
            </p>
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={refreshing}
          className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-700 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span>{refreshing ? 'Analyzing...' : 'Scan & Evaluate'}</span>
        </button>
      </div>

      {/* 2. Top Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Active Recommendations</span>
            <Sparkles className="w-4 h-4 text-primary-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
            {summary?.total_active ?? 0}
          </p>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Requires attention</span>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>High Priority / Critical</span>
            <ShieldAlert className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-2">
            {summary?.high_priority_count ?? 0}
          </p>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Urgent risks & deadlines</span>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Workload Balance</span>
            <SlidersHorizontal className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-2">
            {summary?.by_type?.WORKLOAD_BALANCE ?? 0}
          </p>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Overload prevention</span>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
            <span>Habits & Goals</span>
            <Target className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-2">
            {(summary?.by_type?.HABIT_IMPROVEMENT ?? 0) + (summary?.by_type?.GOAL_PROGRESS ?? 0)}
          </p>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">Momentum actions</span>
        </div>
      </div>

      {/* 3. Filter Navigation & Status Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Category Filters */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-x-auto">
          {[
            { id: 'ALL', label: 'All Items' },
            { id: 'RISK_PRIO', label: '🔥 Urgent & Risks' },
            { id: 'WORKLOAD', label: '⚖️ Workload' },
            { id: 'GOALS', label: '🎯 Goals' },
            { id: 'HABITS', label: '🌱 Habits' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
                activeFilter === tab.id
                  ? 'bg-white dark:bg-[#111827] text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200 dark:border-slate-800'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Status Mode (Pending vs Accepted vs Dismissed) */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shrink-0">
          {[
            { id: 'PENDING', label: 'Active' },
            { id: 'ACCEPTED', label: 'Accepted' },
            { id: 'DISMISSED', label: 'Dismissed' },
            { id: 'COMPLETED', label: 'Completed' },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setActiveStatus(st.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeStatus === st.id
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* 4. Recommendation Cards Feed */}
      {loading ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white dark:bg-[#111827] rounded-2xl border border-slate-200 dark:border-slate-800">
          <div className="w-8 h-8 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin" />
          <p className="text-xs font-medium text-slate-500 mt-3">Evaluating productivity metrics...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-[#111827] rounded-2xl border border-dashed border-slate-200 dark:border-slate-800">
          <div className="p-3 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 mb-3">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
            {activeStatus === 'PENDING'
              ? 'All Caught Up!'
              : `No ${activeStatus.toLowerCase()} recommendations found`}
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
            {activeStatus === 'PENDING'
              ? 'Your upcoming workload is balanced, habits are tracking consistently, and no urgent deadline risks were detected.'
              : 'You have not marked any recommendations in this category yet.'}
          </p>
          {activeStatus === 'PENDING' && (
            <button
              onClick={handleGenerate}
              className="mt-4 px-3 py-1.5 rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-600 dark:text-indigo-400 text-xs font-semibold transition-all cursor-pointer"
            >
              Re-scan Database
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredItems.map((rec) => {
            const isProcessingAccept = actionInProgress[rec.id] === 'accept';
            const isProcessingDismiss = actionInProgress[rec.id] === 'dismiss';
            const isProcessingComplete = actionInProgress[rec.id] === 'complete';

            return (
              <div
                key={rec.id}
                className="glass-card glass-card-hover p-5 flex flex-col justify-between space-y-4"
              >
                {/* Header row */}
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <div className="flex items-center gap-2">
                      {getTypeBadge(rec.type)}
                      {getPriorityBadge(rec.priority)}
                    </div>
                    <span className="text-[11px] text-slate-400">
                      {rec.category}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
                    {rec.title}
                  </h3>
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                    {rec.description}
                  </p>
                </div>

                {/* Explainability / Deterministic Reason Callout */}
                <div className="p-3 rounded-xl bg-white/40 dark:bg-white/5 border border-white/60 dark:border-white/10">
                  <div className="flex items-start gap-2">
                    <Lightbulb className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                        Why this recommendation?
                      </span>
                      <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5 leading-relaxed">
                        {rec.reason}
                      </p>
                    </div>
                  </div>

                  {/* Reschedule Action Details */}
                  {rec.action_type === 'RESCHEDULE_TASK' && rec.action_payload && (
                    <div className="mt-2.5 pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                      <span>{rec.action_payload.source_date}</span>
                      <ArrowRight className="w-3 h-3" />
                      <span className="underline decoration-indigo-400 underline-offset-2">
                        {rec.action_payload.suggested_date}
                      </span>
                    </div>
                  )}

                  {rec.action_type === 'FOCUS_TASK' && rec.action_payload?.suggested_window && (
                    <div className="mt-2.5 pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center gap-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400">
                      <Clock className="w-3 h-3" />
                      <span>Suggested: {rec.action_payload.suggested_window}</span>
                    </div>
                  )}
                </div>

                {/* Action Footer */}
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between">
                  {rec.status === 'PENDING' ? (
                    <>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAccept(rec)}
                          disabled={isProcessingAccept}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                        >
                          <Check className="w-3 h-3" />
                          <span>{rec.action_type === 'RESCHEDULE_TASK' ? 'Apply & Reschedule' : 'Accept'}</span>
                        </button>

                        <button
                          onClick={() => handleComplete(rec.id)}
                          disabled={isProcessingComplete}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Mark Done</span>
                        </button>
                      </div>

                      <button
                        onClick={() => handleDismiss(rec.id)}
                        disabled={isProcessingDismiss}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs font-medium transition-all cursor-pointer"
                      >
                        <X className="w-3 h-3" />
                        <span>Dismiss</span>
                      </button>
                    </>
                  ) : (
                    <div className="flex items-center justify-between w-full">
                      <span className="text-xs font-semibold text-slate-500">
                        Status: <span className="font-bold text-indigo-600 dark:text-indigo-400">{rec.status}</span>
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {rec.updated_at ? new Date(rec.updated_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
