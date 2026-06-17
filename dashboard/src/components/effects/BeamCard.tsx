import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * Aceternity-style "beam" KPI card — a bright beam sweeps across the top edge
 * behind glassmorphism. Used for the large KPI tiles.
 */
export function BeamCard({
  children,
  className,
  color = "#00D2FF",
}: {
  children: ReactNode;
  className?: string;
  color?: string;
}) {
  return (
    <div className={cn("glass relative overflow-hidden p-5", className)}>
      <motion.div
        aria-hidden
        className="absolute -top-px left-0 h-px w-1/2"
        style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }}
        animate={{ x: ["-50%", "200%"] }}
        transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
      />
      <div
        aria-hidden
        className="absolute -top-16 left-1/2 h-32 w-32 -translate-x-1/2 rounded-full blur-3xl"
        style={{ background: `${color}22` }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

/** Neon Orbitron heading. */
export function NeonText({
  children,
  className,
  color = "#00D2FF",
}: {
  children: ReactNode;
  className?: string;
  color?: string;
}) {
  return (
    <span
      className={cn("font-display", className)}
      style={{ color, textShadow: `0 0 12px ${color}aa` }}
    >
      {children}
    </span>
  );
}
