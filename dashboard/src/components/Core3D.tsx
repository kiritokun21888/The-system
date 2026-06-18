import { Suspense, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Icosahedron, Stars } from "@react-three/drei";
import type { Mesh } from "three";

/** The rotating wireframe "core" mesh. */
function CoreMesh({ active }: { active: boolean }) {
  const inner = useRef<Mesh>(null);
  const outer = useRef<Mesh>(null);

  useFrame((_, dt) => {
    if (inner.current) {
      inner.current.rotation.y += dt * 0.4;
      inner.current.rotation.x += dt * 0.15;
    }
    if (outer.current) {
      outer.current.rotation.y -= dt * 0.2;
      outer.current.rotation.z += dt * 0.1;
    }
  });

  const accent = active ? "#00FF88" : "#00D2FF";
  return (
    <Float speed={2} rotationIntensity={0.4} floatIntensity={0.8}>
      <Icosahedron ref={outer} args={[1.6, 1]}>
        <meshBasicMaterial color={accent} wireframe transparent opacity={0.35} />
      </Icosahedron>
      <Icosahedron ref={inner} args={[1.05, 0]}>
        <meshStandardMaterial
          color="#7B2FFF"
          emissive={accent}
          emissiveIntensity={0.7}
          metalness={0.8}
          roughness={0.2}
          wireframe
        />
      </Icosahedron>
      <pointLight position={[0, 0, 0]} color={accent} intensity={4} distance={6} />
    </Float>
  );
}

/** Detect whether the browser/GPU can create a WebGL context. */
function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

/** A compact 3D core visualization for the dashboard header. */
export function Core3D({ active = false }: { active?: boolean }) {
  // Skip entirely on machines without WebGL (e.g. hardware acceleration off) so
  // the canvas never throws and blanks anything.
  if (!webglAvailable()) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div
          className="h-16 w-16 rounded-full border-2"
          style={{
            borderColor: active ? "#00FF88" : "#00D2FF",
            boxShadow: `0 0 24px ${active ? "#00FF88" : "#00D2FF"}66`,
          }}
        />
      </div>
    );
  }
  return (
    <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }}>
      <Suspense fallback={null}>
        <ambientLight intensity={0.3} />
        <Stars radius={40} depth={30} count={800} factor={3} saturation={0} fade speed={1} />
        <CoreMesh active={active} />
      </Suspense>
    </Canvas>
  );
}
