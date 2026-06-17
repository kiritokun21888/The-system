import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";

export interface MemoryNodeData {
  label: string;
  color: string;
  importance: number;
  selected: boolean;
  [key: string]: unknown;
}

/** Obsidian-style memory node: a glowing dot sized by importance + a label. */
function MemoryNodeImpl({ data }: { data: MemoryNodeData }) {
  const size = 14 + data.importance * 3;
  return (
    <div className="flex flex-col items-center" style={{ width: Math.max(120, size + 40) }}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <motion.div
        className="rounded-full"
        style={{
          width: size,
          height: size,
          background: data.color,
          boxShadow: `0 0 ${data.selected ? 26 : 12}px ${data.color}`,
          border: data.selected ? `2px solid #E8F4FF` : `1px solid ${data.color}`,
        }}
        whileHover={{ scale: 1.25 }}
        animate={{ scale: data.selected ? 1.2 : 1 }}
      />
      <div
        className="mt-1 max-w-[120px] truncate text-center text-[10px]"
        style={{ color: data.selected ? "#E8F4FF" : "#4A7090" }}
      >
        {data.label}
      </div>
    </div>
  );
}

export const MemoryNode = memo(MemoryNodeImpl);
