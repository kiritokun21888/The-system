import { AnimatePresence, motion } from "framer-motion";
import { useAgents } from "@/hooks/useAgents";
import { Badge } from "@/components/ui/badge";
import { STATUS_COLOR, fmtDuration } from "@/lib/utils";
import { NeonText } from "@/components/effects/BeamCard";

/** Right-panel live task feed — cards slide in from the right, exit left. */
export function TaskFeed() {
  const { tasks } = useAgents();

  return (
    <div className="glass flex h-full min-h-0 flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <NeonText className="text-sm blink-cursor">LIVE FEED</NeonText>
        <span className="text-[10px] font-mono text-[var(--text-dim)]">{tasks.length} active</span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {tasks.map((t) => {
            const color = STATUS_COLOR[t.status] ?? STATUS_COLOR.queued;
            const failed = t.status === "escalated" || t.status === "aborted";
            const loops = Object.values(t.loops).reduce((a, b) => a + b, 0);
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, x: 60 }}
                animate={{
                  opacity: 1,
                  x: 0,
                  boxShadow: failed
                    ? ["0 0 0px #FF3366", "0 0 24px #FF3366", "0 0 8px #FF3366"]
                    : "0 0 0px transparent",
                }}
                exit={{ opacity: 0, x: -60 }}
                transition={{ type: "spring", stiffness: 260, damping: 26 }}
                className="glass-tight p-2.5"
                style={{ borderColor: `${color}55` }}
              >
                <div className="mb-1.5 flex items-start justify-between gap-2">
                  <span className="line-clamp-2 text-[11px] leading-snug text-[var(--text-primary)]">
                    {t.prompt}
                  </span>
                  <Badge color={color}>{t.status}</Badge>
                </div>
                <div className="flex items-center justify-between text-[9px] font-mono text-[var(--text-dim)]">
                  <span>{t.stage ? `▸ ${t.stage.replace(/_/g, " ")}` : "—"}</span>
                  <span className="flex gap-2">
                    {loops > 0 && <span style={{ color: "#FF9500" }}>↻ {loops}</span>}
                    <span>P{t.priority}</span>
                    <span>{fmtDuration(t.elapsed)}</span>
                  </span>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
