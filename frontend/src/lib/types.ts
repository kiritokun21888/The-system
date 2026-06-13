export type TaskStatus =
  | "pending"
  | "in_progress"
  | "done"
  | "delegated_to_agent";

export interface Task {
  id: number;
  title: string;
  description: string;
  priority: number;
  status: TaskStatus;
  due_date: string | null;
  created_at: string | null;
  updated_at: string | null;
  tags: string[];
  subtasks: { title: string; done: boolean }[];
  agent_assigned: string | null;
  notes: string;
}

export type AgentState = "idle" | "running" | "done" | "error";

export interface AgentSnapshot {
  id: string;
  type: string;
  input: string;
  state: AgentState;
  result: string | null;
  error: string | null;
  created_at: string;
}

export type MemoryType = "fact" | "preference" | "task_context" | "conversation";

export interface Memory {
  id: number;
  type: MemoryType;
  content: string;
  source: string;
  timestamp: string | null;
  tags: string[];
  importance_score: number;
}

export interface Connection {
  service: string;
  connected: boolean;
  last_synced: string | null;
}

export interface ZeroNotification {
  id: string;
  level: "info" | "success" | "warn" | "error";
  title: string;
  message: string;
  ts: number;
}

export interface Briefing {
  greeting: string;
  weather: {
    ok: boolean;
    city: string;
    temp_c: number;
    condition: string;
  } | null;
  events: string[];
  top_tasks: Task[];
  generated_at: string;
}

export interface ZeroEvent {
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}
