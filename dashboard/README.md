# Swarm Mission Control — Dashboard

A next-generation **Electron desktop app** that visualizes the multi-agent code
generation & review swarm in real time: a live React Flow agent mesh, an
Obsidian-style memory knowledge graph, 3D core visualization, particle fields,
glassmorphism, and neon design — all driven by a WebSocket bridge to the actual
Python swarm.

> Builds and type-checks clean (`vite build` + `tsc --noEmit`, 0 errors).
> Runs fully **with or without** the backend — when the socket is down it falls
> back to an in-browser simulation so the UI is always live and demoable.

---

## Tech stack

| Area | Libraries |
|---|---|
| UI | React 18 · TypeScript · Vite · TailwindCSS v4 · shadcn-style primitives |
| Effects | Custom Aceternity/Magic-UI-style components (spotlight, beams, retro grid, border-travel) · Framer Motion (all transitions) · tsparticles (ambient field) |
| Graphs | @xyflow/react v12 (agent mesh + Obsidian memory graph) · d3-force (graph physics) · d3 (chord/arc diagram) |
| 3D | React Three Fiber · @react-three/drei (rotating core + stars) |
| Charts | Recharts (throughput, duration, sparklines) |
| State | Zustand (agent / metrics / memory / ui stores) |
| Editor | Monaco (`@monaco-editor/react`) for the config editor |
| Desktop | Electron (frameless window, tray, global shortcut, deep links, single-instance) |

> Aceternity UI and Magic UI are copy-paste component collections (not npm
> packages); their effects are implemented as real custom components under
> `src/components/effects/`, matching the design spec. `reagraph` was omitted in
> favor of React Flow for the memory graph (which the brief endorses) to keep the
> WebGL surface stable; the d3-force layout gives the same Obsidian physics.

---

## Run it

### 1. Backend (the real-time bridge to the swarm)

```bash
cd The-system
pip install -r dashboard_backend/requirements.txt   # fastapi, uvicorn, watchdog
python -m uvicorn dashboard_backend.server:app --port 8000
```

This boots the actual swarm (offline deterministic backend), continuously feeds
it tasks, and broadcasts live events over `ws://localhost:8000/ws`. It also
serves the Obsidian memory vault under `dashboard/memory/`.

### 2. Frontend (the desktop app)

```bash
cd dashboard
npm install                 # first time

# Option A — desktop window (Electron):
npm run electron:dev        # starts Vite + opens the frameless Electron window

# Option B — in a browser tab (no Electron):
npm run dev                 # http://localhost:5173
```

**No backend running?** The app still launches — it detects the dead socket and
switches to the built-in `MockEngine`, so every screen stays live with realistic
simulated data (the sidebar shows "simulation"). Start the backend any time and
it reconnects automatically (exponential backoff).

### Build for production

```bash
npm run build               # → dist/  (web bundle)
npm run electron:build      # → release/  (packaged desktop app, needs electron binary)
```

---

## Screens

1. **Dashboard** — left status panel (system status, KPI stat cards w/ sparklines,
   live agent roster), center React Flow **agent mesh** (custom glowing nodes that
   pulse when active, animated particle edges whose thickness = traffic, minimap),
   a 3D core in the corner, and a right **live task feed** (cards slide in/out,
   failures flash red).
2. **Memory** — Obsidian-style force-directed knowledge graph of the markdown
   vault (nodes sized by importance, colored by category), fuzzy search, tag
   filter pills, retro-grid background, and a slide-in drawer that renders the
   note, its tags, linked memories, and edit/delete controls. "New Memory" form.
3. **Agents** — a 3D-tilt card per agent: status ring, live metrics (tasks/min,
   latency, error rate, cache %), a throughput sparkline, pause/resume/restart/
   configure controls, and an expandable color-coded log panel.
4. **Performance** — KPI beam cards, multi-line throughput chart (one line per
   agent), duration-distribution bars, a **d3 chord diagram** of inter-agent flow,
   and a cost-tracking table.
5. **Settings** — connection status, Monaco `config.yaml` editor, model-backend
   selector, accent-color theme picker, vault path, and vault export.

---

## Real-time protocol

The app subscribes to `ws://localhost:8000/ws` and consumes these events
(all defined in `src/lib/types.ts`, produced by `dashboard_backend/server.py`):

`snapshot` · `metric_update` · `agent_status` · `task_update` · `edge_update`
· `log_entry` · `memory_update`

Reconnection is exponential-backoff; a genuine hard outage (no socket, no mock)
shows the full-screen "CONNECTION LOST — RECONNECTING" overlay.

---

## Project layout

```
dashboard/
  electron/        main.js (frameless window, tray, shortcuts) + preload.js
  src/
    components/
      effects/     Spotlight, GridBackground/RetroGrid, ParticleField, Card3D, BeamCard
      nodes/       AgentNode, AnimatedEdge, MemoryNode (React Flow custom types)
      panels/      StatusPanel, AgentRoster, TaskFeed, AgentGraph, StatCard
      charts/      Sparkline, ThroughputChart, DurationBar, ArcDiagram (d3), KpiCard
      memory/      MemoryGraph, MemoryDrawer, MemoryControls (search/tags/new)
      ui/          shadcn-style Button, Card, Input, Badge
      Sidebar, Core3D, ConnectionOverlay
    pages/         Dashboard, MemoryGraphPage, AgentControl, Performance, Settings
    hooks/         useWebSocket (+ mock fallback), useMemory, useAgents, useMetrics
    store/         agentStore, metricsStore, memoryStore, uiStore (Zustand)
    lib/           types, utils, mockData (MockEngine), markdown
dashboard_backend/
  server.py        FastAPI: WebSocket bridge + memory REST API
  memory_manager.py  Obsidian vault indexer (watchdog) + graph builder
dashboard/memory/  the markdown vault (technical/ projects/ tasks/ preferences/)
```
