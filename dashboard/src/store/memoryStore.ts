import { create } from "zustand";
import type { MemoryGraphT, MemoryRecord } from "@/lib/types";

interface MemoryState {
  graph: MemoryGraphT;
  memories: MemoryRecord[];
  selectedId: string | null;
  search: string;
  activeTags: string[];
  setData: (graph: MemoryGraphT, memories: MemoryRecord[]) => void;
  select: (id: string | null) => void;
  setSearch: (q: string) => void;
  toggleTag: (tag: string) => void;
  clearTags: () => void;
}

/** Obsidian-style memory vault state: graph, records, selection, filters. */
export const useMemoryStore = create<MemoryState>((set) => ({
  graph: { nodes: [], edges: [] },
  memories: [],
  selectedId: null,
  search: "",
  activeTags: [],
  setData: (graph, memories) => set({ graph, memories }),
  select: (selectedId) => set({ selectedId }),
  setSearch: (search) => set({ search }),
  toggleTag: (tag) =>
    set((s) => ({
      activeTags: s.activeTags.includes(tag)
        ? s.activeTags.filter((t) => t !== tag)
        : [...s.activeTags, tag],
    })),
  clearTags: () => set({ activeTags: [] }),
}));
