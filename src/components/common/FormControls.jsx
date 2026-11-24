export function Input({
  label,
  id,
  type = 'text',
  placeholder,
  value,
  onChange,
  required = false,
  error,
  helperText,
  icon: Icon,
  className = '',
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
        >
          {label} {required && <span className="text-rose-500">*</span>}
        </label>
      )}
      <div className="relative rounded-lg shadow-2xs">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <Icon className="h-4 w-4" />
          </div>
        )}
        <input
          type={type}
          id={id}
          value={value}
          onChange={onChange}
          required={required}
          placeholder={placeholder}
          className={`block w-full rounded-xl border bg-white/60 dark:bg-white/5 backdrop-blur-md text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors ${
            Icon ? 'pl-9 pr-3 py-2' : 'px-3 py-2'
          } ${
            error
              ? 'border-rose-300 dark:border-rose-800 text-rose-900 focus:ring-rose-500'
              : 'border-white/60 dark:border-white/10'
          }`}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-rose-500">{error}</p>}
      {helperText && !error && (
        <p className="text-xs text-slate-400 dark:text-slate-500">{helperText}</p>
      )}
    </div>
  );
}

export function Textarea({
  label,
  id,
  rows = 3,
  placeholder,
  value,
  onChange,
  required = false,
  error,
  helperText,
  className = '',
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
        >
          {label} {required && <span className="text-rose-500">*</span>}
        </label>
      )}
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={onChange}
        required={required}
        placeholder={placeholder}
        className={`block w-full rounded-xl border bg-white/60 dark:bg-white/5 backdrop-blur-md text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors px-3 py-2 ${
          error
            ? 'border-rose-300 dark:border-rose-800 text-rose-900'
            : 'border-white/60 dark:border-white/10'
        }`}
        {...props}
      />
      {error && <p className="text-xs text-rose-500">{error}</p>}
      {helperText && !error && (
        <p className="text-xs text-slate-400 dark:text-slate-500">{helperText}</p>
      )}
    </div>
  );
}

export function Select({
  label,
  id,
  value,
  onChange,
  options = [],
  required = false,
  error,
  helperText,
  className = '',
  placeholder = 'Select an option',
  ...props
}) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
        >
          {label} {required && <span className="text-rose-500">*</span>}
        </label>
      )}
      <select
        id={id}
        value={value}
        onChange={onChange}
        required={required}
        className={`block w-full rounded-xl border bg-white/60 dark:bg-white/5 backdrop-blur-md text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors px-3 py-2 cursor-pointer ${
          error
            ? 'border-rose-300 dark:border-rose-800 text-rose-900'
            : 'border-white/60 dark:border-white/10'
        }`}
        {...props}
      >
        {placeholder && (
          <option value="" disabled className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
            {placeholder}
          </option>
        )}
        {options.map((opt) => (
          <option key={opt.value || opt.id || opt} value={opt.value || opt.id || opt} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
            {opt.label || opt.name || opt}
          </option>
        ))}
      </select>
      {error && <p className="text-xs text-rose-500">{error}</p>}
      {helperText && !error && (
        <p className="text-xs text-slate-400 dark:text-slate-500">{helperText}</p>
      )}
    </div>
  );
}
