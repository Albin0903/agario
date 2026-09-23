import { AnimatePresence, motion } from "motion/react";
import type React from "react";
import { useEffect, useRef } from "react";
import { springs } from "../lib/springs";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className = "",
}: DialogProps): React.JSX.Element {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop with soft blur and gentle fade */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs"
            aria-hidden="true"
          />

          {/* Modal Container with spring physics */}
          <motion.dialog
            open
            ref={dialogRef}
            aria-labelledby="dialog-title"
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ type: "spring", ...springs.smooth }}
            className={`relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4 z-10 text-left m-0 ${className}`}
          >
            <div className="space-y-1">
              <h2 id="dialog-title" className="text-lg font-bold text-slate-900 tracking-tight">
                {title}
              </h2>
              {description && (
                <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">{description}</p>
              )}
            </div>

            <div className="py-1">{children}</div>

            {footer && (
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                {footer}
              </div>
            )}
          </motion.dialog>
        </div>
      )}
    </AnimatePresence>
  );
}
