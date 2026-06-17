import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Pause, Play, RotateCcw, Settings2, Terminal } from "lucide-react";
import { Card3D } from "@/components/effects/Card3D";
import { Sparkline } from "@/components/charts/Sparkline";
import { Button } from "@/components/ui/button";
import { NeonText } from "@/components/effects/BeamCard";
import { useAgents } from "@/hooks/useAgents";
import { useMetrics } from "@/hooks/useMetrics";
import { STATUS_COLOR } from "@/lib/utils";
import type { LogEntry } from "@/lib/types";

const LOG_COLOR: Record<string, string> = {
  INFO: "#00D2FF",
  WARNING: "#FF9500",
  ERROR: "#FF3366",
  DEBUG: "#4A7090",
};

/** Agent control grid — one rich card per agent. */
export function AgentControl() {
  const { agents, logsByAgent } = useAgents();
  const { history, current } = useMetrics();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-full min-h-0 overflow-y-auto pr-1"
    >
      <NeonText className="text-xl font-bold">AGENT CONTROL</NeonText>
      <div className="mb-4 text-[10px] font-mono text-[var(--text-dim)]">
        per-unit telemetry & controls
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        {agents.map((a) => {
          const color = STATUS_COLOR[a.status] ?? STATUS_COLOR.idle;
          const spark = history.map((p) => Number(p[a.name] ?? 0));
          const cacheRate =
            current?.agents[a.name] && current.agents[a.name].processed
              ? (current.agents[a.name].cache_hits / current.agents[a.name].processed) * 100
              : 0;
          return (
            <AgentCard
              key={a.name}
              name={a.name}
              status={a.status}
              color={color}
              perMin={a.per_minute}
              avgLatency={a.avg_latency}
              errorRate={a.error_rate}
              cacheRate={cacheRate}
              spark={spark}
              logs={logsByAgent[a.name] ?? []}
            />
          );
        })}
      </div>
    </motion.div>
  );
}

function AgentCard({
  name, status, color, perMin, avgLatency, errorRate, cacheRate, spark, logs,
}: {
  name: string;
  status: string;
  color: string;
  perMin: number;
  avgLatency: number;
  errorRate: number;
  cacheRate: number;
  spark: number[];
  logs: LogEntry[];
}) {
  const [paused, setPaused] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  return (
    <Card3D>
      <div className="mb-3 flex items-center justify-between">
        <NeonText color={color} className="text-sm font-bold">
          {name.replace(/_/g, " ").toUpperCase()}
        </NeonText>
        <motion.span
          className="h-7 w-7 rounded-full"
          style={{ border: `2px solid ${color}`, boxShadow: `0 0 12px ${color}66` }}
          animate={status === "running" ? { rotate: 360 } : {}}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <Metric label="tasks/min" value={perMin.toFixed(1)} color={color} />
        <Metric label="avg latency" value={`${(avgLatency * 1000).toFixed(0)}ms`} color="#00D2FF" />
        <Metric label="error rate" value={`${(errorRate * 100).toFixed(1)}%`} color={errorRate > 0.3 ? "#FF3366" : "#00FF88"} />
        <Metric label="cache hit" value={`${cacheRate.toFixed(0)}%`} color="#7B2FFF" />
      </div>

      <div className="mt-3 h-12">
        <Sparkline data={spark.length > 1 ? spark : [0, 0]} color={color} />
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Button size="sm" variant={paused ? "success" : "outline"} onClick={() => setPaused((p) => !p)}>
          {paused ? <Play size={13} /> : <Pause size={13} />} {paused ? "Resume" : "Pause"}
        </Button>
        <Button size="sm" variant="ghost">
          <RotateCcw size={13} /> Restart
        </Button>
        <Button size="sm" variant="ghost">
          <Settings2 size={13} /> Config
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowLogs((s) => !s)}>
          <Terminal size={13} /> Logs
        </Button>
      </div>

      <AnimatePresence>
        {showLogs && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="mt-3 overflow-hidden"
          >
            <div className="max-h-40 overflow-y-auto rounded-lg bg-[rgba(2,4,10,0.7)] p-2 font-mono text-[10px]">
              {logs.length === 0 && <div className="text-[var(--text-dim)]">no recent log entries</div>}
              {logs.map((l, i) => (
                <div key={i} className="flex gap-2 py-0.5">
                  <span style={{ color: LOG_COLOR[l.level] ?? "#4A7090" }}>{l.level[0]}</span>
                  <span className="text-[var(--text-dim)]">{l.ts}</span>
                  <span className="truncate text-[var(--text-primary)]">{l.msg}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card3D>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="glass-tight px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-[var(--text-dim)]">{label}</div>
      <div className="font-mono text-sm" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
