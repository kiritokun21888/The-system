import { AnimatePresence, motion } from "framer-motion";
import { useAgents } from "@/hooks/useAgents";
import { STATUS_COLOR } from "@/lib/utils";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

/** Live agent roster — animated rows reorder by activity. */
export function AgentRoster() {
  const { agents } = useAgents();
  // Active agents float to the top.
  const sorted = [...agents].sort((a, b) => Number(b.active) - Number(a.active));

  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader>
        <CardTitle>Agent Roster</CardTitle>
        <span className="text-[10px] font-mono text-[var(--text-dim)]">{agents.length} units</span>
      </CardHeader>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto pr-1">
        <AnimatePresence>
          {sorted.map((a) => {
            const color = STATUS_COLOR[a.status] ?? STATUS_COLOR.idle;
            return (
              <motion.div
                key={a.name}
                layout
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ type: "spring", stiffness: 300, damping: 28 }}
                className="glass-tight flex items-center gap-3 p-2.5"
              >
                <span
                  className="pulse-dot h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: color, color }}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-display text-[11px] uppercase tracking-wide text-[var(--text-primary)]">
                    {a.name.replace(/_/g, " ")}
                  </div>
                  <div className="truncate text-[10px] text-[var(--text-dim)]">
                    {a.current_task || "awaiting dispatch"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm" style={{ color }}>
                    {a.processed}
                  </div>
                  <div className="text-[9px] text-[var(--text-dim)]">tasks</div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Card>
  );
}
