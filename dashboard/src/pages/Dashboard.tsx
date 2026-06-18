import { motion } from "framer-motion";
import { StatusPanel } from "@/components/panels/StatusPanel";
import { AgentGraph } from "@/components/panels/AgentGraph";
import { TaskFeed } from "@/components/panels/TaskFeed";
import { Core3D } from "@/components/Core3D";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useAgents } from "@/hooks/useAgents";

/** Main dashboard: left status (30%), center live graph (40%), right feed (30%). */
export function Dashboard() {
  const { agents } = useAgents();
  const anyActive = agents.some((a) => a.status === "running");

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="grid h-full min-h-0 gap-3"
      style={{ gridTemplateColumns: "30% 1fr 30%" }}
    >
      <div className="min-h-0">
        <StatusPanel />
      </div>

      <div className="relative min-h-0">
        <div className="absolute right-3 top-3 z-10 h-28 w-28 opacity-90">
          <ErrorBoundary silent label="core3d">
            <Core3D active={anyActive} />
          </ErrorBoundary>
        </div>
        <div className="pointer-events-none absolute left-4 top-4 z-10">
          <div className="font-display text-sm font-bold tracking-widest text-[var(--accent-cyan)] glow-cyan">
            AGENT MESH
          </div>
          <div className="text-[10px] font-mono text-[var(--text-dim)]">live pipeline topology</div>
        </div>
        <AgentGraph />
      </div>

      <div className="min-h-0">
        <TaskFeed />
      </div>
    </motion.div>
  );
}
