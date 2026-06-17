import { motion } from "framer-motion";
import { useMetrics } from "@/hooks/useMetrics";
import { useUiStore } from "@/store/uiStore";
import { StatCard } from "./StatCard";
import { AgentRoster } from "./AgentRoster";
import { NeonText } from "@/components/effects/BeamCard";
import { fmtUsd } from "@/lib/utils";

/** Left dashboard column: system status, KPI stat grid, agent roster. */
export function StatusPanel() {
  const { current, history } = useMetrics();
  const connected = useUiStore((s) => s.connected);
  const usingMock = useUiStore((s) => s.usingMock);

  // Build small sparkline series from rolling history.
  const totalThroughput = history.map((p) =>
    Object.entries(p)
      .filter(([k]) => k !== "t" && k !== "label")
      .reduce((a, [, v]) => a + (typeof v === "number" ? v : 0), 0)
  );
  const queueSpark = history.map((_, i) => (current ? current.queue_depth : 0) + (i % 3));
  const latencySpark = history.map((p) => Number(p["coder"] ?? 0));

  const m = current;
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {/* status header */}
      <div className="glass border-travel flex items-center gap-3 p-4">
        <span
          className="pulse-dot h-3 w-3 rounded-full"
          style={{ background: connected ? "#00FF88" : "#00D2FF", color: connected ? "#00FF88" : "#00D2FF" }}
        />
        <div>
          <NeonText color={connected ? "#00FF88" : "#00D2FF"} className="text-lg font-bold">
            SYSTEM ONLINE
          </NeonText>
          <div className="text-[10px] font-mono text-[var(--text-dim)]">
            {usingMock ? "simulation mode · mock feed" : "live · ws://localhost:8000"}
          </div>
        </div>
      </div>

      {/* stat grid */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Tasks Complete" value={m?.tasks_completed ?? 0} color="#00FF88" spark={totalThroughput} />
        <StatCard label="Active Agents" value={m ? Object.values(m.agents).filter((a) => a.per_minute > 0).length : 0} color="#00D2FF" spark={totalThroughput} />
        <StatCard label="Queue Depth" value={m?.queue_depth ?? 0} color="#7B2FFF" spark={queueSpark} />
        <StatCard label="Avg Latency" value={m ? (avgLatency(m) * 1000).toFixed(0) : 0} unit="ms" color="#FF9500" spark={latencySpark} />
      </div>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <StatCard label="Total Session Cost" value={fmtUsd(m?.total_cost_usd ?? 0)} color="#FF3366" spark={totalThroughput} />
      </motion.div>

      <AgentRoster />
    </div>
  );
}

function avgLatency(m: { agents: Record<string, { avg_latency: number }> }): number {
  const vals = Object.values(m.agents).map((a) => a.avg_latency);
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
}
