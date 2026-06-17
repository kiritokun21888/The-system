import { useMemo } from "react";
import { useMemoryStore } from "@/store/memoryStore";
import type { MemoryRecord } from "@/lib/types";

const API = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Memory vault hook: filtered graph + REST CRUD against the backend. */
export function useMemory() {
  const { graph, memories, search, activeTags, selectedId } = useMemoryStore();

  // Derived: filter visible nodes by search text + active tag pills.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const byId = new Map(memories.map((m) => [m.id, m]));
    const visible = new Set(
      graph.nodes
        .filter((n) => {
          const m = byId.get(n.id);
          const tagOk = activeTags.length === 0 || n.tags.some((t) => activeTags.includes(t));
          const searchOk =
            !q ||
            n.title.toLowerCase().includes(q) ||
            n.tags.join(" ").toLowerCase().includes(q) ||
            (m?.content ?? "").toLowerCase().includes(q);
          return tagOk && searchOk;
        })
        .map((n) => n.id)
    );
    return {
      nodes: graph.nodes.filter((n) => visible.has(n.id)),
      edges: graph.edges.filter((e) => visible.has(e.source) && visible.has(e.target)),
    };
  }, [graph, memories, search, activeTags]);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    memories.forEach((m) => m.tags.forEach((t) => s.add(t)));
    return [...s].sort();
  }, [memories]);

  const selected = useMemo(
    () => memories.find((m) => m.id === selectedId) ?? null,
    [memories, selectedId]
  );

  const linkedTo = useMemo(() => {
    if (!selected) return [] as MemoryRecord[];
    const ids = new Set<string>();
    graph.edges.forEach((e) => {
      if (e.source === selected.id) ids.add(e.target);
      if (e.target === selected.id) ids.add(e.source);
    });
    return memories.filter((m) => ids.has(m.id));
  }, [selected, graph, memories]);

  return { graph, filtered, memories, allTags, selected, linkedTo };
}

/** Create a new memory file via the backend. */
export async function createMemory(body: Partial<MemoryRecord>): Promise<void> {
  await fetch(`${API}/memory`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Update an existing memory. */
export async function updateMemory(id: string, body: Partial<MemoryRecord>): Promise<void> {
  await fetch(`${API}/memory/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Delete a memory. */
export async function deleteMemory(id: string): Promise<void> {
  await fetch(`${API}/memory/${id}`, { method: "DELETE" });
}
