import { motion } from "framer-motion";
import { KpiCard } from "@/components/charts/KpiCard";
import { ThroughputChart } from "@/components/charts/ThroughputChart";
import { DurationBar } from "@/components/charts/DurationBar";
import { ArcDiagram } from "@/components/charts/ArcDiagram";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useMetrics } from "@/hooks/useMetrics";
import { fmtUsd } from "@/lib/utils";
import { NeonText } from "@/components/effects/BeamCard";

const fade = (i: number) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: i * 0.06, duration: 0.4 },
});

/** Performance & analytics center. */
export function Performance() {
  const { current, costHistory } = useMetrics();
  const m = current;
  const totalProcessed = m ? Object.values(m.agents).reduce((a, b) => a + b.processed, 0) : 0;
  const totalTokens = m
    ? Object.values(m.agents).reduce((a, b) => a + b.tokens_in + b.tokens_out, 0)
    : 0;
  const costSpark = costHistory.map((c) => c.cost);
  const projectedHourly = m && m.uptime_seconds > 0
    ? (m.total_cost_usd / m.uptime_seconds) * 3600
    : 0;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto pr-1">
      <NeonText className="text-xl font-bold">PERFORMANCE CENTER</NeonText>

      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4">
        <motion.div {...fade(0)}>
          <KpiCard label="Tasks Completed" value={m?.tasks_completed ?? 0} color="#00FF88" spark={costSpark} />
        </motion.div>
        <motion.div {...fade(1)}>
          <KpiCard label="Agent Invocations" value={totalProcessed} color="#00D2FF" spark={costSpark} />
        </motion.div>
        <motion.div {...fade(2)}>
          <KpiCard label="Tokens Processed" value={fmtTokens(totalTokens)} color="#7B2FFF" spark={costSpark} />
        </motion.div>
        <motion.div {...fade(3)}>
          <KpiCard label="Escalations" value={m?.tasks_escalated ?? 0} color="#FF9500" spark={costSpark} />
        </motion.div>
      </div>

      {/* charts */}
      <div className="grid grid-cols-3 gap-4" style={{ minHeight: 280 }}>
        <Card className="col-span-2 flex flex-col">
          <CardHeader>
            <CardTitle>Throughput · tasks/min per agent</CardTitle>
          </CardHeader>
          <div className="min-h-0 flex-1">
            <ThroughputChart />
          </div>
        </Card>
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Agent Flow Volume</CardTitle>
          </CardHeader>
          <div className="min-h-0 flex-1">
            <ArcDiagram />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-4" style={{ minHeight: 240 }}>
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Task Duration Distribution</CardTitle>
          </CardHeader>
          <div className="min-h-0 flex-1">
            <DurationBar />
          </div>
        </Card>

        {/* cost table */}
        <Card className="col-span-2 flex flex-col">
          <CardHeader>
            <CardTitle>Cost Tracking</CardTitle>
            <span className="font-mono text-[10px] text-[var(--text-dim)]">
              projected ~{fmtUsd(projectedHourly)}/hr
            </span>
          </CardHeader>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="text-[var(--text-dim)]">
                <tr className="border-b border-[var(--border-glow)]">
                  <th className="py-1.5">agent</th>
                  <th>processed</th>
                  <th>tokens in/out</th>
                  <th>cache</th>
                  <th className="text-right">cost</th>
                </tr>
              </thead>
              <tbody>
                {m &&
                  Object.entries(m.agents).map(([name, a]) => (
                    <tr key={name} className="border-b border-[rgba(0,210,255,0.06)]">
                      <td className="py-1.5 text-[var(--text-primary)]">{name.replace(/_/g, " ")}</td>
                      <td className="text-[var(--accent-cyan)]">{a.processed}</td>
                      <td className="text-[var(--text-dim)]">
                        {fmtTokens(a.tokens_in)}/{fmtTokens(a.tokens_out)}
                      </td>
                      <td className="text-[var(--accent-violet)]">{a.cache_hits}</td>
                      <td className="text-right text-[var(--accent-green)]">{fmtUsd(a.cost_usd)}</td>
                    </tr>
                  ))}
                <tr>
                  <td className="py-2 font-bold text-[var(--text-primary)]">TOTAL</td>
                  <td className="text-[var(--accent-cyan)]">{totalProcessed}</td>
                  <td className="text-[var(--text-dim)]">{fmtTokens(totalTokens)}</td>
                  <td />
                  <td className="text-right font-bold text-[var(--accent-green)]">
                    {fmtUsd(m?.total_cost_usd ?? 0)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </motion.div>
  );
}

function fmtTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}
