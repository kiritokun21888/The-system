import { useMetricsStore } from "@/store/metricsStore";

/** Convenience selector for metrics + time-series history. */
export function useMetrics() {
  const current = useMetricsStore((s) => s.current);
  const history = useMetricsStore((s) => s.history);
  const costHistory = useMetricsStore((s) => s.costHistory);
  return { current, history, costHistory };
}
