import type React from "react";

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  stage?: boolean;
  interactive?: boolean;
  compact?: boolean;
  highlighted?: boolean;
  onClick?: () => void;
}

export function Card({
  children,
  className = "",
  stage = false,
  interactive = false,
  compact = false,
  highlighted = false,
  onClick,
}: CardProps): React.JSX.Element {
  const baseClasses = "rounded-2xl border bg-white transition-all";
  const stageClasses = stage
    ? "p-8 sm:p-12 shadow-xl shadow-slate-200/60 relative overflow-hidden border-slate-200/90"
    : compact
      ? "p-4 shadow-xs border-slate-200"
      : "p-6 shadow-xs border-slate-200/90";

  const interactiveClasses = interactive
    ? "hover:border-slate-300 hover:shadow-md cursor-pointer active:scale-[0.99]"
    : "";

  const highlightClasses = highlighted
    ? "border-indigo-200 bg-indigo-50/20 ring-1 ring-indigo-200/60"
    : "";

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: Interactive behavior delegated conditionally
    <div
      onClick={onClick}
      className={`${baseClasses} ${stageClasses} ${interactiveClasses} ${highlightClasses} ${className}`}
    >
      {children}
    </div>
  );
}
