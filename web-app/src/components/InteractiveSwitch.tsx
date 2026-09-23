import { motion } from "motion/react";
import type React from "react";
import { springs } from "../lib/springs";

interface InteractiveSwitchProps {
  active: boolean;
  onToggle: () => void;
  activeLabel: string;
  inactiveLabel: string;
  className?: string;
}

export function InteractiveSwitch({
  active,
  onToggle,
  activeLabel,
  inactiveLabel,
  className = "",
}: InteractiveSwitchProps): React.JSX.Element {
  return (
    <motion.button
      type="button"
      onClick={onToggle}
      whileTap={{ scale: 0.96 }}
      transition={{ type: "spring", ...springs.snappy }}
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${
        active
          ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100 focus-visible:ring-emerald-500"
          : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200 focus-visible:ring-slate-400"
      } ${className}`}
      aria-pressed={active}
    >
      <span
        className={`w-2 h-2 rounded-full transition-colors ${
          active ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
        }`}
      />
      <span>{active ? activeLabel : inactiveLabel}</span>
    </motion.button>
  );
}
