/**
 * DailyBriefing — full-screen overlay that slides in each morning. Shows the
 * greeting, weather, calendar events, top tasks and any overnight agent work.
 * Dismisses on click anywhere.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useZero } from "../lib/store";

export default function DailyBriefing() {
  const { briefing, dismissBriefing } = useZero();

  return (
    <AnimatePresence>
      {briefing && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={dismissBriefing}
          className="fixed inset-0 z-[60] flex items-center justify-center backdrop-blur-xl"
          style={{ background: "rgba(2,4,10,0.7)" }}
        >
          <motion.div
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ type: "spring", stiffness: 120, damping: 20 }}
            className="panel panel-active w-full max-w-2xl p-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-display text-3xl text-primary glow-cyan">
              {briefing.greeting}
            </div>

            <div className="mt-8 grid grid-cols-2 gap-6">
              <Section title="Weather">
                {briefing.weather ? (
                  <div className="text-text-primary">
                    <span className="text-3xl font-display">
                      {Math.round(briefing.weather.temp_c)}°
                    </span>
                    <div className="text-sm capitalize text-text-dim">
                      {briefing.weather.condition} · {briefing.weather.city}
                    </div>
                  </div>
                ) : (
                  <Dim>Weather not connected</Dim>
                )}
              </Section>

              <Section title="Calendar">
                {briefing.events.length ? (
                  briefing.events.map((e, i) => (
                    <div key={i} className="text-sm text-text-primary">
                      {e}
                    </div>
                  ))
                ) : (
                  <Dim>No events today</Dim>
                )}
              </Section>
            </div>

            <Section title="Top Tasks" className="mt-6">
              {briefing.top_tasks.length ? (
                <ol className="space-y-1">
                  {briefing.top_tasks.map((t, i) => (
                    <li key={t.id} className="text-sm text-text-primary">
                      <span className="font-mono text-primary">{i + 1}.</span>{" "}
                      {t.title}
                    </li>
                  ))}
                </ol>
              ) : (
                <Dim>Nothing pending — you're clear.</Dim>
              )}
            </Section>

            <button
              onClick={dismissBriefing}
              className="mt-8 font-display text-sm text-primary transition hover:glow-cyan"
            >
              GOT IT, ZERO →
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Section({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="mb-2 font-display text-xs uppercase tracking-widest text-text-dim">
        {title}
      </div>
      {children}
    </div>
  );
}

function Dim({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-text-dim">{children}</div>;
}
