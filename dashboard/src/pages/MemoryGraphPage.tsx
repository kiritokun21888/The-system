import { motion } from "framer-motion";
import { MemoryGraph } from "@/components/memory/MemoryGraph";
import { MemoryDrawer } from "@/components/memory/MemoryDrawer";
import { MemorySearch, TagFilter } from "@/components/memory/MemoryControls";
import { RetroGrid } from "@/components/effects/GridBackground";
import { useMemory } from "@/hooks/useMemory";
import { NeonText } from "@/components/effects/BeamCard";

/** Obsidian-style memory knowledge graph page. */
export function MemoryGraphPage() {
  const { filtered, memories } = useMemory();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex h-full min-h-0 flex-col gap-3"
    >
      <div className="flex items-center justify-between">
        <div>
          <NeonText color="#7B2FFF" className="text-xl font-bold">
            MEMORY VAULT
          </NeonText>
          <div className="text-[10px] font-mono text-[var(--text-dim)]">
            {memories.length} memories · {filtered.nodes.length} shown · obsidian-style graph
          </div>
        </div>
      </div>

      <MemorySearch />
      <TagFilter />

      <div className="glass relative min-h-0 flex-1 overflow-hidden">
        <RetroGrid />
        <div className="relative h-full">
          <MemoryGraph />
        </div>
        <MemoryDrawer />
      </div>
    </motion.div>
  );
}
