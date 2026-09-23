import type React from "react";

export type BadgeVariant = "active" | "pending" | "archived" | "danger" | "info" | "default";
export type BadgeSize = "sm" | "md";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, { container: string; dot: string }> = {
  active: {
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-600 animate-pulse",
  },
  pending: {
    container: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-600",
  },
  archived: {
    container: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
  },
  danger: {
    container: "bg-rose-50 text-rose-700 border-rose-200",
    dot: "bg-rose-600",
  },
  info: {
    container: "bg-indigo-50 text-indigo-700 border-indigo-200",
    dot: "bg-indigo-600",
  },
  default: {
    container: "bg-slate-50 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
  },
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-xs gap-1",
  md: "px-2.5 py-1 text-xs gap-1.5",
};

export function Badge({
  children,
  variant = "default",
  size = "sm",
  dot = false,
  className = "",
}: BadgeProps): React.JSX.Element {
  const styles = variantStyles[variant];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border tracking-tight ${styles.container} ${sizeStyles[size]} ${className}`}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${styles.dot}`}
          aria-hidden="true"
        />
      )}
      <span>{children}</span>
    </span>
  );
}
