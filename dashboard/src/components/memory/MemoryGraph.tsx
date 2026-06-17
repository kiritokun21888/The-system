import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  forceCenter,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationNodeDatum,
} from "d3";
import { MemoryNode } from "@/components/nodes/MemoryNode";
import { useMemory } from "@/hooks/useMemory";
import { useMemoryStore } from "@/store/memoryStore";

const nodeTypes = { memory: MemoryNode };

interface SimNode extends SimulationNodeDatum {
  id: string;
}

/**
 * Obsidian-style force-directed memory graph. A d3-force simulation lays the
 * nodes out (charge + links + centering) exactly like Obsidian's graph view;
 * nodes are sized by importance and coloured by category.
 */
export function MemoryGraph() {
  const { filtered } = useMemory();
  const select = useMemoryStore((s) => s.select);
  const selectedId = useMemoryStore((s) => s.selectedId);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});

  // Run the force simulation whenever the visible node/edge set changes.
  const sig = useMemo(
    () => filtered.nodes.map((n) => n.id).join(",") + "|" + filtered.edges.map((e) => e.id).join(","),
    [filtered]
  );

  useEffect(() => {
    if (!filtered.nodes.length) {
      setPositions({});
      return;
    }
    const simNodes: SimNode[] = filtered.nodes.map((n, i) => ({
      id: n.id,
      x: Math.cos((i / filtered.nodes.length) * Math.PI * 2) * 220,
      y: Math.sin((i / filtered.nodes.length) * Math.PI * 2) * 220,
    }));
    const links = filtered.edges.map((e) => ({ source: e.source, target: e.target }));
    const sim = forceSimulation(simNodes)
      .force("charge", forceManyBody().strength(-420))
      .force("link", forceLink(links).id((d: SimulationNodeDatum & { id?: string }) => d.id ?? "").distance(120).strength(0.5))
      .force("center", forceCenter(0, 0))
      .stop();
    for (let i = 0; i < 320; i++) sim.tick();
    const pos: Record<string, { x: number; y: number }> = {};
    for (const n of simNodes) pos[n.id] = { x: n.x ?? 0, y: n.y ?? 0 };
    setPositions(pos);
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  const nodes: Node[] = useMemo(
    () =>
      filtered.nodes.map((n) => ({
        id: n.id,
        type: "memory",
        position: positions[n.id] ?? { x: 0, y: 0 },
        data: { label: n.title, color: n.color, importance: n.importance, selected: n.id === selectedId },
      })),
    [filtered.nodes, positions, selectedId]
  );

  const edges: Edge[] = useMemo(
    () =>
      filtered.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: e.kind === "explicit",
        style: {
          stroke: e.kind === "explicit" ? "#00D2FF" : "#4A7090",
          strokeWidth: e.kind === "explicit" ? 1.6 : 1,
          strokeDasharray: e.kind === "tag" ? "4 4" : "0",
          opacity: 0.45,
        },
      })),
    [filtered.edges]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      minZoom={0.2}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
      nodesConnectable={false}
      onNodeClick={(_, n) => select(n.id)}
      onPaneClick={() => select(null)}
    >
      <Background variant={BackgroundVariant.Dots} gap={30} size={1} color="rgba(123,47,255,0.12)" />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
