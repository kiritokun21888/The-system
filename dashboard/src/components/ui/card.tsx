import * as React from "react";
import { cn } from "@/lib/utils";

/** Glassmorphism panel container. Set `active` for the traveling border light. */
export function Card({
  className,
  active,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { active?: boolean }) {
  return (
    <div className={cn("glass p-4", active && "border-travel", className)} {...props} />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mb-3 flex items-center justify-between", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "font-display text-xs uppercase tracking-widest text-[var(--text-dim)]",
        className
      )}
      {...props}
    />
  );
}
