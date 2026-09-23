import type React from "react";

interface SkeletonProps {
  className?: string;
}

// Fundamental skeleton primitive with subtle pulse
export function Skeleton({ className = "" }: SkeletonProps): React.JSX.Element {
  return (
    <div className={`animate-pulse rounded-md bg-slate-200/70 ${className}`} aria-hidden="true" />
  );
}

// Skeleton card matching standard Card geometry to guarantee CLS = 0
export function SkeletonCard(): React.JSX.Element {
  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-5 space-y-4 shadow-xs">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-4 w-4 rounded-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-3 w-44" />
      </div>
    </div>
  );
}

// Skeleton row for list items with exact line heights
export function SkeletonRow(): React.JSX.Element {
  return (
    <div className="flex items-center justify-between p-4 rounded-lg border border-slate-100 bg-slate-50/50">
      <div className="flex items-center gap-3">
        <Skeleton className="w-8 h-8 rounded-lg" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-40" />
        </div>
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  );
}
