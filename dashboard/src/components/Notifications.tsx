import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, X, Info, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useAssistantStore } from "@/store/assistantStore";
import { cn } from "@/lib/utils";

const LEVEL = {
  info: { color: "#00D2FF", Icon: Info },
  warning: { color: "#FF9500", Icon: AlertTriangle },
  success: { color: "#00FF88", Icon: CheckCircle2 },
  error: { color: "#FF3366", Icon: AlertTriangle },
} as const;

/** Slide-in toast notifications (top-right) + a bell history panel. */
export function Notifications() {
  const { notifications, dismiss } = useAssistantStore();
  const [openHistory, setOpenHistory] = useState(false);
  const toasts = notifications.slice(0, 4);

  return (
    <>
      {/* bell */}
      <button
        onClick={() => setOpenHistory((o) => !o)}
        className="glass relative flex h-9 w-9 items-center justify-center rounded-lg text-[var(--accent-cyan)]"
        title="Notifications"
      >
        <Bell size={16} />
        {notifications.length > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent-red)] px-1 text-[9px] font-bold text-white">
            {notifications.length}
          </span>
        )}
      </button>

      {/* toasts */}
      <div className="pointer-events-none fixed right-4 top-16 z-50 flex w-80 flex-col gap-2">
        <AnimatePresence>
          {toasts.map((n) => {
            const meta = LEVEL[(n.level as keyof typeof LEVEL)] ?? LEVEL.info;
            return (
              <motion.div
                key={n.id}
                layout
                initial={{ opacity: 0, x: 80 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 80 }}
                className="glass pointer-events-auto flex items-start gap-2 p-3"
                style={{ borderColor: `${meta.color}55` }}
              >
                <meta.Icon size={16} color={meta.color} className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-[var(--text-primary)]">{n.title}</div>
                  {n.body && <div className="text-[11px] text-[var(--text-dim)]">{n.body}</div>}
                  <div className="mt-0.5 text-[9px] font-mono uppercase tracking-wider" style={{ color: meta.color }}>
                    {n.agent}
                  </div>
                </div>
                <button onClick={() => dismiss(n.id)} className="text-[var(--text-dim)] hover:text-[var(--accent-red)]">
                  <X size={14} />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* history drawer */}
      <AnimatePresence>
        {openHistory && (
          <motion.div
            initial={{ opacity: 0, x: 60 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 60 }}
            className="glass fixed right-4 top-28 bottom-4 z-50 flex w-80 flex-col p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="font-display text-xs uppercase tracking-widest text-[var(--accent-cyan)]">
                Notifications
              </span>
              <button onClick={() => setOpenHistory(false)} className="text-[var(--text-dim)]">
                <X size={16} />
              </button>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
              {notifications.length === 0 && (
                <div className="text-[11px] text-[var(--text-dim)]">No notifications yet.</div>
              )}
              {notifications.map((n) => {
                const meta = LEVEL[(n.level as keyof typeof LEVEL)] ?? LEVEL.info;
                return (
                  <div key={n.id} className="glass-tight p-2">
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-primary)]">
                      <meta.Icon size={12} color={meta.color} /> {n.title}
                    </div>
                    {n.body && <div className="mt-0.5 text-[10px] text-[var(--text-dim)]">{n.body}</div>}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/** Bottom status strip: real CPU/RAM/disk + uptime + vault size. */
export function StatsBar() {
  const { stats, uptime, vaultBytes, connected, agents } = useAssistantStore();
  const activeAgents = agents.filter((a) => a.status === "running" || a.status === "active").length;
  const fmtUp = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h ? `${h}h ${m}m` : `${m}m`;
  };
  const bar = (label: string, val: number, color: string) => (
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] uppercase tracking-wider text-[var(--text-dim)]">{label}</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[rgba(0,210,255,0.1)]">
        <div className="h-full rounded-full transition-all" style={{ width: `${val}%`, background: color }} />
      </div>
      <span className="w-8 font-mono text-[10px]" style={{ color }}>
        {val.toFixed(0)}%
      </span>
    </div>
  );

  return (
    <div className="glass flex items-center justify-between rounded-none border-x-0 border-b-0 px-4 py-1.5 text-[10px]">
      <div className="flex items-center gap-4">
        <span
          className="h-2 w-2 rounded-full pulse-dot"
          style={{ background: connected ? "#00FF88" : "#FF3366", color: connected ? "#00FF88" : "#FF3366" }}
        />
        <span className="font-display tracking-wider" style={{ color: connected ? "#00FF88" : "#FF3366" }}>
          {connected ? "ENGINE LIVE" : "ENGINE OFFLINE"}
        </span>
        {stats && (
          <>
            {bar("CPU", stats.cpu, "#00D2FF")}
            {bar("RAM", stats.ram, "#7B2FFF")}
            {bar("DISK", stats.disk, "#FF9500")}
          </>
        )}
      </div>
      <div className="flex items-center gap-4 font-mono text-[var(--text-dim)]">
        <span>{activeAgents} agents active</span>
        <span>vault {(vaultBytes / 1024).toFixed(0)} KB</span>
        <span>up {fmtUp(uptime)}</span>
      </div>
    </div>
  );
}
