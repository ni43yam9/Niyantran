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
    'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none';

  const variants = {
    primary:
      'bg-[#568B75] hover:bg-[#467360] active:bg-[#385C4D] text-white shadow-sm focus:ring-[#568B75]/50 dark:bg-[#75B798] dark:hover:bg-[#86c4a6] dark:active:bg-[#568B75] dark:text-[#101C18] font-semibold',
    secondary:
      'glass-btn-secondary focus:ring-[#568B75]/30',
    outline:
      'border border-white/60 dark:border-white/10 hover:bg-white/40 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200 focus:ring-slate-400',
    ghost:
      'text-slate-600 hover:bg-white/40 hover:text-slate-900 focus:ring-slate-400 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-slate-100',
    danger:
      'bg-[#DC6B6B] hover:bg-[#c95858] text-white focus:ring-[#DC6B6B]/50 dark:bg-[#F08080] dark:hover:bg-[#e07070] dark:text-[#101C18]',
    subtle:
      'bg-[#568B75]/15 hover:bg-[#568B75]/25 text-[#243C32] focus:ring-[#568B75]/40 dark:bg-[#75B798]/15 dark:hover:bg-[#75B798]/25 dark:text-[#75B798]',
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
