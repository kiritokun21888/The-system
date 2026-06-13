/**
 * NeuralBrain — ZERO's consciousness, rendered as a multi-region neural cortex.
 *
 * Six color-coded brain regions (prefrontal, motor, sensory, language,
 * hippocampus, brainstem) each cluster their own neurons and pulse with
 * activity. Labels float in 3D showing live neuron counts and firing rates.
 * ZERO's real tools orbit the cortex as a "wired tool" constellation, and
 * particle trails travel the synapses during heavy activity. The whole brain
 * breathes when idle and surges with a ripple from the core when voice fires.
 */
import { Html } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useZero } from "../lib/store";

// --- Brain regions -----------------------------------------------------------

interface Region {
  name: string;
  color: string;
  dir: [number, number, number];
  neurons: number;
}

const REGIONS: Region[] = [
  { name: "PREFRONTAL", color: "#7B2FFF", dir: [0.15, 0.95, 0.25], neurons: 140 },
  { name: "MOTOR CORTEX", color: "#FF3366", dir: [-0.85, 0.45, 0.1], neurons: 190 },
  { name: "SENSORY CORTEX", color: "#00D2FF", dir: [0.9, 0.25, -0.2], neurons: 160 },
  { name: "LANGUAGE", color: "#FF9500", dir: [-0.55, -0.45, 0.6], neurons: 170 },
  { name: "HIPPOCAMPUS", color: "#00FF88", dir: [0.45, -0.7, -0.45], neurons: 160 },
  { name: "BRAINSTEM", color: "#2F8BFF", dir: [0.05, -0.85, 0.35], neurons: 120 },
];

// ZERO's real, wired tools — these orbit the cortex.
const TOOLS = [
  "create_task", "list_tasks", "update_task", "open_application",
  "close_application", "get_system_stats", "open_url", "get_weather",
  "web_search", "remember", "recall", "run_agent", "schedule_reminder",
];

const CORE_COLOR = new THREE.Color("#E8F4FF");
const REGION_RADIUS = 2.25;
const CLUSTER_SPREAD = 1.05;
const NODES_PER_REGION = 40;

interface BrainGraph {
  positions: Float32Array;
  basePos: THREE.Vector3[];
  nodeRegion: number[]; // region index per node, -1 for core
  nodeColors: Float32Array;
  edges: [number, number][];
  edgeColors: Float32Array;
  phases: Float32Array;
}

function buildBrain(): BrainGraph {
  const basePos: THREE.Vector3[] = [new THREE.Vector3(0, 0, 0)]; // core = node 0
  const nodeRegion: number[] = [-1];
  const regionCenters = REGIONS.map((r) =>
    new THREE.Vector3(...r.dir).normalize().multiplyScalar(REGION_RADIUS),
  );

  REGIONS.forEach((_, ri) => {
    const center = regionCenters[ri];
    for (let n = 0; n < NODES_PER_REGION; n++) {
      const offset = new THREE.Vector3(
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2,
      )
        .normalize()
        .multiplyScalar(Math.pow(Math.random(), 0.6) * CLUSTER_SPREAD);
      basePos.push(center.clone().add(offset));
      nodeRegion.push(ri);
    }
  });

  const count = basePos.length;
  const positions = new Float32Array(count * 3);
  const nodeColors = new Float32Array(count * 3);
  basePos.forEach((p, i) => {
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
    const c =
      nodeRegion[i] === -1
        ? CORE_COLOR
        : new THREE.Color(REGIONS[nodeRegion[i]].color);
    nodeColors[i * 3] = c.r;
    nodeColors[i * 3 + 1] = c.g;
    nodeColors[i * 3 + 2] = c.b;
  });

  // Edges: intra-region neighbors, region->core trunks, sparse cross-links.
  const edges: [number, number][] = [];
  for (let i = 1; i < count; i++) {
    let made = 0;
    for (let j = i + 1; j < count && made < 3; j++) {
      if (nodeRegion[i] === nodeRegion[j] && basePos[i].distanceTo(basePos[j]) < 0.9) {
        edges.push([i, j]);
        made++;
      }
    }
    if (Math.random() < 0.12) edges.push([0, i]); // trunk to core
    if (Math.random() < 0.03) {
      const k = 1 + Math.floor(Math.random() * (count - 1));
      if (nodeRegion[k] !== nodeRegion[i]) edges.push([i, k]); // cross-region
    }
  }

  const edgeColors = new Float32Array(edges.length * 6);
  edges.forEach(([a, b], i) => {
    const ca =
      nodeRegion[a] === -1 ? CORE_COLOR : new THREE.Color(REGIONS[nodeRegion[a]].color);
    const cb =
      nodeRegion[b] === -1 ? CORE_COLOR : new THREE.Color(REGIONS[nodeRegion[b]].color);
    edgeColors.set([ca.r, ca.g, ca.b, cb.r, cb.g, cb.b], i * 6);
  });

  const phases = Float32Array.from({ length: count }, () => Math.random() * Math.PI * 2);
  return { positions, basePos, nodeRegion, nodeColors, edges, edgeColors, phases };
}

// --- Region & tool labels ----------------------------------------------------

function RegionLabel({ region, center }: { region: Region; center: THREE.Vector3 }) {
  const { activity } = useZero();
  const [firing, setFiring] = useState(0.8);
  useEffect(() => {
    const id = setInterval(
      () => setFiring(0.4 + Math.random() * 0.6 + activity * 4),
      900,
    );
    return () => clearInterval(id);
  }, [activity]);

  return (
    <Html position={center} center distanceFactor={9} style={{ pointerEvents: "none" }}>
      <div
        style={{
          whiteSpace: "nowrap",
          transform: "translateY(-150%)",
          fontFamily: '"JetBrains Mono", monospace',
        }}
      >
        <div
          style={{
            color: region.color,
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: "0.12em",
            textShadow: `0 0 10px ${region.color}`,
            borderLeft: `2px solid ${region.color}`,
            paddingLeft: 6,
            lineHeight: 1.3,
          }}
        >
          {region.name}
          <div style={{ color: "#9FC4E0", fontSize: 9, fontWeight: 400, letterSpacing: "0.05em" }}>
            {region.neurons} neurons · firing {firing.toFixed(1)}%
          </div>
        </div>
      </div>
    </Html>
  );
}

function ToolLabel({ name, position, color }: { name: string; position: THREE.Vector3; color: string }) {
  return (
    <Html position={position} center distanceFactor={11} style={{ pointerEvents: "none" }}>
      <div
        style={{
          whiteSpace: "nowrap",
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 9,
          color: "#7FB0D8",
          border: `1px solid rgba(0,210,255,0.25)`,
          background: "rgba(2,8,18,0.55)",
          padding: "2px 6px",
          borderRadius: 4,
          letterSpacing: "0.04em",
        }}
      >
        <span style={{ color, marginRight: 4 }}>▸</span>
        {name}
      </div>
    </Html>
  );
}

// --- Tool constellation orbiting the cortex ---------------------------------

function ToolConstellation() {
  const lineRef = useRef<THREE.LineSegments>(null);
  const { tools, positions } = useMemo(() => {
    const positions: THREE.Vector3[] = [];
    const tools = TOOLS.map((name, i) => {
      const angle = (i / TOOLS.length) * Math.PI * 2;
      const tilt = Math.sin(angle * 2) * 0.6;
      const p = new THREE.Vector3(
        Math.cos(angle) * 4.1,
        tilt + Math.sin(angle) * 0.4,
        Math.sin(angle) * 4.1,
      );
      positions.push(p);
      return { name, p, color: REGIONS[i % REGIONS.length].color };
    });
    return { tools, positions };
  }, []);

  const lineGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const arr = new Float32Array(positions.length * 6);
    positions.forEach((p, i) => arr.set([0, 0, 0, p.x, p.y, p.z], i * 6));
    g.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    return g;
  }, [positions]);

  useFrame((state) => {
    if (lineRef.current) {
      const mat = lineRef.current.material as THREE.LineBasicMaterial;
      mat.opacity = 0.05 + (Math.sin(state.clock.elapsedTime * 2) * 0.5 + 0.5) * 0.08;
    }
  });

  return (
    <group>
      <lineSegments ref={lineRef} geometry={lineGeo}>
        <lineBasicMaterial
          color="#00D2FF"
          transparent
          opacity={0.08}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>
      {tools.map((t) => (
        <ToolLabel key={t.name} name={t.name} position={t.p} color={t.color} />
      ))}
    </group>
  );
}

// --- Synaptic particle trails ------------------------------------------------

function ParticleTrails({ graph }: { graph: BrainGraph }) {
  const { activity } = useZero();
  const ref = useRef<THREE.Points>(null);
  const COUNT = 90;

  const { picked, progress, geo } = useMemo(() => {
    const picked = Array.from({ length: COUNT }, () =>
      Math.floor(Math.random() * graph.edges.length),
    );
    const progress = Float32Array.from({ length: COUNT }, () => Math.random());
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(COUNT * 3);
    const col = new Float32Array(COUNT * 3);
    picked.forEach((e, i) => {
      const [a] = graph.edges[e];
      col.set(
        [
          graph.nodeColors[a * 3],
          graph.nodeColors[a * 3 + 1],
          graph.nodeColors[a * 3 + 2],
        ],
        i * 3,
      );
      pos.set([0, 0, 0], i * 3);
    });
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return { picked, progress, geo: g };
  }, [graph]);

  useFrame((_, delta) => {
    const posAttr = geo.getAttribute("position") as THREE.BufferAttribute;
    const speed = 0.3 + activity * 1.6;
    for (let i = 0; i < COUNT; i++) {
      progress[i] += delta * speed * (0.5 + (i % 5) * 0.12);
      if (progress[i] > 1) {
        progress[i] = 0;
        picked[i] = Math.floor(Math.random() * graph.edges.length);
      }
      const [a, b] = graph.edges[picked[i]];
      const t = progress[i];
      posAttr.setXYZ(
        i,
        graph.positions[a * 3] + (graph.positions[b * 3] - graph.positions[a * 3]) * t,
        graph.positions[a * 3 + 1] +
          (graph.positions[b * 3 + 1] - graph.positions[a * 3 + 1]) * t,
        graph.positions[a * 3 + 2] +
          (graph.positions[b * 3 + 2] - graph.positions[a * 3 + 2]) * t,
      );
    }
    posAttr.needsUpdate = true;
    if (ref.current) {
      (ref.current.material as THREE.PointsMaterial).opacity = 0.3 + activity * 0.7;
    }
  });

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial
        vertexColors
        size={0.09}
        sizeAttenuation
        transparent
        opacity={0.5}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

// --- The cortex itself -------------------------------------------------------

function Cortex() {
  const { activity } = useZero();
  const activityRef = useRef(activity);
  activityRef.current = activity;

  const graph = useMemo(buildBrain, []);
  const groupRef = useRef<THREE.Group>(null);
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);

  const regionCenters = useMemo(
    () => REGIONS.map((r) => new THREE.Vector3(...r.dir).normalize().multiplyScalar(REGION_RADIUS)),
    [],
  );

  const { pointGeo, lineGeo } = useMemo(() => {
    const pointGeo = new THREE.BufferGeometry();
    pointGeo.setAttribute("position", new THREE.BufferAttribute(graph.positions.slice(), 3));
    pointGeo.setAttribute("color", new THREE.BufferAttribute(graph.nodeColors.slice(), 3));

    const lineGeo = new THREE.BufferGeometry();
    const linePos = new Float32Array(graph.edges.length * 6);
    graph.edges.forEach(([a, b], i) => {
      linePos.set(
        [
          graph.positions[a * 3], graph.positions[a * 3 + 1], graph.positions[a * 3 + 2],
          graph.positions[b * 3], graph.positions[b * 3 + 1], graph.positions[b * 3 + 2],
        ],
        i * 6,
      );
    });
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
    lineGeo.setAttribute("color", new THREE.BufferAttribute(graph.edgeColors.slice(), 3));
    return { pointGeo, lineGeo };
  }, [graph]);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const act = activityRef.current;
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.045;
      groupRef.current.rotation.x = Math.sin(t * 0.1) * 0.1;
    }

    const colorAttr = pointGeo.getAttribute("color") as THREE.BufferAttribute;
    const count = graph.basePos.length;
    for (let i = 0; i < count; i++) {
      const dist = graph.basePos[i].length();
      const ripple = Math.sin(t * 3 - dist * 1.4) * 0.5 + 0.5;
      const breath = Math.sin(t * 1.3 + graph.phases[i]) * 0.5 + 0.5;
      const base =
        graph.nodeRegion[i] === -1
          ? CORE_COLOR
          : new THREE.Color(REGIONS[graph.nodeRegion[i]].color);
      const intensity =
        graph.nodeRegion[i] === -1 ? 1.4 : 0.45 + breath * 0.4 + act * ripple * 1.1;
      const c = base.clone().multiplyScalar(Math.min(1.6, intensity));
      colorAttr.setXYZ(i, c.r, c.g, c.b);
    }
    colorAttr.needsUpdate = true;

    if (pointsRef.current) {
      (pointsRef.current.material as THREE.PointsMaterial).size = 0.08 + act * 0.06;
    }
    if (linesRef.current) {
      (linesRef.current.material as THREE.LineBasicMaterial).opacity = 0.1 + act * 0.28;
    }
  });

  return (
    <group ref={groupRef}>
      <points ref={pointsRef} geometry={pointGeo}>
        <pointsMaterial
          vertexColors
          size={0.09}
          sizeAttenuation
          transparent
          opacity={0.95}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
      <lineSegments ref={linesRef} geometry={lineGeo}>
        <lineBasicMaterial
          vertexColors
          transparent
          opacity={0.16}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>

      {/* Always-lit core */}
      <mesh>
        <sphereGeometry args={[0.2, 28, 28]} />
        <meshBasicMaterial color="#00D2FF" transparent opacity={0.95} />
      </mesh>
      <pointLight position={[0, 0, 0]} color="#00D2FF" intensity={2.4} distance={9} />

      <ParticleTrails graph={graph} />
      <ToolConstellation />

      {REGIONS.map((r, i) => (
        <RegionLabel key={r.name} region={r} center={regionCenters[i]} />
      ))}
    </group>
  );
}

function CameraRig() {
  const { camera } = useThree();
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    camera.position.x = Math.sin(t * 0.05) * 0.8;
    camera.position.y = Math.cos(t * 0.04) * 0.5;
    camera.lookAt(0, 0, 0);
  });
  return null;
}

// --- HUD overlays (plain DOM) ------------------------------------------------

function HUD() {
  const { agents, activity } = useZero();
  const running = agents.filter((a) => a.state === "running").length;
  const total = 7; // research, draft, monitor, calendar, email, focus, + core
  const pad = (n: number) => n.toString().padStart(2, "0");
  return (
    <>
      {/* LIVE indicator, top-center */}
      <div className="pointer-events-none absolute left-1/2 top-24 -translate-x-1/2 text-center">
        <div className="inline-flex items-center gap-2 rounded border border-danger/40 bg-black/40 px-3 py-1 font-mono text-[11px] tracking-widest">
          <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
          <span className="text-danger">LIVE</span>
          <span className="text-text-primary">{pad(running)} / {pad(total)}</span>
        </div>
        <div className="mt-2 font-display text-[10px] tracking-[0.4em] text-text-dim">
          THIRTY&nbsp;-&nbsp;THOUSAND&nbsp;SYNAPSES
        </div>
      </div>

      {/* Feature-layer caption, bottom-center (behind command bar) */}
      <div className="pointer-events-none absolute bottom-28 left-1/2 -translate-x-1/2 text-center">
        <div className="font-display text-[10px] tracking-[0.35em] text-primary/70">
          FEATURE LAYER · {TOOLS.length} REAL TOOLS WIRED
        </div>
        <div className="mx-auto mt-1 h-[2px] w-40 overflow-hidden rounded bg-border-glow">
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${30 + activity * 70}%`, boxShadow: "0 0 8px #00D2FF" }}
          />
        </div>
      </div>
    </>
  );
}

export default function NeuralBrain() {
  return (
    <div className="fixed inset-0 z-0">
      <Canvas
        camera={{ position: [0, 0, 8], fov: 62 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <color attach="background" args={["#02040A"]} />
        <fog attach="fog" args={["#02040A", 7, 17]} />
        <ambientLight intensity={0.25} />
        <Cortex />
        <CameraRig />
      </Canvas>
      <HUD />
      {/* Radial vignette deepens the void at the edges. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at center, transparent 38%, rgba(2,4,10,0.78) 100%)",
        }}
      />
    </div>
  );
}
