import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Minus, Square, X } from "lucide-react";
import { Spotlight } from "@/components/effects/Spotlight";
import { ParticleField } from "@/components/effects/ParticleField";
import { GridBackground } from "@/components/effects/GridBackground";
import { Sidebar } from "@/components/Sidebar";
import { ConnectionOverlay } from "@/components/ConnectionOverlay";
import { Dashboard } from "@/pages/Dashboard";
import { MemoryGraphPage } from "@/pages/MemoryGraphPage";
import { AgentControl } from "@/pages/AgentControl";
import { Performance } from "@/pages/Performance";
import { Settings } from "@/pages/Settings";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAssistant } from "@/hooks/useAssistant";
import { CommandBar } from "@/components/CommandBar";
import { Notifications, StatsBar } from "@/components/Notifications";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useUiStore, type ViewId } from "@/store/uiStore";

// Electron's draggable-region CSS property isn't in the standard typings.
const DRAG = { WebkitAppRegion: "drag" } as unknown as React.CSSProperties;
const NO_DRAG = { WebkitAppRegion: "no-drag" } as unknown as React.CSSProperties;

const PAGES: Record<ViewId, JSX.Element> = {
  dashboard: <Dashboard />,
  memory: <MemoryGraphPage />,
  agents: <AgentControl />,
  performance: <Performance />,
  settings: <Settings />,
};

/** Custom frameless title bar with a drag region + window controls. */
function TitleBar() {
  return (
    <div
      className="flex h-9 shrink-0 items-center justify-between px-4"
      style={DRAG}
    >
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-[var(--accent-cyan)] pulse-dot text-[var(--accent-cyan)]" />
        <span className="font-display text-[11px] font-bold tracking-[0.2em] text-[var(--text-primary)]">
          SWARM · MISSION CONTROL
        </span>
      </div>
      <div className="flex items-center gap-1" style={NO_DRAG}>
        <button onClick={() => window.swarmAPI?.minimize()} className="rounded p-1 text-[var(--text-dim)] hover:bg-[rgba(0,210,255,0.1)] hover:text-[var(--accent-cyan)]">
          <Minus size={14} />
        </button>
        <button onClick={() => window.swarmAPI?.maximize()} className="rounded p-1 text-[var(--text-dim)] hover:bg-[rgba(0,210,255,0.1)] hover:text-[var(--accent-cyan)]">
          <Square size={12} />
        </button>
        <button onClick={() => window.swarmAPI?.close()} className="rounded p-1 text-[var(--text-dim)] hover:bg-[rgba(255,51,102,0.15)] hover:text-[var(--accent-red)]">
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

/** Root application shell. */
export default function App() {
  useWebSocket(); // legacy swarm visualization (simulation)
  useAssistant(); // real assistant backend (commands, agents, stats)
  const view = useUiStore((s) => s.view);
  const setView = useUiStore((s) => s.setView);

  // Honour Electron deep links (system://memory etc.) routed via preload.
  useEffect(() => {
    window.swarmAPI?.onNavigate((v) => {
      if (["dashboard", "memory", "agents", "performance", "settings"].includes(v)) {
        setView(v as ViewId);
      }
    });
  }, [setView]);

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-[var(--bg-void)]">
      {/* ambient backgrounds — isolated so a GPU/WebGL failure can't blank the app */}
      <Spotlight />
      <ErrorBoundary silent label="particles">
        <ParticleField />
      </ErrorBoundary>
      <GridBackground />

      <div className="relative z-10 flex h-full flex-col">
        <TitleBar />

        {/* always-visible real command bar + notifications */}
        <div className="flex items-center gap-3 px-4 pb-1 pt-1">
          <div className="flex-1">
            <CommandBar />
          </div>
          <Notifications />
        </div>

        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <main className="min-h-0 flex-1 overflow-hidden p-4">
            <AnimatePresence mode="wait">
              <motion.div
                key={view}
                initial={{ opacity: 0, scale: 0.99 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.99 }}
                transition={{ duration: 0.25 }}
                className="h-full"
              >
                <ErrorBoundary label="page">{PAGES[view]}</ErrorBoundary>
              </motion.div>
            </AnimatePresence>
          </main>
        </div>

        {/* real system stats strip */}
        <StatsBar />
      </div>

      <ConnectionOverlay />
    </div>
  );
}
