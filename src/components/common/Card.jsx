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
      className={`glass-card ${
        hover
          ? 'glass-card-hover cursor-pointer'
          : ''
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
      className={`flex items-start justify-between gap-3 mb-4 pb-2 border-b border-white/60 dark:border-white/10 ${className}`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && (
          <div className="p-2 rounded-xl bg-sage-primary/10 dark:bg-forest-primary/15 text-sage-primary dark:text-forest-primary shrink-0">
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
