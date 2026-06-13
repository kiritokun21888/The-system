/**
 * Central app store: owns the WebSocket connection to the backend and exposes
 * live state (tasks, agents, memory, notifications, brain activity, briefing)
 * plus action helpers to the entire component tree via React context.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, WS_URL } from "./api";
import type {
  AgentSnapshot,
  Briefing,
  Connection,
  Memory,
  Task,
  ZeroEvent,
  ZeroNotification,
} from "./types";

interface ZeroState {
  online: boolean;
  brainEnabled: boolean;
  thinking: boolean;
  listening: boolean;
  /** 0..1 — drives the neural brain's global activity/surge level. */
  activity: number;
  transcript: string;
  tasks: Task[];
  agents: AgentSnapshot[];
  memories: Memory[];
  connections: Connection[];
  notifications: ZeroNotification[];
  briefing: Briefing | null;
  lastReply: string;
  send: (action: string, data: Record<string, unknown>) => void;
  chat: (message: string, speak?: boolean) => Promise<void>;
  refreshTasks: () => Promise<void>;
  refreshAgents: () => Promise<void>;
  refreshMemory: () => Promise<void>;
  refreshConnections: () => Promise<void>;
  dismissNotification: (id: string) => void;
  dismissBriefing: () => void;
  setListening: (v: boolean) => void;
}

const ZeroContext = createContext<ZeroState | null>(null);

export function ZeroProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState(false);
  const [brainEnabled, setBrainEnabled] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [listening, setListening] = useState(false);
  const [activity, setActivity] = useState(0.15);
  const [transcript, setTranscript] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [agents, setAgents] = useState<AgentSnapshot[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [notifications, setNotifications] = useState<ZeroNotification[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [lastReply, setLastReply] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const activityDecay = useRef<number | null>(null);

  const bump = useCallback((to: number) => {
    setActivity((a) => Math.min(1, Math.max(a, to)));
  }, []);

  const pushNotification = useCallback(
    (n: Omit<ZeroNotification, "id" | "ts">) => {
      const note: ZeroNotification = {
        ...n,
        id: Math.random().toString(36).slice(2),
        ts: Date.now(),
      };
      setNotifications((prev) => [note, ...prev].slice(0, 8));
      setTimeout(() => dismissNotification(note.id), 5000);
    },
    [],
  );

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const handleEvent = useCallback(
    (event: ZeroEvent) => {
      const p = event.payload as any;
      switch (event.type) {
        case "system.online":
          setOnline(true);
          break;
        case "brain.thinking":
          setThinking(true);
          bump(0.7);
          break;
        case "brain.tool":
          bump(0.9);
          break;
        case "brain.reply":
          setThinking(false);
          if (p.reply) setLastReply(p.reply);
          break;
        case "voice.wake":
          setListening(true);
          bump(1);
          break;
        case "voice.command":
          setTranscript(p.text || "");
          break;
        case "task.created":
        case "task.updated":
        case "task.deleted":
          void refreshTasks();
          break;
        case "agent.spawned":
        case "agent.state":
          void refreshAgents();
          bump(p.state === "running" ? 0.85 : 0.4);
          break;
        case "notification":
          pushNotification({
            level: p.level || "info",
            title: p.title || "ZERO",
            message: p.message || "",
          });
          break;
        case "briefing":
          setBriefing(p as Briefing);
          break;
      }
    },
    [bump, pushNotification],
  );

  // --- WebSocket lifecycle with auto-reconnect ---
  useEffect(() => {
    let closed = false;
    let retry = 0;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => {
        setOnline(true);
        retry = 0;
      };
      ws.onmessage = (msg) => {
        try {
          handleEvent(JSON.parse(msg.data) as ZeroEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setOnline(false);
        if (!closed) {
          retry = Math.min(retry + 1, 6);
          setTimeout(connect, retry * 800);
        }
      };
      ws.onerror = () => ws.close();
    };

    connect();
    void bootstrap();

    return () => {
      closed = true;
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Activity decay toward idle breathing ---
  useEffect(() => {
    activityDecay.current = window.setInterval(() => {
      setActivity((a) => {
        const target = listening ? 0.9 : thinking ? 0.7 : 0.15;
        return a + (target - a) * 0.08;
      });
    }, 120);
    return () => {
      if (activityDecay.current) window.clearInterval(activityDecay.current);
    };
  }, [listening, thinking]);

  const bootstrap = async () => {
    try {
      const s = await api.status();
      setBrainEnabled(Boolean(s.brain_enabled));
      setOnline(true);
    } catch {
      /* backend not up yet */
    }
    void refreshTasks();
    void refreshAgents();
    void refreshMemory();
    void refreshConnections();
  };

  const refreshTasks = useCallback(async () => {
    try {
      setTasks((await api.listTasks()).tasks);
    } catch {
      /* offline */
    }
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      setAgents((await api.listAgents()).agents as AgentSnapshot[]);
    } catch {
      /* offline */
    }
  }, []);

  const refreshMemory = useCallback(async () => {
    try {
      setMemories((await api.listMemory()).memories);
    } catch {
      /* offline */
    }
  }, []);

  const refreshConnections = useCallback(async () => {
    try {
      setConnections((await api.connections()).connections);
    } catch {
      /* offline */
    }
  }, []);

  const send = useCallback((action: string, data: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, data }));
    }
  }, []);

  const chat = useCallback(
    async (message: string, speak = false) => {
      setThinking(true);
      bump(0.7);
      try {
        const res = await api.chat(message, speak);
        setLastReply(res.reply);
      } catch (e) {
        pushNotification({
          level: "error",
          title: "Connection error",
          message: "Could not reach ZERO's brain.",
        });
      } finally {
        setThinking(false);
        setTranscript("");
      }
    },
    [bump, pushNotification],
  );

  const value: ZeroState = {
    online,
    brainEnabled,
    thinking,
    listening,
    activity,
    transcript,
    tasks,
    agents,
    memories,
    connections,
    notifications,
    briefing,
    lastReply,
    send,
    chat,
    refreshTasks,
    refreshAgents,
    refreshMemory,
    refreshConnections,
    dismissNotification,
    dismissBriefing: () => setBriefing(null),
    setListening,
  };

  return <ZeroContext.Provider value={value}>{children}</ZeroContext.Provider>;
}

export function useZero(): ZeroState {
  const ctx = useContext(ZeroContext);
  if (!ctx) throw new Error("useZero must be used within ZeroProvider");
  return ctx;
}
