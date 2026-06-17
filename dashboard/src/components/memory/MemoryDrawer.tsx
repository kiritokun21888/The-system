import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link2, Pencil, Trash2, X, Check } from "lucide-react";
import { useMemory, deleteMemory, updateMemory } from "@/hooks/useMemory";
import { useMemoryStore } from "@/store/memoryStore";
import { renderMarkdown } from "@/lib/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { NeonText } from "@/components/effects/BeamCard";

const CAT_COLOR: Record<string, string> = {
  technical: "#00D2FF",
  project: "#7B2FFF",
  task: "#00FF88",
  preference: "#FF9500",
};

/** Right-side drawer showing the selected memory: rendered markdown, tags,
 *  linked notes, and edit / delete controls. */
export function MemoryDrawer() {
  const { selected, linkedTo } = useMemory();
  const select = useMemoryStore((s) => s.select);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);

  useEffect(() => {
    setEditing(false);
    setConfirmDel(false);
    setDraft(selected?.content ?? "");
  }, [selected?.id]);

  const color = selected ? CAT_COLOR[selected.category] ?? "#00D2FF" : "#00D2FF";

  return (
    <AnimatePresence>
      {selected && (
        <motion.div
          initial={{ x: 460, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 460, opacity: 0 }}
          transition={{ type: "spring", stiffness: 280, damping: 32 }}
          className="glass absolute right-4 top-4 bottom-4 z-30 flex w-[440px] flex-col p-5"
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <NeonText color={color} className="text-lg font-bold leading-tight">
              {selected.title}
            </NeonText>
            <button onClick={() => select(null)} className="text-[var(--text-dim)] hover:text-[var(--accent-red)]">
              <X size={18} />
            </button>
          </div>

          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            <Badge color={color}>{selected.category}</Badge>
            {selected.tags.map((t) => (
              <Badge key={t} color="#4A7090">
                #{t}
              </Badge>
            ))}
            <Badge color="#FF9500">imp {selected.importance}</Badge>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {editing ? (
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="h-64 font-mono text-xs"
              />
            ) : (
              <div
                className="md-body text-sm leading-relaxed text-[var(--text-primary)]"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(selected.content) }}
              />
            )}

            {linkedTo.length > 0 && (
              <div className="mt-5">
                <div className="mb-2 flex items-center gap-1 text-[10px] font-display uppercase tracking-widest text-[var(--text-dim)]">
                  <Link2 size={12} /> Linked Memories
                </div>
                <div className="flex flex-col gap-1.5">
                  {linkedTo.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => select(l.id)}
                      className="glass-tight flex items-center gap-2 p-2 text-left text-xs text-[var(--text-primary)] hover:border-[var(--accent-cyan)]"
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: CAT_COLOR[l.category] ?? "#00D2FF" }}
                      />
                      {l.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* controls */}
          <div className="mt-4 flex items-center gap-2" style={{ borderTop: "1px solid var(--border-glow)", paddingTop: 12 }}>
            {editing ? (
              <Button
                variant="success"
                size="sm"
                onClick={async () => {
                  await updateMemory(selected.id, { content: draft });
                  setEditing(false);
                }}
              >
                <Check size={14} /> Save
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <Pencil size={14} /> Edit
              </Button>
            )}
            {confirmDel ? (
              <Button variant="danger" size="sm" onClick={async () => {
                await deleteMemory(selected.id);
                select(null);
              }}>
                <Trash2 size={14} /> Confirm delete
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setConfirmDel(true)}>
                <Trash2 size={14} /> Delete
              </Button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
