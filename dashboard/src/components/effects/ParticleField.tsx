import { useEffect, useMemo, useState } from "react";
import Particles, { initParticlesEngine } from "@tsparticles/react";
import { loadSlim } from "@tsparticles/slim";
import type { ISourceOptions } from "@tsparticles/engine";

/** Ambient tsparticles field — slow-drifting cyan dots behind everything. */
export function ParticleField() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine);
    }).then(() => setReady(true));
  }, []);

  const options: ISourceOptions = useMemo(
    () => ({
      fullScreen: { enable: false },
      background: { color: "transparent" },
      fpsLimit: 60,
      particles: {
        number: { value: 55, density: { enable: true } },
        color: { value: ["#00D2FF", "#7B2FFF"] },
        opacity: { value: { min: 0.1, max: 0.4 } },
        size: { value: { min: 1, max: 2.5 } },
        move: {
          enable: true,
          speed: 0.4,
          direction: "none",
          random: true,
          outModes: { default: "out" },
        },
        links: {
          enable: true,
          distance: 130,
          color: "#00D2FF",
          opacity: 0.08,
          width: 1,
        },
      },
      detectRetina: true,
    }),
    []
  );

  if (!ready) return null;
  return (
    <Particles id="ambient-particles" options={options} className="pointer-events-none fixed inset-0 z-0" />
  );
}
