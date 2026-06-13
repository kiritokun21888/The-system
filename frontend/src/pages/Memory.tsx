/**
 * Memory — ZERO's memory browser. Thin page wrapper around MemoryPanel.
 */
import { motion } from "framer-motion";
import MemoryPanel from "../components/MemoryPanel";

export default function Memory() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative z-10 flex h-full flex-col gap-4 p-6"
    >
      <h1 className="font-display text-lg text-primary glow-cyan">
        WHAT ZERO REMEMBERS
      </h1>
      <div className="min-h-0 flex-1">
        <MemoryPanel />
      </div>
    </motion.div>
  );
}
