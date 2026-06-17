import { useEffect, useRef } from "react";
import { MockEngine } from "@/lib/mockData";
import { useAgentStore } from "@/store/agentStore";
import { useMetricsStore } from "@/store/metricsStore";
import { useMemoryStore } from "@/store/memoryStore";
import { useUiStore } from "@/store/uiStore";
import type {
  AgentStatus, EdgeTraffic, LogEntry, MemoryGraphT, MemoryRecord,
  MetricsSnapshot, SnapshotData, TaskRow,
} from "@/lib/types";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
const MAX_BACKOFF = 16000;

// Port 8000 now serves the real assistant backend (different protocol). The
// legacy swarm-visualization pages run on the in-browser simulation so they
// stay animated without misreading assistant events. The real, wired surface is
// the CommandBar + Notifications + StatsBar (see useAssistant).
const FORCE_MOCK = true;

/** Route a single backend/mock event into the appropriate Zustand store. */
function dispatch(type: string, data: unknown, ts?: number) {
  const ag = useAgentStore.getState();
  const me = useMetricsStore.getState();
  const ui = useUiStore.getState();
  switch (type) {
    case "snapshot": {
      const d = data as SnapshotData;
      ag.setAgents(d.agents);
      ag.setTasks(d.tasks);
      ag.setEdges(d.edges);
      if (d.pipeline?.length) ag.setPipeline(d.pipeline);
      me.setMetrics(d.metrics);
      break;
    }
    case "metric_update":
      me.setMetrics(data as MetricsSnapshot);
      break;
    case "agent_status":
      ag.setAgents(data as AgentStatus[]);
      break;
    case "task_update":
      ag.setTasks(data as TaskRow[]);
      break;
    case "edge_update":
      ag.setEdges(data as EdgeTraffic[]);
      break;
    case "log_entry":
      ag.pushLog(data as LogEntry);
      break;
    case "memory_update": {
      const d = data as { graph: MemoryGraphT; memories: MemoryRecord[] };
      useMemoryStore.getState().setData(d.graph, d.memories);
      break;
    }
  }
  if (ts) ui.setLatency(Math.max(0, Math.round(Date.now() - ts * 1000)));
}

/**
 * Connect to the FastAPI WebSocket with exponential-backoff reconnection.
 * Falls back to an in-browser MockEngine whenever the socket is down, so the
 * UI is always live and demoable.
 */
export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const mockRef = useRef<MockEngine | null>(null);
  const backoffRef = useRef(1000);
  const timerRef = useRef<number | null>(null);
  const closedRef = useRef(false);

  useEffect(() => {
    const ui = useUiStore.getState();

    const startMock = () => {
      if (mockRef.current) return;
      const engine = new MockEngine((type, data) => dispatch(type, data));
      mockRef.current = engine;
      engine.start();
      ui.setConnected(false, true);
    };
    const stopMock = () => {
      mockRef.current?.stop();
      mockRef.current = null;
    };

    if (FORCE_MOCK) {
      startMock();
      return () => {
        closedRef.current = true;
        stopMock();
      };
    }

    const connect = () => {
      if (closedRef.current) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        startMock();
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        backoffRef.current = 1000;
        stopMock();
        ui.setConnected(true, false);
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          dispatch(msg.type, msg.data, msg.ts);
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onerror = () => ws.close();
      ws.onclose = () => {
        ui.setConnected(false, !!mockRef.current);
        startMock(); // keep the UI alive while we retry
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (closedRef.current) return;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        backoffRef.current = Math.min(MAX_BACKOFF, backoffRef.current * 2);
        connect();
      }, backoffRef.current);
    };

    connect();

    return () => {
      closedRef.current = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      wsRef.current?.close();
      stopMock();
    };
  }, []);
}

/** Submit a custom task to the backend (no-op-safe if offline). */
export async function submitTask(prompt: string, priority = 2): Promise<void> {
  const base = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  try {
    await fetch(`${base}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, priority }),
    });
  } catch {
    /* offline — mock engine keeps running */
  }
}
