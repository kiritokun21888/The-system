import { create } from "zustand";
import type { AgentStatus, EdgeTraffic, LogEntry, TaskRow } from "@/lib/types";

interface AgentState {
  agents: AgentStatus[];
  tasks: TaskRow[];
  edges: EdgeTraffic[];
  pipeline: string[];
  logs: LogEntry[];
  logsByAgent: Record<string, LogEntry[]>;
  setAgents: (a: AgentStatus[]) => void;
  setTasks: (t: TaskRow[]) => void;
  setEdges: (e: EdgeTraffic[]) => void;
  setPipeline: (p: string[]) => void;
  pushLog: (l: LogEntry) => void;
}

const MAX_LOGS = 200;

/** Live agent graph state: agents, tasks, edges, and a rolling log buffer. */
export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  tasks: [],
  edges: [],
  pipeline: ["spec_parser", "coder", "test_writer", "test_runner", "reviewer"],
  logs: [],
  logsByAgent: {},
  setAgents: (agents) => set({ agents }),
  setTasks: (tasks) => set({ tasks }),
  setEdges: (edges) => set({ edges }),
  setPipeline: (pipeline) => set({ pipeline }),
  pushLog: (l) =>
    set((s) => {
      const logs = [l, ...s.logs].slice(0, MAX_LOGS);
      const key = l.agent || l.logger || "system";
      const agentLogs = [l, ...(s.logsByAgent[key] ?? [])].slice(0, 20);
      return { logs, logsByAgent: { ...s.logsByAgent, [key]: agentLogs } };
    }),
}));
