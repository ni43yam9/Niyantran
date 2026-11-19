export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  className = '',
  disabled = false,
  type = 'button',
  onClick,
  ...props
}) {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none';

  const variants = {
    primary:
      'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm focus:ring-indigo-500 dark:bg-indigo-600 dark:hover:bg-indigo-500',
    secondary:
      'bg-slate-100 hover:bg-slate-200 text-slate-800 focus:ring-slate-400 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-100',
    outline:
      'border border-slate-300 hover:bg-slate-50 text-slate-700 focus:ring-slate-400 dark:border-slate-700 dark:hover:bg-slate-800/60 dark:text-slate-200',
    ghost:
      'text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:ring-slate-400 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100',
    danger:
      'bg-rose-600 hover:bg-rose-700 text-white focus:ring-rose-500 dark:bg-rose-600 dark:hover:bg-rose-500',
    subtle:
      'bg-indigo-50 hover:bg-indigo-100 text-indigo-700 focus:ring-indigo-400 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/60 dark:text-indigo-300',
  };

  const sizes = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-3.5 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
    icon: 'p-2 text-sm',
    'icon-sm': 'p-1.5 text-xs',
  };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${baseStyles} ${variants[variant] || variants.primary} ${
        sizes[size] || sizes.md
      } ${className}`}
      {...props}
    >
      {Icon && iconPosition === 'left' && (
        <Icon className={size === 'sm' || size === 'icon-sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
      )}
      {children}
      {Icon && iconPosition === 'right' && (
        <Icon className={size === 'sm' || size === 'icon-sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
      )}
    </button>
  );
}
