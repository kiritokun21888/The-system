import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";
import { FileSearch, Code2, FlaskConical, Play, ShieldCheck, Cpu } from "lucide-react";
import { STATUS_COLOR } from "@/lib/utils";

const ICONS: Record<string, typeof Cpu> = {
  parser: FileSearch,
  code: Code2,
  tests: FlaskConical,
  play: Play,
  shield: ShieldCheck,
  cpu: Cpu,
};

export interface AgentNodeData {
  label: string;
  icon: string;
  status: string;
  active: number;
  processed: number;
  [key: string]: unknown;
}

/** Custom React Flow node: a glowing agent core that pulses when active. */
function AgentNodeImpl({ data }: { data: AgentNodeData }) {
  const color = STATUS_COLOR[data.status] ?? STATUS_COLOR.idle;
  const Icon = ICONS[data.icon] ?? Cpu;
  const active = data.status === "running";

  return (
    <div className="relative flex flex-col items-center" style={{ width: 96 }}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-[var(--accent-cyan)]" />
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-[var(--accent-cyan)]" />

      {/* pulsing outer ring */}
      {active && (
        <motion.div
          className="absolute top-0 h-[72px] w-[72px] rounded-full"
          style={{ border: `2px solid ${color}` }}
          initial={{ scale: 0.8, opacity: 0.7 }}
          animate={{ scale: [0.8, 1.6], opacity: [0.7, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
        />
      )}

      <motion.div
        className="relative flex h-[72px] w-[72px] items-center justify-center rounded-full"
        style={{
          background: `radial-gradient(circle at 50% 35%, ${color}33, rgba(6,13,26,0.9))`,
          border: `2px solid ${color}`,
          boxShadow: active ? `0 0 28px ${color}88` : `0 0 12px ${color}44`,
        }}
        animate={active ? { scale: [1, 1.06, 1] } : { scale: 1 }}
        transition={{ duration: 1.2, repeat: active ? Infinity : 0 }}
      >
        <Icon size={26} color={color} strokeWidth={1.6} />
        {/* live task-count badge */}
        <div
          className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-bold font-mono"
          style={{ background: color, color: "#02040A", boxShadow: `0 0 10px ${color}` }}
        >
          {data.processed}
        </div>
      </motion.div>

      <div className="mt-2 text-center">
        <div className="font-display text-[10px] uppercase tracking-wider text-[var(--text-primary)]">
          {data.label.replace(/_/g, " ")}
        </div>
        <div className="text-[9px] font-mono" style={{ color }}>
          {data.status}
        </div>
      </div>
    </div>
  );
}

export const AgentNode = memo(AgentNodeImpl);
