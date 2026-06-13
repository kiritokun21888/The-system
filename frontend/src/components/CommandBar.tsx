/**
 * CommandBar — the primary voice/text command input. Expands from a compact
 * pill to full width while listening, pulses cyan, and shows the live
 * transcript as ZERO hears it.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useZero } from "../lib/store";

export default function CommandBar() {
  const { chat, thinking, listening, setListening, transcript, lastReply } =
    useZero();
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (transcript) setValue(transcript);
  }, [transcript]);

  const expanded = focused || listening || value.length > 0;

  const submit = async () => {
    const text = value.trim();
    if (!text) return;
    setValue("");
    await chat(text, true);
  };

  return (
    <div className="pointer-events-auto flex w-full flex-col items-center gap-3">
      <AnimatePresence>
        {lastReply && (
          <motion.div
            key={lastReply}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.32, 1] }}
            className="panel max-w-2xl px-5 py-3 text-center text-sm text-text-primary"
          >
            <span className="font-display text-xs text-primary">ZERO</span>{" "}
            <span className="opacity-90">{lastReply}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        layout
        animate={{ width: expanded ? "100%" : 320 }}
        transition={{ type: "spring", stiffness: 220, damping: 26 }}
        className={`panel relative flex items-center gap-3 px-5 ${
          expanded ? "max-w-3xl" : ""
        }`}
        style={{ height: 60 }}
      >
        <motion.button
          onClick={() => setListening(!listening)}
          className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
          style={{
            background: listening ? "var(--accent-primary)" : "transparent",
            border: "1px solid var(--accent-primary)",
          }}
          whileTap={{ scale: 0.9 }}
        >
          {listening && (
            <motion.span
              className="absolute inset-0 rounded-full"
              style={{ border: "1px solid var(--accent-primary)" }}
              animate={{ scale: [1, 1.8], opacity: [0.7, 0] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
          )}
          <MicIcon active={listening} />
        </motion.button>

        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={listening ? "Listening…" : "Ask ZERO anything, or speak"}
          className="flex-1 bg-transparent font-mono text-sm text-text-primary placeholder:text-text-dim"
        />

        {thinking && (
          <div className="loading-bar h-[2px] w-16 rounded bg-border-glow" />
        )}

        <button
          onClick={submit}
          className="font-display text-xs text-primary transition hover:glow-cyan"
        >
          SEND
        </button>
      </motion.div>
    </div>
  );
}

function MicIcon({ active }: { active: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke={active ? "#02040A" : "#00D2FF"}
      strokeWidth="2"
      strokeLinecap="round"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4" />
    </svg>
  );
}
