import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMetrics } from "@/hooks/useMetrics";

const AGENT_COLORS: Record<string, string> = {
  spec_parser: "#00D2FF",
  coder: "#7B2FFF",
  test_writer: "#00FF88",
  test_runner: "#FF9500",
  reviewer: "#FF3366",
};

const tooltipStyle = {
  background: "rgba(6,13,26,0.95)",
  border: "1px solid rgba(0,210,255,0.3)",
  borderRadius: 10,
  fontFamily: "JetBrains Mono, monospace",
  fontSize: 11,
};

/** Tasks/minute over time, one coloured line per agent. */
export function ThroughputChart() {
  const { history } = useMetrics();
  const agents = Object.keys(AGENT_COLORS);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={history} margin={{ top: 10, right: 16, bottom: 0, left: -18 }}>
        <CartesianGrid stroke="rgba(0,210,255,0.08)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: "#4A7090", fontSize: 10 }} minTickGap={40} />
        <YAxis tick={{ fill: "#4A7090", fontSize: 10 }} />
        <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#4A7090" }} />
        <Legend wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
        {agents.map((a) => (
          <Line
            key={a}
            type="monotone"
            dataKey={a}
            name={a.replace(/_/g, " ")}
            stroke={AGENT_COLORS[a]}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
