import type React from "react";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps): React.JSX.Element {
  return (
    <div
      className={`text-center py-12 px-6 border border-dashed border-slate-200 rounded-2xl bg-slate-50/40 space-y-4 ${className}`}
    >
      {icon && (
        <div className="w-12 h-12 mx-auto rounded-xl bg-slate-100 flex items-center justify-center text-slate-400">
          {icon}
        </div>
      )}
      <div className="space-y-1 max-w-sm mx-auto">
        <h3 className="text-sm font-semibold text-slate-900 tracking-tight">{title}</h3>
        <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

