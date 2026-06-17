import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "ghost" | "outline" | "danger" | "success";
type Size = "sm" | "md" | "icon";

const VARIANTS: Record<Variant, string> = {
  default:
    "bg-[rgba(0,210,255,0.12)] text-[var(--accent-cyan)] border border-[var(--border-glow)] hover:bg-[rgba(0,210,255,0.22)] hover:shadow-[0_0_18px_rgba(0,210,255,0.35)]",
  ghost: "text-[var(--text-dim)] hover:text-[var(--text-primary)] hover:bg-[rgba(0,210,255,0.06)]",
  outline:
    "border border-[var(--border-glow)] text-[var(--text-primary)] hover:border-[var(--accent-cyan)] hover:shadow-[0_0_14px_rgba(0,210,255,0.25)]",
  danger:
    "bg-[rgba(255,51,102,0.12)] text-[var(--accent-red)] border border-[rgba(255,51,102,0.3)] hover:bg-[rgba(255,51,102,0.22)]",
  success:
    "bg-[rgba(0,255,136,0.1)] text-[var(--accent-green)] border border-[rgba(0,255,136,0.3)] hover:bg-[rgba(0,255,136,0.2)]",
};
const SIZES: Record<Size, string> = {
  sm: "h-7 px-3 text-xs",
  md: "h-9 px-4 text-sm",
  icon: "h-9 w-9",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

/** Glassmorphic neon button (shadcn-style API). */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 disabled:opacity-40 disabled:pointer-events-none active:scale-95",
        VARIANTS[variant],
        SIZES[size],
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
