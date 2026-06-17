import { create } from "zustand";

export type ViewId = "dashboard" | "memory" | "agents" | "performance" | "settings";

interface UiState {
  view: ViewId;
  sidebarExpanded: boolean;
  connected: boolean;
  usingMock: boolean;
  wsLatency: number;
  accent: string;
  setView: (v: ViewId) => void;
  toggleSidebar: () => void;
  setConnected: (c: boolean, mock?: boolean) => void;
  setLatency: (ms: number) => void;
  setAccent: (c: string) => void;
}

/** Global UI state: navigation, sidebar, connection status, theme accent. */
export const useUiStore = create<UiState>((set) => ({
  view: "dashboard",
  sidebarExpanded: false,
  connected: false,
  usingMock: false,
  wsLatency: 0,
  accent: "#00D2FF",
  setView: (view) => set({ view }),
  toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),
  setConnected: (connected, usingMock = false) => set({ connected, usingMock }),
  setLatency: (wsLatency) => set({ wsLatency }),
  setAccent: (accent) => {
    document.documentElement.style.setProperty("--accent-cyan", accent);
    set({ accent });
  },
}));
