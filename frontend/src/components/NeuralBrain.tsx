/**
 * NeuralBrain — full-screen Three.js neural network that visualizes ZERO's
 * consciousness. 200+ nodes on a sphere, connected by edges that pulse with
 * activity. A central core is always lit; the whole brain breathes when idle
 * and surges with a ripple from the center when voice/activity spikes.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useZero } from "../lib/store";

const NODE_COUNT = 220;
const MAX_EDGE_DIST = 1.15;
const PRIMARY = new THREE.Color("#00D2FF");
const SECONDARY = new THREE.Color("#7B2FFF");
const CORE = new THREE.Color("#E8F4FF");

interface Graph {
  positions: Float32Array;
  basePos: THREE.Vector3[];
  edges: [number, number][];
}

function buildGraph(): Graph {
  const basePos: THREE.Vector3[] = [];
  // Fibonacci sphere for an even node distribution.
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < NODE_COUNT; i++) {
    const y = 1 - (i / (NODE_COUNT - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = golden * i;
    const jitter = 0.9 + Math.random() * 0.35;
    basePos.push(
      new THREE.Vector3(
        Math.cos(theta) * radius,
        y,
        Math.sin(theta) * radius,
      ).multiplyScalar(2.4 * jitter),
    );
  }
  // Force a central core node.
  basePos[0].set(0, 0, 0);

  const edges: [number, number][] = [];
  for (let i = 1; i < NODE_COUNT; i++) {
    let connected = 0;
    for (let j = i + 1; j < NODE_COUNT && connected < 3; j++) {
      if (basePos[i].distanceTo(basePos[j]) < MAX_EDGE_DIST) {
        edges.push([i, j]);
        connected++;
      }
    }
    // Every node keeps a faint link to the core.
    if (Math.random() < 0.08) edges.push([0, i]);
  }

  const positions = new Float32Array(NODE_COUNT * 3);
  basePos.forEach((p, i) => {
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
  });
  return { positions, basePos, edges };
}

function BrainMesh() {
  const { activity } = useZero();
  const activityRef = useRef(activity);
  activityRef.current = activity;

  const graph = useMemo(buildGraph, []);
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);
  const groupRef = useRef<THREE.Group>(null);

  // Per-node phase offsets so the breathing isn't uniform.
  const phases = useMemo(
    () => Float32Array.from({ length: NODE_COUNT }, () => Math.random() * Math.PI * 2),
    [],
  );

  const { pointGeo, lineGeo } = useMemo(() => {
    const pointGeo = new THREE.BufferGeometry();
    pointGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(graph.positions.slice(), 3),
    );
    const colors = new Float32Array(NODE_COUNT * 3);
    pointGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const lineGeo = new THREE.BufferGeometry();
    const linePos = new Float32Array(graph.edges.length * 6);
    graph.edges.forEach(([a, b], i) => {
      linePos.set(
        [
          graph.positions[a * 3],
          graph.positions[a * 3 + 1],
          graph.positions[a * 3 + 2],
          graph.positions[b * 3],
          graph.positions[b * 3 + 1],
          graph.positions[b * 3 + 2],
        ],
        i * 6,
      );
    });
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
    return { pointGeo, lineGeo };
  }, [graph]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const act = activityRef.current;
    const group = groupRef.current;
    if (group) {
      group.rotation.y = t * 0.04;
      group.rotation.x = Math.sin(t * 0.1) * 0.08;
    }

    // Animate node sizes/colors: breathe at idle, surge with activity.
    const colorAttr = pointGeo.getAttribute("color") as THREE.BufferAttribute;
    for (let i = 0; i < NODE_COUNT; i++) {
      const dist = graph.basePos[i].length();
      // Ripple expands outward from the core based on activity.
      const ripple = Math.sin(t * 3 - dist * 1.5) * 0.5 + 0.5;
      const breath = Math.sin(t * 1.2 + phases[i]) * 0.5 + 0.5;
      const intensity =
        i === 0 ? 1 : 0.25 + breath * 0.4 + act * ripple * 0.9;
      const mix = i === 0 ? CORE : PRIMARY.clone().lerp(SECONDARY, breath * 0.4);
      const c = (i === 0 ? CORE : mix).clone().multiplyScalar(Math.min(1.4, intensity));
      colorAttr.setXYZ(i, c.r, c.g, c.b);
    }
    colorAttr.needsUpdate = true;

    if (pointsRef.current) {
      const mat = pointsRef.current.material as THREE.PointsMaterial;
      mat.size = 0.07 + act * 0.05;
    }
    if (linesRef.current) {
      const mat = linesRef.current.material as THREE.LineBasicMaterial;
      mat.opacity = 0.06 + act * 0.22;
    }
  });

  return (
    <group ref={groupRef}>
      <points ref={pointsRef} geometry={pointGeo}>
        <pointsMaterial
          vertexColors
          size={0.08}
          sizeAttenuation
          transparent
          opacity={0.95}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
      <lineSegments ref={linesRef} geometry={lineGeo}>
        <lineBasicMaterial
          color={PRIMARY}
          transparent
          opacity={0.12}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>
      {/* Always-lit core glow */}
      <mesh>
        <sphereGeometry args={[0.18, 24, 24]} />
        <meshBasicMaterial color={PRIMARY} transparent opacity={0.9} />
      </mesh>
      <pointLight position={[0, 0, 0]} color={PRIMARY} intensity={2} distance={8} />
    </group>
  );
}

function Particles() {
  const { activity } = useZero();
  const ref = useRef<THREE.Points>(null);
  const count = 400;
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 3 + Math.random() * 4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.02;
      (ref.current.material as THREE.PointsMaterial).opacity = 0.1 + activity * 0.3;
    }
  });

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial
        color="#00D2FF"
        size={0.025}
        transparent
        opacity={0.2}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function CameraRig() {
  const { camera } = useThree();
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    camera.position.x = Math.sin(t * 0.05) * 0.6;
    camera.position.y = Math.cos(t * 0.04) * 0.4;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function NeuralBrain() {
  return (
    <div className="fixed inset-0 z-0">
      <Canvas
        camera={{ position: [0, 0, 7], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <color attach="background" args={["#02040A"]} />
        <fog attach="fog" args={["#02040A", 6, 14]} />
        <ambientLight intensity={0.2} />
        <BrainMesh />
        <Particles />
        <CameraRig />
      </Canvas>
      {/* Radial vignette to deepen the void at the edges. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at center, transparent 40%, rgba(2,4,10,0.7) 100%)",
        }}
      />
    </div>
  );
}
