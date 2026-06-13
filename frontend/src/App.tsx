/**
 * App — top-level shell. Renders the persistent neural-brain background, the
 * splash boot sequence, the nav rail, routed pages, the docked command bar,
 * the notification stream and the daily-briefing overlay.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  HashRouter,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import CommandBar from "./components/CommandBar";
import DailyBriefing from "./components/DailyBriefing";
import NeuralBrain from "./components/NeuralBrain";
import NotificationStream from "./components/NotificationStream";
import { ZeroProvider, useZero } from "./lib/store";
import Agents from "./pages/Agents";
import Dashboard from "./pages/Dashboard";
import Memory from "./pages/Memory";
import Settings from "./pages/Settings";
import Tasks from "./pages/Tasks";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/tasks", label: "Tasks" },
  { to: "/agents", label: "Agents" },
  { to: "/memory", label: "Memory" },
  { to: "/settings", label: "Settings" },
];

function Splash({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const id = setTimeout(onDone, 2600);
    return () => clearTimeout(id);
  }, [onDone]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-void"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.6, letterSpacing: "0.5em" }}
        animate={{ opacity: 1, scale: 1, letterSpacing: "0.2em" }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.32, 1] }}
        className="font-display text-6xl text-primary glow-cyan"
      >
        Z.E.R.O
      </motion.div>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
        className="mt-4 font-mono text-xs uppercase tracking-[0.3em] text-text-dim"
      >
        Zero-latency Executive Reasoning Operator
      </motion.div>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: 200 }}
        transition={{ delay: 1, duration: 1.4 }}
        className="loading-bar mt-8 h-[2px] rounded bg-border-glow"
      />
    </motion.div>
  );
}

function StatusPill() {
  const { online, listening, thinking } = useZero();
  const label = !online
    ? "CONNECTING…"
    : listening
      ? "LISTENING"
      : thinking
        ? "THINKING"
        : "ONLINE";
  const color = !online
    ? "var(--accent-warm)"
    : listening || thinking
      ? "var(--accent-primary)"
      : "var(--accent-success)";
  return (
    <div className="flex items-center gap-2 font-mono text-[10px] tracking-widest">
      <span
        className={`h-1.5 w-1.5 rounded-full ${online ? "breathe" : ""}`}
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
      <span style={{ color }}>ZERO {label}</span>
    </div>
  );
}

function Shell() {
  const location = useLocation();
  return (
    <div className="relative h-full w-full">
      <NeuralBrain />
      <NotificationStream />
      <DailyBriefing />

      <header className="relative z-20 flex items-center justify-between px-6 py-4">
        <div className="font-display text-xl text-primary glow-cyan">Z.E.R.O</div>
        <nav className="flex gap-6">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `nav-link font-display text-xs ${isActive ? "active" : ""}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <StatusPill />
      </header>

      <main className="relative h-[calc(100%-140px)]">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ type: "spring", stiffness: 130, damping: 20 }}
            className="h-full"
          >
            <Routes location={location}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/agents" element={<Agents />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="relative z-20 flex justify-center px-6 pb-5">
        <CommandBar />
      </footer>
    </div>
  );
}

export default function App() {
  const [booted, setBooted] = useState(false);
  return (
    <ZeroProvider>
      <AnimatePresence>
        {!booted && <Splash onDone={() => setBooted(true)} />}
      </AnimatePresence>
      <HashRouter>
        <Shell />
      </HashRouter>
    </ZeroProvider>
  );
}
