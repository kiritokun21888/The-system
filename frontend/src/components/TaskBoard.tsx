/**
 * TaskBoard — a Kanban view (Pending / In Progress / Done) with native HTML5
 * drag-and-drop. Cards stagger-mount and dragging a card to a column updates
 * its status through the API.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import type { Task, TaskStatus } from "../lib/types";

const COLUMNS: { id: TaskStatus; label: string; accent: string }[] = [
  { id: "pending", label: "Pending", accent: "var(--accent-warm)" },
  { id: "in_progress", label: "In Progress", accent: "var(--accent-primary)" },
  { id: "done", label: "Done", accent: "var(--accent-success)" },
];

const PRIORITY_COLOR = [
  "var(--text-dim)",
  "var(--text-dim)",
  "var(--accent-primary)",
  "var(--accent-warm)",
  "var(--accent-danger)",
];

export default function TaskBoard() {
  const { tasks, refreshTasks } = useZero();
  const [dragId, setDragId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<TaskStatus | null>(null);

  const move = async (id: number, status: TaskStatus) => {
    await api.updateTask(id, { status });
    await refreshTasks();
  };

  const byStatus = (status: TaskStatus) =>
    tasks.filter((t) =>
      status === "in_progress"
        ? t.status === "in_progress" || t.status === "delegated_to_agent"
        : t.status === status,
    );

  return (
    <div className="grid h-full grid-cols-1 gap-4 md:grid-cols-3">
      {COLUMNS.map((col) => {
        const items = byStatus(col.id);
        return (
          <div
            key={col.id}
            onDragOver={(e) => {
              e.preventDefault();
              setOverCol(col.id);
            }}
            onDragLeave={() => setOverCol(null)}
            onDrop={() => {
              if (dragId != null) void move(dragId, col.id);
              setDragId(null);
              setOverCol(null);
            }}
            className={`panel flex flex-col gap-3 p-4 ${
              overCol === col.id ? "panel-active" : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-sm" style={{ color: col.accent }}>
                {col.label}
              </span>
              <span className="font-mono text-xs text-text-dim">
                {items.length}
              </span>
            </div>

            <div className="flex flex-col gap-2 overflow-y-auto">
              <AnimatePresence>
                {items.map((task, i) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    index={i}
                    onDragStart={() => setDragId(task.id)}
                  />
                ))}
              </AnimatePresence>
              {items.length === 0 && (
                <div className="py-6 text-center font-mono text-xs text-text-dim">
                  — empty —
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TaskCard({
  task,
  index,
  onDragStart,
}: {
  task: Task;
  index: number;
  onDragStart: () => void;
}) {
  return (
    <motion.div
      layout
      draggable
      onDragStart={onDragStart}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ delay: index * 0.04, duration: 0.3, ease: [0.16, 1, 0.32, 1] }}
      className="cursor-grab rounded-xl border border-border-glow bg-surface/60 p-3 active:cursor-grabbing"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm text-text-primary">{task.title}</span>
        <span
          className="mt-1 h-2 w-2 shrink-0 rounded-full"
          style={{ background: PRIORITY_COLOR[task.priority - 1] }}
          title={`Priority ${task.priority}`}
        />
      </div>
      {task.agent_assigned && (
        <span className="mt-2 inline-block rounded bg-secondary/20 px-2 py-0.5 font-mono text-[10px] text-secondary">
          {task.agent_assigned}
        </span>
      )}
      {task.due_date && (
        <div className="mt-2 font-mono text-[10px] text-text-dim">
          due {new Date(task.due_date).toLocaleDateString()}
        </div>
      )}
      {task.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <span
              key={tag}
              className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}
