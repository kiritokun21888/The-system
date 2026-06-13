/**
 * Tasks — full task manager. A natural-language quick-add bar feeds the brain's
 * priority/date inference, with the Kanban board below.
 */
import { useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import TaskBoard from "../components/TaskBoard";

export default function Tasks() {
  const { refreshTasks } = useZero();
  const [text, setText] = useState("");

  const add = async () => {
    const raw = text.trim();
    if (!raw) return;
    await api.createTask({ title: raw, raw_text: raw });
    setText("");
    await refreshTasks();
  };

  return (
    <div className="relative z-10 flex h-full flex-col gap-4 p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="panel flex items-center gap-3 p-3"
      >
        <span className="font-display text-xs text-primary">+ TASK</span>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="e.g. Finish the proposal by Friday — it's urgent"
          className="flex-1 bg-transparent font-mono text-sm text-text-primary placeholder:text-text-dim"
        />
        <button onClick={add} className="font-display text-xs text-primary hover:glow-cyan">
          ADD
        </button>
      </motion.div>

      <div className="min-h-0 flex-1">
        <TaskBoard />
      </div>
    </div>
  );
}
