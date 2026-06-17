import { useAgentStore } from "@/store/agentStore";

/** Convenience selector for agent-related live state. */
export function useAgents() {
  const agents = useAgentStore((s) => s.agents);
  const tasks = useAgentStore((s) => s.tasks);
  const edges = useAgentStore((s) => s.edges);
  const pipeline = useAgentStore((s) => s.pipeline);
  const logs = useAgentStore((s) => s.logs);
  const logsByAgent = useAgentStore((s) => s.logsByAgent);
  return { agents, tasks, edges, pipeline, logs, logsByAgent };
}
