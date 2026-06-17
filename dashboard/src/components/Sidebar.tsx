import { motion } from "framer-motion";
import {
  Activity,
  BrainCircuit,
  ChevronRight,
  Cpu,
  LayoutDashboard,
  Settings as SettingsIcon,
} from "lucide-react";
import { useUiStore, type ViewId } from "@/store/uiStore";
import { cn } from "@/lib/utils";

const NAV: { id: ViewId; label: string; icon: typeof Cpu }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "memory", label: "Memory", icon: BrainCircuit },
  { id: "agents", label: "Agents", icon: Cpu },
  { id: "performance", label: "Performance", icon: Activity },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

/** Collapsible left navigation rail with Framer Motion width animation. */
export function Sidebar() {
  const { view, setView, sidebarExpanded, toggleSidebar, connected, usingMock, wsLatency } =
    useUiStore();

  return (
    <motion.aside
      animate={{ width: sidebarExpanded ? 240 : 60 }}
      transition={{ type: "spring", stiffness: 260, damping: 30 }}
      className="glass z-20 flex h-full shrink-0 flex-col overflow-hidden rounded-none border-y-0 border-l-0 p-3"
    >
      {/* logo + toggle */}
      <div className="mb-6 flex items-center justify-between">
        <span className="font-display text-lg font-black glow-cyan text-[var(--accent-cyan)]">
          {sidebarExpanded ? "SYSTEM" : "SYS"}
        </span>
        {sidebarExpanded && (
          <button onClick={toggleSidebar} className="text-[var(--text-dim)] hover:text-[var(--accent-cyan)]">
            <ChevronRight className="rotate-180" size={18} />
          </button>
        )}
      </div>
      {!sidebarExpanded && (
        <button
          onClick={toggleSidebar}
          className="mb-4 flex justify-center text-[var(--text-dim)] hover:text-[var(--accent-cyan)]"
        >
          <ChevronRight size={18} />
        </button>
      )}

      {/* nav items */}
      <nav className="flex flex-1 flex-col gap-1.5">
        {NAV.map((item) => {
          const Icon = item.icon;
          const activeItem = view === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={cn(
                "relative flex items-center gap-3 rounded-lg px-3 py-2.5 transition-all",
                activeItem
                  ? "bg-[rgba(0,210,255,0.12)] text-[var(--accent-cyan)]"
                  : "text-[var(--text-dim)] hover:bg-[rgba(0,210,255,0.06)] hover:text-[var(--text-primary)]"
              )}
            >
              {activeItem && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r bg-[var(--accent-cyan)]"
                  style={{ boxShadow: "0 0 10px var(--accent-cyan)" }}
                />
              )}
              <Icon size={20} className="shrink-0" />
              {sidebarExpanded && (
                <span className="font-display text-xs uppercase tracking-wider">{item.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* connection footer */}
      <div className="mt-3 flex items-center gap-2 px-2 pt-3" style={{ borderTop: "1px solid var(--border-glow)" }}>
        <span
          className="h-2 w-2 shrink-0 rounded-full pulse-dot"
          style={{
            background: connected ? "#00FF88" : usingMock ? "#FF9500" : "#FF3366",
            color: connected ? "#00FF88" : usingMock ? "#FF9500" : "#FF3366",
          }}
        />
        {sidebarExpanded && (
          <span className="text-[10px] font-mono text-[var(--text-dim)]">
            {connected ? `live · ${wsLatency}ms` : usingMock ? "simulation" : "offline"}
          </span>
        )}
      </div>
    </motion.aside>
  );
}
