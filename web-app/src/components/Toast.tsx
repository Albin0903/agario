import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type React from "react";
import { springs } from "../lib/springs";

export type ToastType = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

export interface ToastContainerProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

const typeConfig: Record<
  ToastType,
  { icon: typeof CheckCircle2; container: string; iconClass: string }
> = {
  success: {
    icon: CheckCircle2,
    container: "border-emerald-200 bg-white shadow-emerald-500/5",
    iconClass: "text-emerald-600",
  },
  error: {
    icon: AlertCircle,
    container: "border-rose-200 bg-white shadow-rose-500/5",
    iconClass: "text-rose-600",
  },
  info: {
    icon: Info,
    container: "border-indigo-200 bg-white shadow-indigo-500/5",
    iconClass: "text-indigo-600",
  },
};

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps): React.JSX.Element {
  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
    >
      <AnimatePresence>
        {toasts.map((toast) => {
          const config = typeConfig[toast.type];
          const IconComponent = config.icon;

          return (
            <motion.output
              key={toast.id}
              layout
              initial={{ opacity: 0, y: -12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }}
              transition={{ type: "spring", ...springs.bouncy }}
              className={`pointer-events-auto rounded-xl border p-4 shadow-lg flex items-start gap-3 text-left ${config.container}`}
            >
              <IconComponent className={`w-5 h-5 shrink-0 mt-0.5 ${config.iconClass}`} />
              <div className="flex-1 space-y-0.5">
                <p className="text-xs font-semibold text-slate-900 tracking-tight">{toast.title}</p>
                {toast.message && (
                  <p className="text-xs text-slate-500 leading-normal">{toast.message}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md transition-colors cursor-pointer"
                title="Fermer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.output>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
