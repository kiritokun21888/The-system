import * as React from "react";
import { cn } from "@/lib/utils";

/** A glowing pill badge. Pass a hex `color` to tint it. */
export function Badge({
  className,
  color = "#00D2FF",
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { color?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        className
      )}
      style={{
        color,
        background: `${color}1a`,
        border: `1px solid ${color}55`,
        boxShadow: `0 0 10px ${color}33`,
      }}
      {...props}
    >
      {children}
    </span>
  );
}
