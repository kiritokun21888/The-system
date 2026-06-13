/**
 * ConnectionsPanel — integration manager. Each service shows a connected
 * (green) or disconnected (dim) status, a connect action, and last-synced time.
 */
import { motion } from "framer-motion";
import { useState } from "react";
import { useZero } from "../lib/store";
import type { Connection } from "../lib/types";

export default function ConnectionsPanel() {
  const { connections, refreshConnections } = useZero();
  const [keyFor, setKeyFor] = useState<string | null>(null);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {connections.map((c: Connection, i) => (
        <motion.div
          key={c.service}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
          className="panel flex items-center justify-between p-4"
        >
          <div className="flex items-center gap-3">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{
                background: c.connected
                  ? "var(--accent-success)"
                  : "var(--text-dim)",
                boxShadow: c.connected ? "0 0 10px var(--accent-success)" : "none",
              }}
            />
            <div>
              <div className="text-sm text-text-primary">{c.service}</div>
              <div className="font-mono text-[10px] text-text-dim">
                {c.connected
                  ? `synced ${c.last_synced ? new Date(c.last_synced).toLocaleTimeString() : ""}`
                  : "not connected"}
              </div>
            </div>
          </div>
          <button
            onClick={() => {
              setKeyFor(keyFor === c.service ? null : c.service);
              void refreshConnections();
            }}
            className="font-display text-xs"
            style={{
              color: c.connected ? "var(--accent-success)" : "var(--accent-primary)",
            }}
          >
            {c.connected ? "MANAGE" : "CONNECT"}
          </button>
        </motion.div>
      ))}
      {keyFor && (
        <div className="panel col-span-full p-4">
          <div className="mb-2 font-display text-xs text-primary">
            Configure {keyFor}
          </div>
          <p className="font-mono text-xs text-text-dim">
            Add the relevant key to <span className="text-primary">backend/.env</span>{" "}
            and restart ZERO. OAuth services launch their consent flow from the
            desktop client. See <span className="text-primary">.env.example</span>{" "}
            for the exact variable names.
          </p>
        </div>
      )}
    </div>
  );
}
