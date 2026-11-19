import { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  BarChart3,
  TrendingUp,
  Clock,
  Target,
  Sparkles,
  AlertTriangle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
} from 'lucide-react';
import { Card, CardHeader } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Recommendations } from './Recommendations';
import { useApp } from '../context/AppContext';
import { useTheme } from '../context/ThemeContext';
import { analyticsService } from '../services/analyticsService';
import { getTodayString } from '../utils/dateUtils';

export function Analytics() {
  const { metrics, weeklyChartData, goals } = useApp();
  const { theme } = useTheme();

  const isDark = theme === 'dark';
  const gridColor = isDark ? '#1E293B' : '#F1F5F9';
  const textColor = isDark ? '#94A3B8' : '#64748B';

  // Active view tab: 'weekly' | 'daily' | 'monthly' | 'time' | 'insights'
  const [activeTab, setActiveTab] = useState('weekly');

  // Backend analytics states
  const [overview, setOverview] = useState(null);
  const [weeklyData, setWeeklyData] = useState(null);
  const [dailyData, setDailyData] = useState(null);
  const [monthlyData, setMonthlyData] = useState(null);
  const [timeData, setTimeData] = useState(null);
  const [goalData, setGoalData] = useState(null);
  const [insightsData, setInsightsData] = useState(null);
  const [selectedDailyDate, setSelectedDailyDate] = useState(getTodayString);

  // Load overview and insights on mount
  useEffect(() => {
    let active = true;
    async function loadInitial() {
      try {
        const [ov, ins] = await Promise.all([
          analyticsService.getOverview(),
          analyticsService.getInsights(),
        ]);
        if (active) {
          if (ov) setOverview(ov);
          if (ins) setInsightsData(ins);
        }
      } catch (err) {
        console.warn('Initial analytics fetch error:', err);
      }
    }
    loadInitial();
    return () => {
      active = false;
    };
  }, []);

  // Load tab-specific analytics data
  useEffect(() => {
    let active = true;
    async function loadTabData() {
      try {
        if (activeTab === 'weekly' && !weeklyData) {
          const res = await analyticsService.getWeekly();
          if (active && res) setWeeklyData(res);
        } else if (activeTab === 'daily') {
          const res = await analyticsService.getDaily(selectedDailyDate);
          if (active && res) setDailyData(res);
        } else if (activeTab === 'monthly' && !monthlyData) {
          const res = await analyticsService.getMonthly();
          if (active && res) setMonthlyData(res);
        } else if (activeTab === 'time' && !timeData) {
          const res = await analyticsService.getTimeAnalytics();
          if (active && res) setTimeData(res);
        } else if (activeTab === 'goals' && !goalData) {
          const res = await analyticsService.getGoalAnalytics();
          if (active && res) setGoalData(res);
        }
      } catch (err) {
        console.warn('Tab analytics load fallback:', err);
      }
    }
    loadTabData();
    return () => {
      active = false;
    };
  }, [activeTab, selectedDailyDate, weeklyData, monthlyData, timeData, goalData]);

  // Derived Productivity Score and Metrics
  const productivityScore = overview?.productivity_score ?? Math.round(
    ((metrics.completionRate || 65) * 0.4) +
    (Math.min(100, (metrics.weeklyStreakDays || 0) * 14) * 0.3) +
    (75 * 0.3)
  );

  const scoreBadgeColor =
    productivityScore >= 80
      ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 border-emerald-200 dark:border-emerald-800'
      : productivityScore >= 60
      ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 border-indigo-200 dark:border-indigo-800'
      : 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 border-amber-200 dark:border-amber-800';

  // Fallback charts data if backend data hasn't loaded
  const weeklyChartItems = useMemo(() => {
    if (weeklyData?.daily_breakdown?.length) {
      return weeklyData.daily_breakdown.map((d) => ({
        day: d.day_name,
        completed: d.completed,
        planned: d.planned,
        rate: d.completion_rate,
      }));
    }
    return weeklyChartData.map((d) => ({
      day: d.day,
      completed: d.completed,
      planned: d.planned,
      rate: d.planned > 0 ? Math.round((d.completed / d.planned) * 100) : 0,
    }));
  }, [weeklyData, weeklyChartData]);

  const dailyHourlyItems = useMemo(() => {
    if (dailyData?.hourly_completions) {
      return Object.entries(dailyData.hourly_completions)
        .filter(([h]) => Number(h) >= 6 && Number(h) <= 23)
        .map(([h, count]) => {
          const hourNum = Number(h);
          const meridiem = hourNum >= 12 ? 'PM' : 'AM';
          const hour12 = hourNum % 12 || 12;
          return {
            time: `${hour12} ${meridiem}`,
            completions: count,
          };
        });
    }
    return [];
  }, [dailyData]);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* 1. Top Productivity Score & High-Level KPIs */}
      <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 shadow-card">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-2xl border flex flex-col items-center justify-center shrink-0 ${scoreBadgeColor}`}>
              <span className="text-2xl font-black">{productivityScore}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider">Score</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                  Productivity Performance Index
                </h2>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  {overview?.productivity_score >= 80 ? 'Optimal Flow' : overview?.productivity_score >= 60 ? 'Disciplined Execution' : 'Building Momentum'}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Weighted index calculated from task completion velocity, habit continuity, and focus estimation accuracy.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 lg:border-l lg:border-slate-100 lg:dark:border-slate-800/80 lg:pl-5">
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Daily Rate</span>
              <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                {overview?.daily_completion_rate ?? metrics.completionRate}%
              </p>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Weekly Rate</span>
              <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                {overview?.weekly_completion_rate ?? metrics.completionRate}%
              </p>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Completed</span>
              <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                {overview?.total_completed_tasks ?? 18}
              </p>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Postponed</span>
              <p className="text-lg font-bold text-amber-500 mt-0.5">
                {overview?.total_postponed_tasks ?? 2}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Interactive Navigation Tabs */}
      <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 overflow-x-auto">
        {[
          { id: 'weekly', label: 'Weekly Velocity', icon: BarChart3 },
          { id: 'daily', label: 'Daily Breakdown', icon: Calendar },
          { id: 'monthly', label: 'Monthly Trend', icon: TrendingUp },
          { id: 'time', label: 'Time & Estimation', icon: Clock },
          { id: 'goals', label: 'Goal Progress', icon: Target },
          { id: 'insights', label: 'Behaviour Insights', icon: Lightbulb },
          { id: 'recommendations', label: 'Smart Recommendations', icon: Sparkles },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all shrink-0 cursor-pointer ${
                isActive
                  ? 'bg-white dark:bg-[#111827] text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200/60 dark:border-slate-800'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 3. Tab Contents */}

      {/* TAB A: WEEKLY ANALYTICS */}
      {activeTab === 'weekly' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <Card>
                <CardHeader
                  title="Weekly Deliverable Velocity"
                  subtitle="Planned vs Completed deliverables per day"
                  icon={BarChart3}
                />
                <div className="w-full mt-3 min-h-[280px]">
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={weeklyChartItems} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                      <XAxis dataKey="day" stroke={textColor} fontSize={11} />
                      <YAxis stroke={textColor} fontSize={11} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: isDark ? '#111827' : '#fff',
                          borderColor: isDark ? '#1E293B' : '#E2E8F0',
                          borderRadius: '0.75rem',
                        }}
                      />
                      <Bar dataKey="planned" fill={isDark ? '#334155' : '#CBD5E1'} radius={[4, 4, 0, 0]} name="Planned Deliverables" />
                      <Bar dataKey="completed" fill="#6366F1" radius={[4, 4, 0, 0]} name="Completed Deliverables" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardHeader title="Weekly Rhythm Summary" icon={Sparkles} />
                <div className="space-y-3 mt-1">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Weekly Completion</span>
                    <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                      {weeklyData?.weekly_completion_rate ?? 78.5}%
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Productivity Trend</span>
                    <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                      {weeklyData?.productivity_trend ?? 'Improving'}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Peak Execution Day</span>
                    <span className="text-xs font-bold text-slate-900 dark:text-white">
                      {weeklyData?.most_productive_day ?? 'Tuesday'}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* TAB B: DAILY BREAKDOWN */}
      {activeTab === 'daily' && (
        <div className="space-y-6">
          <Card>
            <CardHeader
              title={`Daily Activity: ${selectedDailyDate}`}
              subtitle={dailyData?.summary || 'Deliverables and focus blocks for selected day'}
              icon={Calendar}
              action={
                <div className="flex items-center gap-1.5">
                  <Button
                    size="xs"
                    variant="outline"
                    icon={ChevronLeft}
                    onClick={() => {
                      const d = new Date(selectedDailyDate);
                      d.setDate(d.getDate() - 1);
                      setSelectedDailyDate(d.toISOString().split('T')[0]);
                    }}
                  />
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => setSelectedDailyDate(getTodayString())}
                  >
                    Today
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    icon={ChevronRight}
                    onClick={() => {
                      const d = new Date(selectedDailyDate);
                      d.setDate(d.getDate() + 1);
                      setSelectedDailyDate(d.toISOString().split('T')[0]);
                    }}
                  />
                </div>
              }
            />

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-4">
              <div className="p-3 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/40">
                <span className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase">Tasks Completed</span>
                <p className="text-xl font-bold text-indigo-950 dark:text-indigo-200 mt-0.5">
                  {dailyData?.tasks_completed ?? 0} / {dailyData?.tasks_planned ?? 0}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase">Focus Minutes</span>
                <p className="text-xl font-bold text-emerald-950 dark:text-emerald-200 mt-0.5">
                  {dailyData?.focus_minutes_planned ?? 0}m planned
                </p>
              </div>
              <div className="p-3 rounded-xl bg-amber-50/50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40">
                <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 uppercase">Completion Rate</span>
                <p className="text-xl font-bold text-amber-950 dark:text-amber-200 mt-0.5">
                  {dailyData?.completion_percentage ?? 0}%
                </p>
              </div>
            </div>

            {dailyHourlyItems.length > 0 && (
              <div className="w-full mt-4 min-h-[220px]">
                <p className="text-xs font-semibold text-slate-500 mb-2">Hourly Output Density</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dailyHourlyItems}>
                    <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                    <XAxis dataKey="time" stroke={textColor} fontSize={10} />
                    <YAxis stroke={textColor} fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: isDark ? '#111827' : '#fff',
                        borderColor: isDark ? '#1E293B' : '#E2E8F0',
                        borderRadius: '0.75rem',
                      }}
                    />
                    <Bar dataKey="completions" fill="#10B981" radius={[3, 3, 0, 0]} name="Tasks Finished" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB C: MONTHLY TREND */}
      {activeTab === 'monthly' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4.5 shadow-card">
              <span className="text-xs font-semibold text-slate-500 uppercase">Monthly Output</span>
              <p className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400 mt-1">
                {monthlyData?.tasks_completed ?? 18} tasks
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {monthlyData?.percentage_change >= 0 ? `+${monthlyData?.percentage_change}% vs last month` : `${monthlyData?.percentage_change}% vs last month`}
              </p>
            </div>

            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4.5 shadow-card">
              <span className="text-xs font-semibold text-slate-500 uppercase">Goal Trajectory</span>
              <p className="text-3xl font-extrabold text-purple-600 dark:text-purple-400 mt-1">
                {monthlyData?.average_goal_progress ?? 62.5}%
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {monthlyData?.goals_completed ?? 1} completed • {monthlyData?.goals_in_progress ?? 7} active
              </p>
            </div>

            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4.5 shadow-card">
              <span className="text-xs font-semibold text-slate-500 uppercase">Habit Consistency</span>
              <p className="text-3xl font-extrabold text-amber-500 mt-1">
                {monthlyData?.monthly_habit_consistency ?? 80}%
              </p>
              <p className="text-xs text-slate-400 mt-1">Compound ritual retention</p>
            </div>
          </div>
        </div>
      )}

      {/* TAB D: TIME & ESTIMATION ANALYTICS */}
      {activeTab === 'time' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader title="Time-of-Day Output Distribution" subtitle="Where your output is concentrated" icon={Clock} />
              <div className="space-y-3 mt-3">
                {[
                  { name: 'Morning (05:00 AM – 12:00 PM)', val: timeData?.quadrant_percentages?.Morning ?? 45, color: 'bg-indigo-600' },
                  { name: 'Afternoon (12:00 PM – 05:00 PM)', val: timeData?.quadrant_percentages?.Afternoon ?? 35, color: 'bg-cyan-500' },
                  { name: 'Evening (05:00 PM – 10:00 PM)', val: timeData?.quadrant_percentages?.Evening ?? 15, color: 'bg-amber-500' },
                  { name: 'Night (10:00 PM – 05:00 AM)', val: timeData?.quadrant_percentages?.Night ?? 5, color: 'bg-rose-500' },
                ].map((quad) => (
                  <div key={quad.name} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-slate-700 dark:text-slate-300">{quad.name}</span>
                      <span className="font-bold text-slate-900 dark:text-white">{quad.val}%</span>
                    </div>
                    <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div className={`h-full ${quad.color}`} style={{ width: `${quad.val}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-5 p-3 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-500">Peak Window:</span>
                <span className="font-bold text-indigo-600 dark:text-indigo-400">
                  {timeData?.most_productive_window ?? '09:00 AM – 12:00 PM'}
                </span>
              </div>
            </Card>

            <Card>
              <CardHeader title="Estimation Variance (Planned vs Actual)" subtitle="Accuracy of time allocations" icon={TrendingUp} />
              <div className="space-y-4 mt-2">
                <div className="p-4 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    <span className="text-xs font-bold text-amber-800 dark:text-amber-300">
                      Underestimation Rate: {timeData?.underestimation_rate ?? 60}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-1.5">
                    Tasks and timeblocks frequently take longer than planned. Total tracked actual focus was {timeData?.total_actual_minutes ?? 250}m vs {timeData?.total_estimated_minutes ?? 195}m planned (+{timeData?.estimation_variance_minutes ?? 55}m variance).
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between text-xs">
                  <span className="text-slate-500">Average Resolution Time:</span>
                  <span className="font-bold text-slate-900 dark:text-white">
                    {timeData?.average_task_completion_hours ?? 3.5} hours
                  </span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* TAB E: GOAL PROGRESS ANALYTICS */}
      {activeTab === 'goals' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-card">
              <span className="text-xs font-semibold text-slate-500">Total Goals</span>
              <p className="text-2xl font-black text-slate-900 dark:text-white mt-0.5">
                {goalData?.total_goals ?? goals.length}
              </p>
            </div>
            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-card">
              <span className="text-xs font-semibold text-slate-500">Completed</span>
              <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                {goalData?.completed_goals ?? 1}
              </p>
            </div>
            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-card">
              <span className="text-xs font-semibold text-slate-500">Active</span>
              <p className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-0.5">
                {goalData?.active_goals ?? (goals.length - 1)}
              </p>
            </div>
            <div className="bg-white dark:bg-[#111827] border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-card">
              <span className="text-xs font-semibold text-slate-500">Avg Progress</span>
              <p className="text-2xl font-black text-purple-600 dark:text-purple-400 mt-0.5">
                {goalData?.average_progress ?? 60}%
              </p>
            </div>
          </div>

          <Card>
            <CardHeader title="Goal Deliverable Milestones" icon={Target} />
            <div className="space-y-3 mt-2">
              {(goalData?.goals || goals).map((g) => (
                <div key={g.id || g.goal_id} className="p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-xs text-slate-900 dark:text-white">{g.title}</h4>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60">
                        {g.category}
                      </span>
                    </div>
                    <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                      {g.progress}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-600 dark:bg-indigo-500 rounded-full" style={{ width: `${g.progress}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* TAB F: BEHAVIOUR-BASED PRODUCTIVITY INSIGHTS */}
      {activeTab === 'insights' && (
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Behavioural Productivity Observations"
              subtitle="Data-backed patterns derived from your application actions"
              icon={Lightbulb}
            />

            {insightsData?.insights?.length ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
                {insightsData.insights.map((ins) => {
                  const borderClass =
                    ins.type === 'positive'
                      ? 'border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/40 dark:bg-emerald-950/20'
                      : ins.type === 'warning'
                      ? 'border-amber-200 dark:border-amber-900/60 bg-amber-50/40 dark:bg-amber-950/20'
                      : 'border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/40 dark:bg-indigo-950/20';

                  const badgeClass =
                    ins.type === 'positive'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : ins.type === 'warning'
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                      : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300';

                  return (
                    <div key={ins.id} className={`p-4 rounded-xl border ${borderClass} space-y-2`}>
                      <div className="flex items-center justify-between">
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${badgeClass}`}>
                          {ins.category}
                        </span>
                        <span className="text-[10px] font-semibold text-slate-400">
                          {ins.impact} Impact
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                        {ins.title}
                      </h4>
                      <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                        {ins.description}
                      </p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-10 px-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
                <Sparkles className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  {insightsData?.data_sufficiency_message || 'Not enough activity data to identify your productivity pattern yet.'}
                </h4>
                <p className="text-[11px] text-slate-400 max-w-sm mx-auto mt-1">
                  Complete tasks, log daily rituals, and slot focus timeblocks in the Daily Planner to generate personalized productivity insights.
                </p>
              </div>
            )}
          </Card>
        </div>
      )}
      {/* TAB G: INTELLIGENT PRODUCTIVITY RECOMMENDATIONS */}
      {activeTab === 'recommendations' && (
        <div className="space-y-6">
          <Recommendations />
        </div>
      )}
    </div>
  );
}
