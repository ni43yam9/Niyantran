export function Badge({
  children,
  size = 'md',
  className = '',
  dot = false,
  dotColor = '',
}) {
  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-medium',
    lg: 'text-sm px-3 py-1.5 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border transition-colors ${sizeStyles[size]} ${className}`}
    >
      {dot && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${dotColor || 'bg-current'}`}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
