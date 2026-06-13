/**
 * Settings — integrations hub, voice preferences and manual briefing trigger.
 */
import { motion } from "framer-motion";
import { useState } from "react";
import { api } from "../lib/api";
import { useZero } from "../lib/store";
import ConnectionsPanel from "../components/ConnectionsPanel";

export default function Settings() {
  const { brainEnabled } = useZero();
  const [briefingSent, setBriefingSent] = useState(false);

  const fireBriefing = async () => {
    await api.triggerBriefing();
    setBriefingSent(true);
    setTimeout(() => setBriefingSent(false), 3000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative z-10 flex h-full flex-col gap-6 overflow-y-auto p-6"
    >
      <section>
        <h1 className="mb-3 font-display text-lg text-primary glow-cyan">
          CONNECTIONS
        </h1>
        <ConnectionsPanel />
      </section>

      <section>
        <h2 className="mb-3 font-display text-sm text-primary">PREFERENCES</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="panel p-4">
            <div className="text-sm text-text-primary">AI Brain</div>
            <div className="mt-1 font-mono text-xs text-text-dim">
              {brainEnabled
                ? "Claude reasoning core active."
                : "Set ANTHROPIC_API_KEY in backend/.env to enable full reasoning."}
            </div>
          </div>
          <div className="panel flex items-center justify-between p-4">
            <div>
              <div className="text-sm text-text-primary">Daily Briefing</div>
              <div className="mt-1 font-mono text-xs text-text-dim">
                Trigger the morning briefing now.
              </div>
            </div>
            <button
              onClick={fireBriefing}
              className="font-display text-xs text-primary hover:glow-cyan"
            >
              {briefingSent ? "SENT ✓" : "BRIEF ME"}
            </button>
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 font-display text-sm text-primary">VOICE</h2>
        <div className="panel p-4 font-mono text-xs text-text-dim">
          Voice control is configured in <span className="text-primary">backend/.env</span>:
          set <span className="text-primary">VOICE_ENABLED=true</span>, choose a{" "}
          <span className="text-primary">WHISPER_MODEL</span>, and select{" "}
          <span className="text-primary">TTS_ENGINE</span> (pyttsx3 or elevenlabs).
          Wake word: say "<span className="text-primary">Hey ZERO</span>".
        </div>
      </section>
    </motion.div>
  );
}
