import { useState } from "react";
import { Search, Plus } from "lucide-react";
import { useMemory, createMemory } from "@/hooks/useMemory";
import { useMemoryStore } from "@/store/memoryStore";
import { Input, Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";

/** Search bar + new-memory button (top of the memory page). */
export function MemorySearch() {
  const search = useMemoryStore((s) => s.search);
  const setSearch = useMemoryStore((s) => s.setSearch);
  const [openForm, setOpenForm] = useState(false);

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex-1">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Fuzzy search across all memories…"
          className="pl-9"
        />
      </div>
      <Button onClick={() => setOpenForm(true)}>
        <Plus size={15} /> New Memory
      </Button>
      <NewMemoryForm open={openForm} onClose={() => setOpenForm(false)} />
    </div>
  );
}

/** Tag filter pills — click to filter the graph to that tag. */
export function TagFilter() {
  const { allTags } = useMemory();
  const { activeTags, toggleTag, clearTags } = useMemoryStore();
  if (!allTags.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        onClick={clearTags}
        className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wider transition ${
          activeTags.length === 0 ? "text-[var(--accent-cyan)]" : "text-[var(--text-dim)]"
        }`}
      >
        all
      </button>
      {allTags.map((t) => (
        <button key={t} onClick={() => toggleTag(t)}>
          <Badge color={activeTags.includes(t) ? "#00D2FF" : "#4A7090"}>#{t}</Badge>
        </button>
      ))}
    </div>
  );
}

/** Modal form to create a new memory file. */
function NewMemoryForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("technical");
  const [tags, setTags] = useState("");
  const [importance, setImportance] = useState(5);
  const [content, setContent] = useState("");

  const submit = async () => {
    await createMemory({
      title: title || "Untitled",
      category,
      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      importance,
      content,
    });
    onClose();
    setTitle("");
    setTags("");
    setContent("");
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(2,4,10,0.75)", backdropFilter: "blur(6px)" }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.92, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
            className="glass border-travel w-[480px] p-6"
          >
            <div className="mb-4 font-display text-base font-bold text-[var(--accent-cyan)] glow-cyan">
              NEW MEMORY
            </div>
            <div className="flex flex-col gap-3">
              <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
              <div className="flex gap-2">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="h-9 flex-1 rounded-lg border border-[var(--border-glow)] bg-[rgba(2,4,10,0.6)] px-2 text-sm text-[var(--text-primary)] outline-none"
                >
                  <option value="technical">technical</option>
                  <option value="project">project</option>
                  <option value="task">task</option>
                  <option value="preference">preference</option>
                </select>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[var(--text-dim)]">IMP</span>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={importance}
                    onChange={(e) => setImportance(Number(e.target.value))}
                    className="accent-[var(--accent-cyan)]"
                  />
                  <span className="w-5 font-mono text-sm text-[var(--accent-cyan)]">{importance}</span>
                </div>
              </div>
              <Input placeholder="Tags (comma separated)" value={tags} onChange={(e) => setTags(e.target.value)} />
              <Textarea
                placeholder="Memory content (markdown)…"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="h-32 font-mono text-xs"
              />
              <div className="mt-1 flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={onClose}>
                  Cancel
                </Button>
                <Button variant="success" size="sm" onClick={submit}>
                  Create
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
