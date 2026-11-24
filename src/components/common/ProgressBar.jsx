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
    indigo: 'bg-[#568B75] dark:bg-[#75B798]',
    emerald: 'bg-[#4D9673] dark:bg-[#75C69A]',
    amber: 'bg-[#D69A50] dark:bg-[#E8B76C]',
    rose: 'bg-[#DC6B6B] dark:bg-[#F08080]',
    blue: 'bg-[#7295B5] dark:bg-[#82B4D8]',
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
        className={`w-full bg-white/50 dark:bg-white/10 rounded-full overflow-hidden border border-white/60 dark:border-white/10 ${
          sizeStyles[size] || sizeStyles.md
        }`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out shadow-xs ${
            colorStyles[color] || colorStyles.indigo
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
