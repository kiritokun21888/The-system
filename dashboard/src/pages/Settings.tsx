import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Editor from "@monaco-editor/react";
import { Download, FolderInput, Plug, Cpu } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { NeonText } from "@/components/effects/BeamCard";
import { useUiStore } from "@/store/uiStore";
import { useMemoryStore } from "@/store/memoryStore";

const API = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ACCENTS = ["#00D2FF", "#7B2FFF", "#00FF88", "#FF9500", "#FF3366"];
const MODELS = [
  { id: "deterministic", label: "Deterministic", desc: "Offline · reproducible · $0" },
  { id: "anthropic", label: "Anthropic", desc: "claude-opus-4-8 / claude-haiku-4-5" },
  { id: "local", label: "Local", desc: "Self-hosted model endpoint" },
];

/** Settings & integrations hub. */
export function Settings() {
  const { connected, usingMock, wsLatency, accent, setAccent } = useUiStore();
  const memories = useMemoryStore((s) => s.memories);
  const [config, setConfig] = useState("# loading config.yaml …");
  const [model, setModel] = useState("deterministic");
  const [vault, setVault] = useState("./dashboard/memory");

  useEffect(() => {
    fetch(`${API}/config`)
      .then((r) => r.json())
      .then((d) => d.content && setConfig(d.content))
      .catch(() => setConfig("# backend offline — start dashboard_backend.server to load config.yaml"));
  }, []);

  const exportVault = () => {
    const blob = new Blob([JSON.stringify(memories, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "memory-vault.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full min-h-0 overflow-y-auto pr-1">
      <NeonText className="text-xl font-bold">SETTINGS &amp; CONNECTIONS</NeonText>
      <div className="mb-4 text-[10px] font-mono text-[var(--text-dim)]">integration hub</div>

      <div className="grid grid-cols-2 gap-4">
        {/* connection */}
        <Card active>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <Plug size={13} /> Backend Connection
              </span>
            </CardTitle>
            <Badge color={connected ? "#00FF88" : usingMock ? "#FF9500" : "#FF3366"}>
              {connected ? "connected" : usingMock ? "simulation" : "offline"}
            </Badge>
          </CardHeader>
          <div className="space-y-1 font-mono text-xs text-[var(--text-dim)]">
            <div>endpoint · ws://localhost:8000/ws</div>
            <div>latency · <span className="text-[var(--accent-cyan)]">{wsLatency}ms</span></div>
            <div>mode · {usingMock ? "in-browser mock feed" : "live websocket"}</div>
          </div>
        </Card>

        {/* model selector */}
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <Cpu size={13} /> Model Backend
              </span>
            </CardTitle>
          </CardHeader>
          <div className="grid grid-cols-3 gap-2">
            {MODELS.map((mo) => (
              <button
                key={mo.id}
                onClick={() => setModel(mo.id)}
                className={`glass-tight p-2 text-left transition ${
                  model === mo.id ? "border-[var(--accent-cyan)] shadow-[0_0_16px_rgba(0,210,255,0.3)]" : ""
                }`}
              >
                <div className="font-display text-[11px] text-[var(--text-primary)]">{mo.label}</div>
                <div className="mt-0.5 text-[9px] text-[var(--text-dim)]">{mo.desc}</div>
              </button>
            ))}
          </div>
        </Card>

        {/* theme */}
        <Card>
          <CardHeader>
            <CardTitle>Theme · Accent Color</CardTitle>
          </CardHeader>
          <div className="flex items-center gap-3">
            {ACCENTS.map((c) => (
              <button
                key={c}
                onClick={() => setAccent(c)}
                className="h-8 w-8 rounded-full transition hover:scale-110"
                style={{
                  background: c,
                  boxShadow: `0 0 14px ${c}`,
                  border: accent === c ? "2px solid #E8F4FF" : "2px solid transparent",
                }}
              />
            ))}
          </div>
        </Card>

        {/* vault path + export */}
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="inline-flex items-center gap-1.5">
                <FolderInput size={13} /> Memory Vault
              </span>
            </CardTitle>
          </CardHeader>
          <Input value={vault} onChange={(e) => setVault(e.target.value)} className="mb-2 font-mono text-xs" />
          <Button variant="outline" size="sm" onClick={exportVault}>
            <Download size={14} /> Export vault ({memories.length} notes)
          </Button>
        </Card>
      </div>

      {/* config editor */}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle>config.yaml — live editor</CardTitle>
          <span className="font-mono text-[10px] text-[var(--text-dim)]">Monaco</span>
        </CardHeader>
        <div className="overflow-hidden rounded-lg border border-[var(--border-glow)]" style={{ height: 320 }}>
          <Editor
            height="320px"
            defaultLanguage="yaml"
            theme="vs-dark"
            value={config}
            onChange={(v) => setConfig(v ?? "")}
            options={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 12,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              padding: { top: 12 },
            }}
          />
        </div>
      </Card>
    </motion.div>
  );
}
