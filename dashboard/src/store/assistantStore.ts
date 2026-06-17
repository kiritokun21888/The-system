import { create } from "zustand";

export interface AssistantAgent {
  name: string;
  status: string;
  last_action: string;
  next_action: string;
  enabled: boolean;
}

export interface AssistantTask {
  id: number;
  title: string;
  priority: number;
  due: number | null;
  done: number;
}

export interface SysStats {
  cpu: number;
  ram: number;
  disk: number;
  disk_free_gb: number;
  battery?: number | null;
}

export interface Notification {
  id: string;
  title: string;
  body: string;
  level: string;
  agent: string;
  ts: number;
  action?: { type: string; path?: string; category?: string };
}

interface AssistantState {
  connected: boolean;
  agents: AssistantAgent[];
  tasks: AssistantTask[];
  stats: SysStats | null;
  uptime: number;
  vaultBytes: number;
  voiceAvailable: boolean;
  voiceListening: boolean;
  transcript: string;
  lastResponse: string;
  processing: boolean;
  notifications: Notification[];

  setConnected: (c: boolean) => void;
  setAgents: (a: AssistantAgent[]) => void;
  setTasks: (t: AssistantTask[]) => void;
  setStats: (s: SysStats) => void;
  setSystem: (s: { uptime: number; vault_bytes: number }) => void;
  setVoice: (v: { available?: boolean; listening?: boolean }) => void;
  setTranscript: (t: string) => void;
  setResponse: (t: string) => void;
  setProcessing: (p: boolean) => void;
  pushNotification: (n: Omit<Notification, "id">) => void;
  dismiss: (id: string) => void;
}

let nid = 0;

/** State for the real assistant backend (agents, tasks, stats, notifications). */
export const useAssistantStore = create<AssistantState>((set) => ({
  connected: false,
  agents: [],
  tasks: [],
  stats: null,
  uptime: 0,
  vaultBytes: 0,
  voiceAvailable: false,
  voiceListening: false,
  transcript: "",
  lastResponse: "",
  processing: false,
  notifications: [],

  setConnected: (connected) => set({ connected }),
  setAgents: (agents) => set({ agents }),
  setTasks: (tasks) => set({ tasks }),
  setStats: (stats) => set({ stats }),
  setSystem: (s) => set({ uptime: s.uptime, vaultBytes: s.vault_bytes }),
  setVoice: (v) =>
    set((st) => ({
      voiceAvailable: v.available ?? st.voiceAvailable,
      voiceListening: v.listening ?? st.voiceListening,
    })),
  setTranscript: (transcript) => set({ transcript }),
  setResponse: (lastResponse) => set({ lastResponse, processing: false }),
  setProcessing: (processing) => set({ processing }),
  pushNotification: (n) =>
    set((st) => ({
      notifications: [{ ...n, id: `n${nid++}` }, ...st.notifications].slice(0, 40),
    })),
  dismiss: (id) => set((st) => ({ notifications: st.notifications.filter((x) => x.id !== id) })),
}));
