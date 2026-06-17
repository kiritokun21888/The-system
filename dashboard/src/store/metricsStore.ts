import { create } from "zustand";
import type { MetricsSnapshot } from "@/lib/types";

export interface ThroughputPoint {
  t: number; // epoch ms
  label: string;
  [agent: string]: number | string;
}

interface MetricsState {
  current: MetricsSnapshot | null;
  history: ThroughputPoint[]; // last ~60 samples, one line per agent
  costHistory: { t: number; cost: number }[];
  setMetrics: (m: MetricsSnapshot) => void;
}

const MAX_POINTS = 60;

/** Metrics + rolling time-series history for the charts. */
export const useMetricsStore = create<MetricsState>((set) => ({
  current: null,
  history: [],
  costHistory: [],
  setMetrics: (m) =>
    set((s) => {
      const t = Date.now();
      const point: ThroughputPoint = { t, label: new Date(t).toLocaleTimeString().slice(0, 8) };
      for (const [name, a] of Object.entries(m.agents)) {
        point[name] = Number(a.per_minute.toFixed(1));
      }
      const history = [...s.history, point].slice(-MAX_POINTS);
      const costHistory = [...s.costHistory, { t, cost: m.total_cost_usd }].slice(-MAX_POINTS);
      return { current: m, history, costHistory };
    }),
}));
