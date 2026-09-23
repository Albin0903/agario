import type React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  id?: string;
}

export function Input({
  label,
  error,
  helperText,
  id,
  className = "",
  disabled,
  ...props
}: InputProps): React.JSX.Element {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

  return (
    <div className="space-y-1.5 text-left w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium text-slate-700 select-none tracking-tight"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={inputId}
          disabled={disabled}
          className={`w-full rounded-lg border bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 transition-colors shadow-xs
            focus:outline-none focus:ring-2 focus:ring-offset-1
            disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed
            ${
              error
                ? "border-rose-300 focus:border-rose-500 focus:ring-rose-500/30 text-rose-900"
                : "border-slate-200 hover:border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/20"
            } ${className}`}
          {...props}
        />
      </div>
      {error ? (
        <p className="text-xs text-rose-600 font-medium tracking-tight">{error}</p>
      ) : helperText ? (
        <p className="text-xs text-slate-500 tracking-tight">{helperText}</p>
      ) : null}
    </div>
  );
}

