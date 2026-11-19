export function ProgressBar({
  value = 0,
  max = 100,
  size = 'md',
  color = 'indigo',
  showLabel = false,
  className = '',
}) {
  const percentage = Math.min(Math.max(Math.round((value / max) * 100), 0), 100);

  const sizeStyles = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  };

  const colorStyles = {
    indigo: 'bg-indigo-600 dark:bg-indigo-500',
    emerald: 'bg-emerald-500 dark:bg-emerald-400',
    amber: 'bg-amber-500 dark:bg-amber-400',
    rose: 'bg-rose-500 dark:bg-rose-400',
    blue: 'bg-blue-600 dark:bg-blue-500',
  };

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between items-center text-xs text-slate-500 dark:text-slate-400 mb-1.5 font-medium">
          <span>Progress</span>
          <span className="font-semibold text-slate-700 dark:text-slate-200">
            {percentage}%
          </span>
        </div>
      )}
      <div
        className={`w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden ${
          sizeStyles[size] || sizeStyles.md
        }`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            colorStyles[color] || colorStyles.indigo
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
