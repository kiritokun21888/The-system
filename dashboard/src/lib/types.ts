// Shared types mirroring the FastAPI backend event payloads.

export interface AgentStatus {
  name: string;
  icon: string;
  status: "running" | "idle" | "error" | "done";
  active: number;
  processed: number;
  failures: number;
  error_rate: number;
  avg_latency: number;
  per_minute: number;
  cache_hits: number;
  cost_usd: number;
  current_task: string;
}

export interface TaskRow {
  id: string;
  prompt: string;
  priority: number;
  status: string;
  stage: string;
  loops: Record<string, number>;
  elapsed: number;
  updated: number;
  review_score?: number | null;
  pass_rate?: number | null;
}

export interface EdgeTraffic {
  source: string;
  target: string;
  volume: number;
  feedback?: boolean;
}

export interface AgentMetric {
  processed: number;
  failures: number;
  error_rate: number;
  avg_latency: number;
  per_minute: number;
  cost_usd: number;
  tokens_in: number;
  tokens_out: number;
  cache_hits: number;
}

export interface MetricsSnapshot {
  uptime_seconds: number;
  queue_depth: number;
  tasks_submitted: number;
  tasks_active: number;
  tasks_completed: number;
  tasks_escalated: number;
  tasks_aborted: number;
  total_cost_usd: number;
  agents: Record<string, AgentMetric>;
}

export interface LogEntry {
  level: string;
  logger: string;
  msg: string;
  agent: string;
  ts: string;
}

export interface MemoryNodeT {
  id: string;
  title: string;
  category: string;
  color: string;
  importance: number;
  tags: string[];
}

export interface MemoryEdgeT {
  id: string;
  source: string;
  target: string;
  kind: "explicit" | "tag";
}

export interface MemoryGraphT {
  nodes: MemoryNodeT[];
  edges: MemoryEdgeT[];
}

export interface MemoryRecord {
  id: string;
  title: string;
  category: string;
  tags: string[];
  importance: number;
  created: string;
  updated: string;
  linked: string[];
  content: string;
}

export type WsEvent =
  | { type: "snapshot"; data: SnapshotData; ts: number }
  | { type: "metric_update"; data: MetricsSnapshot; ts: number }
  | { type: "agent_status"; data: AgentStatus[]; ts: number }
  | { type: "task_update"; data: TaskRow[]; ts: number }
  | { type: "edge_update"; data: EdgeTraffic[]; ts: number }
  | { type: "log_entry"; data: LogEntry; ts: number }
  | { type: "memory_update"; data: { graph: MemoryGraphT; memories: MemoryRecord[] }; ts: number };

export interface SnapshotData {
  metrics: MetricsSnapshot;
  agents: AgentStatus[];
  tasks: TaskRow[];
  edges: EdgeTraffic[];
  pipeline: string[];
  connections: number;
}
