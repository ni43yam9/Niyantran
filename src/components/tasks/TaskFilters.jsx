import { Search, X, Plus } from 'lucide-react';
import { Button } from '../common/Button';

export function TaskFilters({
  activeTab,
  onSelectTab,
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  selectedPriority,
  onPriorityChange,
  sortBy,
  onSortChange,
  onClearFilters,
  hasActiveFilters,
  tabCounts,
  onAddNew,
}) {
  const tabs = [
    { id: 'All Tasks', label: 'All Tasks' },
    { id: 'Today', label: 'Today' },
    { id: 'Upcoming', label: 'Upcoming' },
    { id: 'Daily', label: 'Daily' },
    { id: 'Short-Term', label: 'Short-Term' },
    { id: 'Long-Term', label: 'Long-Term' },
    { id: 'Occasional', label: 'Occasional' },
    { id: 'Completed', label: 'Completed' },
    { id: 'Overdue', label: 'Overdue' },
  ];

  const categories = [
    'All Categories',
    'Academic',
    'Coding',
    'Career',
    'Reading',
    'Health',
    'Personal',
  ];

  const priorities = ['All Priorities', 'High', 'Medium', 'Low'];

  const sortOptions = [
    { value: 'dueDateAsc', label: 'Due Date: Soonest' },
    { value: 'dueDateDesc', label: 'Due Date: Latest' },
    { value: 'priorityHigh', label: 'Priority: High to Low' },
    { value: 'priorityLow', label: 'Priority: Low to High' },
    { value: 'titleAsc', label: 'Title: A-Z' },
    { value: 'titleDesc', label: 'Title: Z-A' },
  ];

  return (
    <div className="space-y-4">
      {/* 1. Horizontal Scrollable Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 no-scrollbar border-b border-white/60 dark:border-white/10">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const count = tabCounts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onSelectTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                isActive
                  ? 'bg-primary-600 dark:bg-primary-500 text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-white/50 dark:hover:bg-white/10 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive
                    ? 'bg-black/20 text-white'
                    : 'bg-white/60 dark:bg-white/10 text-slate-500 dark:text-slate-400'
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* 2. Controls Toolbar: Search, Filters, Sorting, and Add button */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3 items-center">
        {/* Search */}
        <div className="lg:col-span-4 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by title or description..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-white/60 dark:bg-white/5 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-xl pl-9 pr-8 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-2xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Category Filter */}
        <div className="lg:col-span-2">
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="w-full bg-white/60 dark:bg-white/5 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-xl px-3 py-2 text-xs text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-2xs cursor-pointer"
          >
            {categories.map((c) => (
              <option key={c} value={c} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Priority Filter */}
        <div className="lg:col-span-2">
          <select
            value={selectedPriority}
            onChange={(e) => onPriorityChange(e.target.value)}
            className="w-full bg-white/60 dark:bg-white/5 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-xl px-3 py-2 text-xs text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-2xs cursor-pointer"
          >
            {priorities.map((p) => (
              <option key={p} value={p} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Sort By */}
        <div className="lg:col-span-2">
          <select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            className="w-full bg-white/60 dark:bg-white/5 border border-white/60 dark:border-white/10 backdrop-blur-md rounded-xl px-3 py-2 text-xs text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500 shadow-2xs cursor-pointer"
          >
            {sortOptions.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Add Task Button */}
        <div className="lg:col-span-2 flex items-center justify-end gap-2">
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onClearFilters}
              className="text-xs font-semibold text-primary-600 dark:text-primary-400 hover:underline px-2"
            >
              Reset
            </button>
          )}
          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={onAddNew}
            className="w-full lg:w-auto"
          >
            Add Task
          </Button>
        </div>
      </div>
    </div>
  );
}
