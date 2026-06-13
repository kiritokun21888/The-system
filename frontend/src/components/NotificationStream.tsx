/**
 * NotificationStream — toasts that slide in from the right and auto-dismiss
 * after 5 seconds (handled in the store). Color-coded by severity level.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useZero } from "../lib/store";

const LEVEL_COLOR: Record<string, string> = {
  info: "var(--accent-primary)",
  success: "var(--accent-success)",
  warn: "var(--accent-warm)",
  error: "var(--accent-danger)",
};

export default function NotificationStream() {
  const { notifications, dismissNotification } = useZero();

  return (
    <div className="pointer-events-none fixed right-6 top-6 z-50 flex w-80 flex-col gap-3">
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.id}
            layout
            initial={{ opacity: 0, x: 120 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 120 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            onClick={() => dismissNotification(n.id)}
            className="panel pointer-events-auto cursor-pointer p-3"
            style={{ borderLeft: `3px solid ${LEVEL_COLOR[n.level]}` }}
          >
            <div
              className="font-display text-xs"
              style={{ color: LEVEL_COLOR[n.level] }}
            >
              {n.title}
            </div>
            <div className="mt-1 text-sm text-text-primary opacity-90">
              {n.message}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
