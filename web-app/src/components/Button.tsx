import type { HTMLMotionProps } from "motion/react";
import { motion } from "motion/react";
import type React from "react";
import { springs } from "../lib/springs";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "link";
export type ButtonSize = "xs" | "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends Omit<HTMLMotionProps<"button">, "ref"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs focus-visible:ring-indigo-500",
  secondary:
    "bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-xs focus-visible:ring-slate-400",
  ghost:
    "bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900 focus-visible:ring-slate-400",
  destructive:
    "bg-white hover:bg-rose-50 text-rose-600 border border-rose-200 shadow-xs focus-visible:ring-rose-500",
  link: "bg-transparent text-indigo-600 hover:text-indigo-700 underline-offset-4 hover:underline focus-visible:ring-indigo-400 p-0 h-auto",
};

const sizeClasses: Record<ButtonSize, string> = {
  xs: "px-2.5 py-1 text-xs gap-1 rounded-md",
  sm: "px-3 py-1.5 text-xs gap-1.5 rounded-lg",
  md: "px-4 py-2 text-sm gap-2 rounded-lg",
  lg: "px-5 py-2.5 text-base gap-2.5 rounded-xl",
  icon: "p-2 w-8 h-8 rounded-lg shrink-0",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  disabled = false,
  children,
  onClick,
  type = "button",
  ...props
}: ButtonProps): React.JSX.Element {
  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ type: "spring", ...springs.snappy }}
      className={`inline-flex items-center justify-center font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
}
