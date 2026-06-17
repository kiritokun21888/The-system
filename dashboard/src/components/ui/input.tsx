import * as React from "react";
import { cn } from "@/lib/utils";

/** Glassmorphic text input. */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-9 w-full rounded-lg border border-[var(--border-glow)] bg-[rgba(2,4,10,0.6)] px-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-dim)] outline-none transition-all focus:border-[var(--accent-cyan)] focus:shadow-[0_0_14px_rgba(0,210,255,0.25)]",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

/** Glassmorphic textarea. */
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-[var(--border-glow)] bg-[rgba(2,4,10,0.6)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-dim)] outline-none transition-all focus:border-[var(--accent-cyan)] focus:shadow-[0_0_14px_rgba(0,210,255,0.25)]",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
