import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AgentNode } from "@/components/nodes/AgentNode";
import { AnimatedEdge } from "@/components/nodes/AnimatedEdge";
import { useAgents } from "@/hooks/useAgents";
import { STATUS_COLOR } from "@/lib/utils";

const nodeTypes = { agent: AgentNode };
const edgeTypes = { animated: AnimatedEdge };

/** Center panel: the live React Flow agent graph with animated data edges. */
export function AgentGraph() {
  const { agents, edges, pipeline } = useAgents();
  const byName = useMemo(() => new Map(agents.map((a) => [a.name, a])), [agents]);

  const nodes: Node[] = useMemo(() => {
    return pipeline.map((name, i) => {
      const a = byName.get(name);
      return {
        id: name,
        type: "agent",
        position: { x: 60 + i * 175, y: 150 + (i % 2 === 0 ? -40 : 40) },
        data: {
          label: name,
          icon: a?.icon ?? "cpu",
          status: a?.status ?? "idle",
          active: a?.active ?? 0,
          processed: a?.processed ?? 0,
        },
        draggable: true,
      };
    });
  }, [pipeline, byName]);

  const flowEdges: Edge[] = useMemo(() => {
    return edges.map((e, i) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      type: "animated",
      data: { volume: e.volume, feedback: e.feedback },
    }));
  }, [edges]);

  return (
    <div className="glass relative h-full overflow-hidden p-0">
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.4}
        maxZoom={1.6}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={26} size={1} color="rgba(0,210,255,0.12)" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(n) => STATUS_COLOR[(n.data as { status?: string })?.status ?? "idle"] ?? "#4A7090"}
          maskColor="rgba(2,4,10,0.6)"
        />
      </ReactFlow>
    </div>
  );
}
