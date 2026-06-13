/**
 * REST client for the Z.E.R.O backend. All calls target localhost:8000.
 */
import type { Connection, Memory, Task } from "./types";

export const API_BASE =
  (window as any).ZERO_API_BASE || "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => request<Record<string, unknown>>("/api/status"),

  chat: (message: string, speak = false) =>
    request<{ reply: string; tools_used: unknown[] }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, speak }),
    }),

  // Tasks
  listTasks: () => request<{ tasks: Task[] }>("/api/tasks"),
  createTask: (payload: Partial<Task> & { raw_text?: string }) =>
    request<Task>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (id: number, payload: Partial<Task>) =>
    request<Task>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteTask: (id: number) =>
    request<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),

  // Memory
  listMemory: () => request<{ memories: Memory[] }>("/api/memory"),
  addMemory: (payload: { content: string; type?: string; tags?: string[]; importance?: number }) =>
    request<Memory>("/api/memory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateMemory: (id: number, payload: Partial<Memory>) =>
    request<Memory>(`/api/memory/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteMemory: (id: number) =>
    request<{ ok: boolean }>(`/api/memory/${id}`, { method: "DELETE" }),

  // Agents
  listAgents: () => request<{ agents: unknown[] }>("/api/agents"),
  spawnAgent: (agent_type: string, input: string) =>
    request<{ ok: boolean; agent_id: string }>("/api/agents", {
      method: "POST",
      body: JSON.stringify({ agent_type, input }),
    }),
  stopAgent: (id: string) =>
    request<{ ok: boolean }>(`/api/agents/${id}`, { method: "DELETE" }),

  // System
  systemStats: () => request<Record<string, unknown>>("/api/system/stats"),
  systemAction: (action: string, args: Record<string, unknown>, confirmed = false) =>
    request<Record<string, unknown>>("/api/system/action", {
      method: "POST",
      body: JSON.stringify({ action, args, confirmed }),
    }),

  // Integrations
  connections: () => request<{ connections: Connection[] }>("/api/connections"),
  weather: () => request<Record<string, unknown>>("/api/weather"),
  triggerBriefing: () =>
    request<{ ok: boolean }>("/api/briefing", { method: "POST" }),
};

export const WS_URL =
  (window as any).ZERO_WS_BASE || "ws://127.0.0.1:8000/ws";
