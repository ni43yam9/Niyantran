import {
  ResponsiveContainer,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { BarChart3, TrendingUp, PieChart as PieChartIcon } from 'lucide-react';
import { Card, CardHeader } from '../common/Card';
import { useApp } from '../../context/AppContext';
import { useTheme } from '../../context/ThemeContext';

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="p-3 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs space-y-1 font-medium">
        <p className="font-bold border-b border-slate-100 dark:border-slate-800 pb-1 mb-1">
          {label}
        </p>
        {payload.map((entry, index) => (
          <div key={`item-${index}`} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-1.5" style={{ color: entry.color }}>
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span>{entry.name}:</span>
            </span>
            <span className="font-bold">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export function ProductivitySection() {
  const { weeklyChartData, categoryDistributionData } = useApp();
  const { theme } = useTheme();

  const isDark = theme === 'dark';
  const gridColor = isDark ? '#1E293B' : '#F1F5F9';
  const textColor = isDark ? '#94A3B8' : '#64748B';
  const tooltipBg = isDark ? '#111827' : '#FFFFFF';
  const tooltipBorder = isDark ? '#1F293D' : '#E2E8F0';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white">
            Productivity & Output Analytics
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Velocity metrics, completion trends, and subject allocations
          </p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60">
          Last 7 Days
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. Weekly Task Completion Bar Chart */}
        <Card className="flex flex-col">
          <CardHeader
            title="Weekly Task Completion"
            subtitle="Completed vs Planned deliverables"
            icon={BarChart3}
          />
          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="day" stroke={textColor} fontSize={11} tickLine={false} />
                <YAxis stroke={textColor} fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar
                  dataKey="completed"
                  name="Completed"
                  fill="#4F46E5"
                  radius={[4, 4, 0, 0]}
                  barSize={14}
                />
                <Bar
                  dataKey="planned"
                  name="Planned"
                  fill={isDark ? '#334155' : '#CBD5E1'}
                  radius={[4, 4, 0, 0]}
                  barSize={14}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-center gap-6 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600" />
              <span>Completed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-slate-300 dark:bg-slate-700" />
              <span>Planned</span>
            </div>
          </div>
        </Card>

        {/* 2. Productivity & Focus Hours Overview Area Chart */}
        <Card className="flex flex-col">
          <CardHeader
            title="Deep Focus Trend"
            subtitle="Daily logged deep focus hours"
            icon={TrendingUp}
          />
          <div className="h-64 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={weeklyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="focusGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06B6D4" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis dataKey="day" stroke={textColor} fontSize={11} tickLine={false} />
                <YAxis stroke={textColor} fontSize={11} tickLine={false} axisLine={false} unit="h" />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="focusHours"
                  name="Focus Hours"
                  stroke="#06B6D4"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#focusGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
            <span className="text-slate-500">Weekly Total: 33.2 hrs</span>
            <span className="font-semibold text-cyan-600 dark:text-cyan-400">
              Avg 4.7 hrs/day
            </span>
          </div>
        </Card>

        {/* 3. Category-wise Task Distribution Donut Chart */}
        <Card className="flex flex-col">
          <CardHeader
            title="Category Allocation"
            subtitle="Distribution of current workload"
            icon={PieChartIcon}
          />
          <div className="h-48 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryDistributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {categoryDistributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [`${value} tasks`, name]}
                  contentStyle={{
                    backgroundColor: tooltipBg,
                    borderColor: tooltipBorder,
                    borderRadius: '0.75rem',
                    color: isDark ? '#fff' : '#000',
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Custom Category Legend */}
          <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px]">
            {categoryDistributionData.map((cat) => (
              <div key={cat.name} className="flex items-center gap-1.5 truncate">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: cat.color }}
                />
                <span className="truncate text-slate-600 dark:text-slate-400">
                  {cat.name} ({cat.value})
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
