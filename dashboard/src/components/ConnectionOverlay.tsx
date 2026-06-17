import { AnimatePresence, motion } from "framer-motion";
import { WifiOff } from "lucide-react";
import { useUiStore } from "@/store/uiStore";

/**
 * Full-screen "connection lost" overlay. Shown only when the live socket is
 * down AND the mock fallback is not active (i.e. a genuine hard outage). In
 * normal offline use the mock keeps the UI live, so this stays hidden.
 */
export function ConnectionOverlay() {
  const connected = useUiStore((s) => s.connected);
  const usingMock = useUiStore((s) => s.usingMock);
  const show = !connected && !usingMock;

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{ background: "rgba(2,4,10,0.85)", backdropFilter: "blur(8px)" }}
        >
          <motion.div
            animate={{ scale: [1, 1.1, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          >
            <WifiOff size={64} color="#FF3366" />
          </motion.div>
          <div className="mt-6 font-display text-2xl font-bold" style={{ color: "#FF3366", textShadow: "0 0 16px #FF3366aa" }}>
            CONNECTION LOST
          </div>
          <div className="mt-2 font-mono text-sm text-[var(--text-dim)]">RECONNECTING…</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
