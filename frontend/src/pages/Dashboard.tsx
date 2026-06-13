/**
 * Dashboard — the main brain view. The neural network fills the background;
 * floating glass panels show system vitals, active agents and top tasks, with
 * the command bar anchored at the bottom.
 */
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import AgentStatus from "../components/AgentStatus";

const panelIn = {
  initial: { opacity: 0, y: 40 },
  animate: { opacity: 1, y: 0 },
  transition: { type: "spring", stiffness: 120, damping: 20 },
};

export default function Dashboard() {
  const { tasks, brainEnabled, online } = useZero();
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const tick = () => api.systemStats().then(setStats).catch(() => {});
    tick();
    const id = setInterval(tick, 4000);
    return () => clearInterval(id);
  }, []);

  const topTasks = [...tasks]
    .filter((t) => t.status !== "done")
    .sort((a, b) => b.priority - a.priority)
    .slice(0, 5);

  return (
    <div className="relative z-10 grid h-full grid-cols-12 gap-4 p-6">
      <motion.div {...panelIn} className="panel col-span-3 flex flex-col gap-4 p-5">
        <h2 className="font-display text-sm text-primary">SYSTEM VITALS</h2>
        {stats?.ok ? (
          <div className="space-y-3">
            <Vital label="CPU" value={stats.cpu_percent} suffix="%" />
            <Vital label="MEMORY" value={stats.memory.percent} suffix="%" />
            <Vital label="DISK" value={stats.disk.percent} suffix="%" />
            {stats.battery && (
              <Vital label="BATTERY" value={stats.battery.percent} suffix="%" />
            )}
          </div>
        ) : (
          <div className="font-mono text-xs text-text-dim">
            {online ? "reading sensors…" : "backend offline"}
          </div>
        )}
        <div className="mt-auto flex items-center gap-2 font-mono text-[10px] text-text-dim">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{
              background: brainEnabled
                ? "var(--accent-success)"
                : "var(--accent-warm)",
            }}
          />
          {brainEnabled ? "BRAIN ONLINE" : "BRAIN OFFLINE MODE"}
        </div>
      </motion.div>

      <div className="col-span-6" />

      <motion.div
        {...panelIn}
        transition={{ ...panelIn.transition, delay: 0.1 }}
        className="panel col-span-3 flex flex-col gap-3 p-5"
      >
        <h2 className="font-display text-sm text-primary">PRIORITY QUEUE</h2>
        <div className="flex flex-col gap-2 overflow-y-auto">
          {topTasks.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-2 rounded-lg border border-border-glow p-2"
            >
              <span className="font-mono text-xs text-primary">P{t.priority}</span>
              <span className="truncate text-sm text-text-primary">{t.title}</span>
            </div>
          ))}
          {topTasks.length === 0 && (
            <div className="font-mono text-xs text-text-dim">Queue clear.</div>
          )}
        </div>
      </motion.div>

      <motion.div
        {...panelIn}
        transition={{ ...panelIn.transition, delay: 0.2 }}
        className="panel col-span-12 self-end p-4"
      >
        <h2 className="mb-2 font-display text-sm text-primary">ACTIVE AGENTS</h2>
        <AgentStatus compact />
      </motion.div>
    </div>
  );
}

function Vital({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number;
  suffix: string;
}) {
  return (
    <div>
      <div className="flex justify-between font-mono text-xs">
        <span className="text-text-dim">{label}</span>
        <span className="text-text-primary">
          {Math.round(value)}
          {suffix}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded bg-surface">
        <motion.div
          className="h-full rounded"
          style={{
            background:
              value > 85 ? "var(--accent-danger)" : "var(--accent-primary)",
          }}
          animate={{ width: `${Math.min(100, value)}%` }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.32, 1] }}
        />
      </div>
    </div>
  );
}
