export function Card({
  children,
  className = '',
  onClick,
  hover = false,
  padding = 'p-5',
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white dark:bg-[#131B2E] border border-slate-200/90 dark:border-slate-800/80 rounded-xl transition-all duration-200 ${
        hover
          ? 'hover:border-slate-300 dark:hover:border-slate-700/80 hover:shadow-card-hover'
          : 'shadow-card'
      } ${padding} ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  className = '',
  icon: Icon,
}) {
  return (
    <div
      className={`flex items-start justify-between gap-3 mb-4 pb-1 border-b border-slate-100 dark:border-slate-800/60 ${className}`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && (
          <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 shrink-0">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-base truncate">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
