import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAgents } from "@/hooks/useAgents";

const BUCKETS = [
  { label: "<0.5s", max: 0.5 },
  { label: "0.5-1s", max: 1 },
  { label: "1-2s", max: 2 },
  { label: "2-4s", max: 4 },
  { label: "4s+", max: Infinity },
];
const COLORS = ["#00FF88", "#00D2FF", "#7B2FFF", "#FF9500", "#FF3366"];

const tooltipStyle = {
  background: "rgba(6,13,26,0.95)",
  border: "1px solid rgba(0,210,255,0.3)",
  borderRadius: 10,
  fontFamily: "JetBrains Mono, monospace",
  fontSize: 11,
};

/** Distribution of task elapsed-time across buckets. */
export function DurationBar() {
  const { tasks } = useAgents();
  const counts = BUCKETS.map((b) => ({ label: b.label, count: 0 }));
  for (const t of tasks) {
    const idx = BUCKETS.findIndex((b) => t.elapsed < b.max);
    if (idx >= 0) counts[idx].count++;
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={counts} margin={{ top: 10, right: 16, bottom: 0, left: -22 }}>
        <CartesianGrid stroke="rgba(0,210,255,0.08)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: "#4A7090", fontSize: 10 }} />
        <YAxis allowDecimals={false} tick={{ fill: "#4A7090", fontSize: 10 }} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(0,210,255,0.06)" }} />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {counts.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
