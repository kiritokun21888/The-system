import { useEffect, useRef } from "react";
import { useAssistantStore } from "@/store/assistantStore";

const WS_URL = import.meta.env.VITE_ASSISTANT_WS ?? "ws://localhost:8000/ws";
const API = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const MAX_BACKOFF = 16000;

/** Route an assistant backend event into the store. */
function dispatch(type: string, data: any) {
  const s = useAssistantStore.getState();
  switch (type) {
    case "snapshot":
      s.setAgents(data.agents ?? []);
      s.setTasks(data.tasks ?? []);
      if (data.stats) s.setStats(data.stats);
      s.setVoice({ available: !!data.voice_available });
      break;
    case "agent_status_all":
      s.setAgents(data);
      break;
    case "agent_status":
      s.setAgents(
        (() => {
          const cur = useAssistantStore.getState().agents.slice();
          const i = cur.findIndex((a) => a.name === data.name);
          if (i >= 0) cur[i] = data;
          else cur.push(data);
          return cur;
        })()
      );
      break;
    case "task_update":
      s.setTasks(data);
      break;
    case "stats":
      s.setStats(data);
      break;
    case "system":
      s.setSystem(data);
      break;
    case "voice_status":
      s.setVoice(data);
      break;
    case "transcript":
      s.setTranscript(data.text);
      break;
    case "response":
      s.setResponse(data.text);
      break;
    case "reminder_fired":
      s.pushNotification({ title: "Reminder", body: data.text, level: "info", agent: "reminder", ts: Date.now() });
      break;
    case "notification":
      s.pushNotification({ ...data, ts: Date.now() });
      break;
  }
}

/** Connect to the real assistant backend with auto-reconnect. */
export function useAssistant() {
  const wsRef = useRef<WebSocket | null>(null);
  const backoff = useRef(1000);
  const timer = useRef<number | null>(null);
  const closed = useRef(false);

  useEffect(() => {
    const s = useAssistantStore.getState();

    const connect = () => {
      if (closed.current) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        schedule();
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => {
        backoff.current = 1000;
        s.setConnected(true);
      };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data);
          dispatch(m.type, m.data);
        } catch {
          /* ignore */
        }
      };
      ws.onerror = () => ws.close();
      ws.onclose = () => {
        s.setConnected(false);
        schedule();
      };
    };
    const schedule = () => {
      if (closed.current) return;
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        backoff.current = Math.min(MAX_BACKOFF, backoff.current * 2);
        connect();
      }, backoff.current);
    };

    connect();
    return () => {
      closed.current = true;
      if (timer.current) window.clearTimeout(timer.current);
      wsRef.current?.close();
    };
  }, []);
}

/** Send a text command to the backend. Returns the spoken/typed response. */
export async function sendCommand(text: string): Promise<string> {
  useAssistantStore.getState().setProcessing(true);
  try {
    const r = await fetch(`${API}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await r.json();
    const resp = data.response ?? data.message ?? "Done.";
    useAssistantStore.getState().setResponse(resp);
    return resp;
  } catch {
    const msg = "Backend offline — start the engine (Start-System.bat) to run real commands.";
    useAssistantStore.getState().setResponse(msg);
    return msg;
  }
}

/** Toggle the offline voice listener on the backend. */
export async function setVoiceEnabled(enabled: boolean): Promise<void> {
  try {
    await fetch(`${API}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice: { enabled } }),
    });
  } catch {
    /* offline */
  }
}
