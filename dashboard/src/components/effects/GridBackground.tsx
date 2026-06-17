/** Aceternity-style animated cyan dot grid background. */
export function GridBackground({ className = "" }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 dot-grid opacity-60 ${className}`}>
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 0%, transparent 40%, rgba(2,4,10,0.9) 100%)",
        }}
      />
    </div>
  );
}

/** Magic UI-style retro perspective grid (used on the memory panel). */
export function RetroGrid() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="retro-grid" />
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(to top, rgba(2,4,10,0.95), transparent 60%)" }}
      />
    </div>
  );
}
