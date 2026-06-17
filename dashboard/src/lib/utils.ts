import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names, resolving conflicts (shadcn convention). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format a small USD value with sensible precision. */
export function fmtUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(5)}`;
  return `$${n.toFixed(2)}`;
}

/** Format seconds as a compact human duration. */
export function fmtDuration(s: number): string {
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

/** Clamp a number to a range. */
export function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

/** Accent color for a status string. */
export const STATUS_COLOR: Record<string, string> = {
  running: "#00D2FF",
  done: "#00FF88",
  completed: "#00FF88",
  idle: "#4A7090",
  error: "#FF3366",
  failure: "#FF3366",
  escalated: "#FF9500",
  aborted: "#FF3366",
  queued: "#7B2FFF",
};
