/**
 * AgentStatus — renders each background agent as a floating, glowing orb.
 * Orb color encodes state: cyan pulse = running, green = done, red = error,
 * dim = idle. Orbs float with randomized phase offsets.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useMemo } from "react";
import { useZero } from "../lib/store";
import type { AgentSnapshot, AgentState } from "../lib/types";

const STATE_COLOR: Record<AgentState, string> = {
  running: "#00D2FF",
  done: "#00FF88",
  error: "#FF3366",
  idle: "#4A7090",
};

export default function AgentStatus({ compact = false }: { compact?: boolean }) {
  const { agents } = useZero();

  if (agents.length === 0) {
    return (
      <div className="flex h-full items-center justify-center font-mono text-xs text-text-dim">
        No active agents
      </div>
    );
  }

  return (
    <div className={`flex flex-wrap gap-6 ${compact ? "" : "p-4"}`}>
      <AnimatePresence>
        {agents.map((agent) => (
          <Orb key={agent.id} agent={agent} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function Orb({ agent }: { agent: AgentSnapshot }) {
  const color = STATE_COLOR[agent.state];
  const phase = useMemo(() => Math.random() * 2, []);
  const running = agent.state === "running";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{
        opacity: 1,
        scale: 1,
        y: [0, -6, 0],
      }}
      exit={{ opacity: 0, scale: 0.5 }}
      transition={{
        y: { duration: 3 + phase, repeat: Infinity, ease: "easeInOut", delay: phase },
        default: { duration: 0.4 },
      }}
      className="flex w-20 flex-col items-center gap-2"
      title={agent.error || agent.result || agent.input}
    >
      <div className="relative flex h-14 w-14 items-center justify-center">
        {running && (
          <motion.span
            className="absolute inset-0 rounded-full"
            style={{ border: `1px solid ${color}` }}
            animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
        <div
          className="h-10 w-10 rounded-full"
          style={{
            background: `radial-gradient(circle at 30% 30%, ${color}, transparent 75%)`,
            boxShadow: `0 0 ${running ? 24 : 12}px ${color}`,
          }}
        />
      </div>
      <span className="font-display text-[10px] uppercase text-text-primary">
        {agent.type}
      </span>
      <span className="font-mono text-[9px]" style={{ color }}>
        {agent.state}
      </span>
    </motion.div>
  );
}
