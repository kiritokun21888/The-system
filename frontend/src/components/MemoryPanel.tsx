/**
 * MemoryPanel — browses what ZERO remembers about the user. Supports adding,
 * editing and deleting memories. Color-coded by memory type.
 */
import { motion } from "framer-motion";
import { useState } from "react";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import type { Memory } from "../lib/types";

const TYPE_COLOR: Record<string, string> = {
  fact: "var(--accent-primary)",
  preference: "var(--accent-secondary)",
  task_context: "var(--accent-warm)",
  conversation: "var(--text-dim)",
};

export default function MemoryPanel() {
  const { memories, refreshMemory } = useZero();
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const add = async () => {
    if (!draft.trim()) return;
    await api.addMemory({ content: draft.trim(), type: "fact", importance: 0.6 });
    setDraft("");
    await refreshMemory();
  };

  const saveEdit = async (id: number) => {
    await api.updateMemory(id, { content: editText });
    setEditing(null);
    await refreshMemory();
  };

  const remove = async (id: number) => {
    await api.deleteMemory(id);
    await refreshMemory();
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="panel flex items-center gap-3 p-3">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Teach ZERO a new fact about you…"
          className="flex-1 bg-transparent font-mono text-sm text-text-primary placeholder:text-text-dim"
        />
        <button
          onClick={add}
          className="font-display text-xs text-primary hover:glow-cyan"
        >
          REMEMBER
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
        {memories.map((m: Memory, i) => (
          <motion.div
            key={m.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            className="panel group flex items-start gap-3 p-3"
            style={{ borderLeft: `3px solid ${TYPE_COLOR[m.type]}` }}
          >
            <div className="flex-1">
              {editing === m.id ? (
                <input
                  autoFocus
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveEdit(m.id)}
                  onBlur={() => saveEdit(m.id)}
                  className="w-full bg-transparent text-sm text-text-primary"
                />
              ) : (
                <div
                  className="cursor-text text-sm text-text-primary"
                  onClick={() => {
                    setEditing(m.id);
                    setEditText(m.content);
                  }}
                >
                  {m.content}
                </div>
              )}
              <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-text-dim">
                <span style={{ color: TYPE_COLOR[m.type] }}>{m.type}</span>
                <span>· {m.source}</span>
                <span>· importance {m.importance_score.toFixed(2)}</span>
              </div>
            </div>
            <button
              onClick={() => remove(m.id)}
              className="opacity-0 transition group-hover:opacity-100"
              style={{ color: "var(--accent-danger)" }}
            >
              ✕
            </button>
          </motion.div>
        ))}
        {memories.length === 0 && (
          <div className="py-10 text-center font-mono text-sm text-text-dim">
            ZERO hasn't formed any memories yet.
          </div>
        )}
      </div>
    </div>
  );
}
