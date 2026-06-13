/**
 * Agents — background agent control panel. Launch any of the six agent types
 * and watch their orbs + live results stream in.
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import AgentStatus from "../components/AgentStatus";

const AGENT_TYPES = [
  { type: "research", label: "Research", hint: "topic to research" },
  { type: "draft", label: "Draft", hint: "what to write" },
  { type: "monitor", label: "Monitor", hint: "URL to watch" },
  { type: "calendar", label: "Calendar", hint: "prepare briefing" },
  { type: "email", label: "Email", hint: "summarize inbox" },
  { type: "focus", label: "Focus", hint: "minutes, e.g. 25" },
];

export default function Agents() {
  const { agents, refreshAgents } = useZero();
  const [selected, setSelected] = useState("research");
  const [input, setInput] = useState("");

  const launch = async () => {
    await api.spawnAgent(selected, input || "go");
    setInput("");
    await refreshAgents();
  };

  const hint = AGENT_TYPES.find((a) => a.type === selected)?.hint || "";

  return (
    <div className="relative z-10 flex h-full flex-col gap-4 p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="panel flex flex-col gap-3 p-4"
      >
        <h2 className="font-display text-sm text-primary">DISPATCH AGENT</h2>
        <div className="flex flex-wrap gap-2">
          {AGENT_TYPES.map((a) => (
            <button
              key={a.type}
              onClick={() => setSelected(a.type)}
              className="rounded-full border px-3 py-1 font-mono text-xs transition"
              style={{
                borderColor:
                  selected === a.type
                    ? "var(--accent-primary)"
                    : "var(--border-glow)",
                color:
                  selected === a.type
                    ? "var(--accent-primary)"
                    : "var(--text-dim)",
                background:
                  selected === a.type ? "rgba(0,210,255,0.08)" : "transparent",
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && launch()}
            placeholder={hint}
            className="flex-1 bg-transparent font-mono text-sm text-text-primary placeholder:text-text-dim"
          />
          <button onClick={launch} className="font-display text-xs text-primary hover:glow-cyan">
            LAUNCH
          </button>
        </div>
      </motion.div>

      <div className="panel flex-1 overflow-y-auto p-4">
        <h2 className="mb-4 font-display text-sm text-primary">AGENT SWARM</h2>
        <AgentStatus />
        <div className="mt-6 space-y-2">
          {agents
            .filter((a) => a.result || a.error)
            .map((a) => (
              <div key={a.id} className="rounded-lg border border-border-glow p-3">
                <div className="font-mono text-xs text-primary">
                  {a.type} · {a.id}
                </div>
                <div className="mt-1 whitespace-pre-wrap text-sm text-text-primary">
                  {a.error || a.result}
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
