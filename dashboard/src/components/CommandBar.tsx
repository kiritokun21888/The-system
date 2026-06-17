import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Mic, MicOff, Loader2, CornerDownLeft } from "lucide-react";
import { sendCommand, setVoiceEnabled } from "@/hooks/useAssistant";
import { useAssistantStore } from "@/store/assistantStore";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "system stats",
  "add task buy milk asap",
  "remind me in 20 minutes to stretch",
  "open chrome",
  "research electric cars",
  "what's running",
];

/** Always-visible command bar: type a command, it really executes. */
export function CommandBar() {
  const [text, setText] = useState("");
  const { processing, lastResponse, transcript, voiceAvailable, voiceListening, connected } =
    useAssistantStore();
  const [micOn, setMicOn] = useState(true);

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    const cmd = text.trim();
    if (!cmd) return;
    setText("");
    await sendCommand(cmd);
  };

  const toggleMic = async () => {
    const next = !micOn;
    setMicOn(next);
    await setVoiceEnabled(next);
  };

  return (
    <div className="relative z-30 mx-auto w-full max-w-3xl">
      <form onSubmit={submit} className="glass border-travel flex items-center gap-2 p-2">
        {/* mic / voice status */}
        <button
          type="button"
          onClick={toggleMic}
          title={
            voiceAvailable
              ? voiceListening
                ? "Listening…"
                : 'Voice ready — say "Hey System"'
              : "Voice offline (install voice pack)"
          }
          className={cn(
            "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition",
            voiceListening
              ? "text-[var(--accent-green)]"
              : voiceAvailable
                ? "text-[var(--accent-cyan)]"
                : "text-[var(--text-dim)]"
          )}
        >
          {micOn ? <Mic size={18} /> : <MicOff size={18} />}
          {voiceListening && (
            <Waveform />
          )}
        </button>

        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='Type a command…  e.g. "open chrome" or "add task buy milk"'
          className="border-0 bg-transparent focus:shadow-none"
        />

        <button
          type="submit"
          disabled={processing}
          className="flex h-9 items-center gap-1.5 rounded-lg bg-[rgba(0,210,255,0.14)] px-3 text-[var(--accent-cyan)] transition hover:bg-[rgba(0,210,255,0.26)] disabled:opacity-50"
        >
          {processing ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          <span className="text-xs font-display tracking-wider">RUN</span>
        </button>
      </form>

      {/* transcript (from voice) */}
      <AnimatePresence>
        {transcript && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-1 px-3 text-[11px] font-mono text-[var(--accent-green)]"
          >
            🎙 heard: "{transcript}"
          </motion.div>
        )}
      </AnimatePresence>

      {/* response line */}
      <AnimatePresence>
        {lastResponse && (
          <motion.div
            key={lastResponse}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="glass-tight mt-2 flex items-start gap-2 p-2.5 text-sm text-[var(--text-primary)]"
          >
            <CornerDownLeft size={14} className="mt-0.5 shrink-0 text-[var(--accent-cyan)]" />
            <span>{lastResponse}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* quick suggestions when idle */}
      {!lastResponse && !text && (
        <div className="mt-2 flex flex-wrap justify-center gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => sendCommand(s)}
              className="rounded-full border border-[var(--border-glow)] px-2.5 py-0.5 text-[10px] text-[var(--text-dim)] transition hover:border-[var(--accent-cyan)] hover:text-[var(--accent-cyan)]"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      {!connected && (
        <div className="mt-1 text-center text-[10px] font-mono text-[var(--accent-amber)]">
          engine offline — commands queue until Start-System.bat is running
        </div>
      )}
    </div>
  );
}

/** Animated listening waveform ring around the mic. */
function Waveform() {
  return (
    <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="absolute rounded-full border border-[var(--accent-green)]"
          style={{ width: 36, height: 36 }}
          initial={{ scale: 0.6, opacity: 0.6 }}
          animate={{ scale: 1.8, opacity: 0 }}
          transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.45, ease: "easeOut" }}
        />
      ))}
    </span>
  );
}
