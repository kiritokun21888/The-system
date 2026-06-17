// Self-contained mock swarm. Produces the same event shapes as the FastAPI
// backend so the UI is always live and demoable, even with nothing running.

import type {
  AgentStatus,
  EdgeTraffic,
  LogEntry,
  MemoryGraphT,
  MemoryRecord,
  MetricsSnapshot,
  SnapshotData,
  TaskRow,
} from "./types";

const PIPELINE = ["spec_parser", "coder", "test_writer", "test_runner", "reviewer"];
const ICONS: Record<string, string> = {
  spec_parser: "parser",
  coder: "code",
  test_writer: "tests",
  test_runner: "play",
  reviewer: "shield",
};

const PROMPTS = [
  "Write a function that returns the nth fibonacci number",
  "Implement an is_prime primality test",
  "Compute the greatest common divisor of two numbers",
  "Check whether a string is a palindrome",
  "Sort a list of numbers ascending",
  "Implement binary search over a sorted list",
  "Implement Kadane's maximum subarray sum",
  "Generate fizzbuzz output up to n",
  "Check whether two strings are anagrams",
  "Build an optimal multi-depot vehicle routing solver",
];

let SEQ = 0;
const rid = () => `mock-${(SEQ++).toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
const rand = (a: number, b: number) => a + Math.random() * (b - a);
const pick = <T,>(arr: T[]) => arr[Math.floor(Math.random() * arr.length)];

interface SimTask {
  row: TaskRow;
  stageIdx: number;
  isUnknown: boolean;
  nextAt: number;
}

export type MockEmit = (type: string, data: unknown) => void;

/** A small deterministic-ish simulation of the swarm for offline demos. */
export class MockEngine {
  private agents: Record<string, AgentStatus> = {};
  private tasks: SimTask[] = [];
  private done: TaskRow[] = [];
  private metrics: MetricsSnapshot;
  private timer: number | null = null;
  private started = Date.now();
  private emit: MockEmit;

  constructor(emit: MockEmit) {
    this.emit = emit;
    for (const name of PIPELINE) {
      this.agents[name] = {
        name,
        icon: ICONS[name],
        status: "idle",
        active: 0,
        processed: 0,
        failures: 0,
        error_rate: 0,
        avg_latency: name === "test_runner" ? 0.04 : rand(0.25, 0.4),
        per_minute: 0,
        cache_hits: 0,
        cost_usd: 0,
        current_task: "",
      };
    }
    this.metrics = {
      uptime_seconds: 0,
      queue_depth: 0,
      tasks_submitted: 0,
      tasks_active: 0,
      tasks_completed: 0,
      tasks_escalated: 0,
      tasks_aborted: 0,
      total_cost_usd: 0,
      agents: {},
    };
  }

  start() {
    this.emit("snapshot", this.snapshot());
    this.emit("memory_update", { graph: MOCK_GRAPH, memories: MOCK_MEMORIES });
    this.timer = window.setInterval(() => this.tick(), 250);
  }

  stop() {
    if (this.timer) window.clearInterval(this.timer);
    this.timer = null;
  }

  submit(prompt: string, priority = 2) {
    this.spawn(prompt, priority);
  }

  private spawn(prompt?: string, priority?: number) {
    const p = prompt ?? pick(PROMPTS);
    const isUnknown = p.includes("vehicle routing");
    const row: TaskRow = {
      id: rid(),
      prompt: p,
      priority: priority ?? Math.ceil(rand(1, 5)),
      status: "running",
      stage: PIPELINE[0],
      loops: {},
      elapsed: 0,
      updated: Date.now() / 1000,
      review_score: null,
      pass_rate: null,
    };
    this.tasks.push({ row, stageIdx: 0, isUnknown, nextAt: Date.now() + rand(300, 700) });
    this.metrics.tasks_submitted++;
    this.log("info", "swarm", `task submitted`, "");
  }

  private tick() {
    const now = Date.now();
    this.metrics.uptime_seconds = (now - this.started) / 1000;

    // Occasionally spawn new work to keep the feed alive.
    if (this.tasks.length < 5 && Math.random() < 0.25) this.spawn();

    for (const t of [...this.tasks]) {
      const stage = PIPELINE[t.stageIdx];
      // reset active flags
      for (const a of Object.values(this.agents)) a.active = 0;
      this.agents[stage].active = 1;
      this.agents[stage].status = "running";
      this.agents[stage].current_task = t.row.prompt;
      t.row.elapsed = (now - (t.row.updated * 1000 - t.row.elapsed * 1000)) / 1000;

      if (now < t.nextAt) continue;

      // advance this stage
      const a = this.agents[stage];
      a.processed++;
      a.cache_hits += Math.random() < 0.3 ? 1 : 0;
      this.bumpRate(stage);
      this.log(stageLevel(stage), "orchestrator", routeMsg(stage), stage);

      // test_runner: buggy-first tasks fail once
      if (stage === "test_runner") {
        const loops = t.row.loops["test_fix_loop"] ?? 0;
        const buggy = t.row.prompt.includes("fibonacci") ||
          t.row.prompt.includes("binary search") ||
          t.row.prompt.includes("Kadane");
        if (buggy && loops === 0) {
          a.failures++;
          this.recompute(stage);
          t.row.loops["test_fix_loop"] = 1;
          t.stageIdx = 1; // back to coder
          t.nextAt = now + rand(300, 600);
          this.log("warning", "orchestrator", "tests failed → routing to coder", "test_runner");
          continue;
        }
        t.row.pass_rate = 1.0;
      }

      // reviewer: unknown task never converges → escalate
      if (stage === "reviewer") {
        if (t.isUnknown) {
          const it = (t.row.loops["review_refine_loop"] ?? 0) + 1;
          t.row.loops["review_refine_loop"] = it;
          t.row.review_score = 0.4;
          if (it >= 4) {
            this.finish(t, "escalated");
          } else {
            t.stageIdx = 1;
            t.nextAt = now + rand(300, 600);
            this.log("info", "orchestrator", `review ${it}/3 below threshold → refining`, "reviewer");
          }
          continue;
        }
        t.row.review_score = 1.0;
        this.finish(t, "completed");
        continue;
      }

      // trivial early termination after tests pass
      const trivial = /reverse|factorial|gcd|vowel|sum a list/i.test(t.row.prompt);
      if (stage === "test_runner" && trivial) {
        this.finish(t, "completed");
        continue;
      }

      t.stageIdx++;
      t.nextAt = now + rand(300, 750);
      t.row.stage = PIPELINE[Math.min(t.stageIdx, PIPELINE.length - 1)];
      t.row.updated = now / 1000;
    }

    // mark idle agents
    const activeStages = new Set(this.tasks.map((t) => PIPELINE[t.stageIdx]));
    for (const [name, a] of Object.entries(this.agents)) {
      if (!activeStages.has(name)) {
        a.active = 0;
        a.status = a.failures && a.error_rate > 0.4 ? "error" : "idle";
        a.current_task = "";
      }
    }
    this.metrics.tasks_active = this.tasks.length;
    this.metrics.queue_depth = Math.max(0, this.tasks.length - 3);

    this.emit("metric_update", this.metricsSnapshot());
    this.emit("agent_status", Object.values(this.agents));
    this.emit("task_update", this.feed());
    this.emit("edge_update", this.edges());
  }

  private finish(t: SimTask, status: string) {
    t.row.status = status;
    t.row.stage = "";
    t.row.updated = Date.now() / 1000;
    this.done.unshift({ ...t.row });
    this.done = this.done.slice(0, 20);
    this.tasks = this.tasks.filter((x) => x !== t);
    if (status === "completed") this.metrics.tasks_completed++;
    else if (status === "escalated") this.metrics.tasks_escalated++;
    this.log(status === "completed" ? "info" : "warning", "orchestrator",
      status === "completed" ? "task completed" : "task escalated to human review", "");
  }

  private bumpRate(stage: string) {
    const a = this.agents[stage];
    a.per_minute = Math.min(60, a.per_minute + rand(0.5, 1.5));
  }
  private recompute(stage: string) {
    const a = this.agents[stage];
    a.error_rate = a.processed ? a.failures / a.processed : 0;
  }

  private feed(): TaskRow[] {
    const live = this.tasks.map((t) => t.row);
    return [...live, ...this.done].slice(0, 25);
  }

  private edges(): EdgeTraffic[] {
    const e: EdgeTraffic[] = [];
    for (let i = 0; i < PIPELINE.length - 1; i++) {
      e.push({ source: PIPELINE[i], target: PIPELINE[i + 1], volume: this.agents[PIPELINE[i + 1]].processed });
    }
    e.push({ source: "test_runner", target: "coder", volume: this.agents.test_runner.failures, feedback: true });
    e.push({ source: "reviewer", target: "coder", volume: this.metrics.tasks_escalated, feedback: true });
    return e;
  }

  private metricsSnapshot(): MetricsSnapshot {
    const agents: MetricsSnapshot["agents"] = {};
    for (const [name, a] of Object.entries(this.agents)) {
      agents[name] = {
        processed: a.processed,
        failures: a.failures,
        error_rate: a.error_rate,
        avg_latency: a.avg_latency,
        per_minute: a.per_minute,
        cost_usd: a.cost_usd,
        tokens_in: a.processed * 120,
        tokens_out: a.processed * 60,
        cache_hits: a.cache_hits,
      };
    }
    return { ...this.metrics, agents };
  }

  private snapshot(): SnapshotData {
    return {
      metrics: this.metricsSnapshot(),
      agents: Object.values(this.agents),
      tasks: this.feed(),
      edges: this.edges(),
      pipeline: PIPELINE,
      connections: 0,
    };
  }

  private log(level: string, logger: string, msg: string, agent: string) {
    const entry: LogEntry = {
      level: level.toUpperCase(),
      logger,
      msg,
      agent,
      ts: new Date().toISOString().slice(11, 19),
    };
    this.emit("log_entry", entry);
  }
}

function stageLevel(stage: string): string {
  return stage === "test_runner" ? "info" : "info";
}
function routeMsg(stage: string): string {
  const m: Record<string, string> = {
    spec_parser: "spec parsed; advancing",
    coder: "code generated; advancing",
    test_writer: "tests written; advancing",
    test_runner: "executing tests",
    reviewer: "reviewing quality",
  };
  return m[stage] ?? "processing";
}

// ---- Static mock memory vault (mirrors the seeded backend vault) ----
export const MOCK_MEMORIES: MemoryRecord[] = [
  mem("mission-control", "Mission Control Dashboard", "project", ["dashboard", "electron", "ui"], 10,
    ["websocket-bridge", "obsidian-memory"],
    "Next-gen Electron mission-control UI for the multi-agent swarm. React 18 + React Flow live agent graph + Obsidian-style memory graph, glassmorphism, cyan/violet neon design system."),
  mem("websocket-bridge", "WebSocket Event Bridge", "project", ["dashboard", "backend", "realtime"], 8,
    ["mission-control"],
    "FastAPI backend polls the live Swarm metrics + task state and broadcasts agent_status, task_update, metric_update, log_entry, and memory_update events over ws://localhost:8000/ws."),
  mem("obsidian-memory", "Obsidian Memory Vault", "project", ["memory", "markdown", "graph"], 8,
    ["mission-control", "websocket-bridge"],
    "Markdown vault where each .md file is one memory with YAML frontmatter. A watchdog observer reindexes on change; the graph links files by explicit linked ids and shared tags."),
  mem("spec-parser-arch", "SpecParser Architecture", "technical", ["agents", "spec", "validation"], 8,
    ["coder-refine-loop", "model-routing"],
    "The SpecParser converts a free-form prompt into a structured Spec (function name, signature, requirements, examples). Uses the cheaper validation model; emits DataValidationError on empty prompts."),
  mem("coder-refine-loop", "Coder Refinement Loop", "technical", ["agents", "coder", "feedback"], 9,
    ["spec-parser-arch", "test-fix-loop"],
    "The Coder generates code and is the refinement target for both feedback loops. Its cache key embeds the attempt counter so refinements are never short-circuited by the cache."),
  mem("test-fix-loop", "Test-Fix Feedback Loop", "technical", ["feedback", "testing", "loops"], 9,
    ["coder-refine-loop", "review-refine-loop"],
    "When the TestRunner reports a failing test, the orchestrator routes back to the Coder with the failing traces. Converges at pass_rate 1.0; hard cap of 4 iterations is the divergence guard."),
  mem("review-refine-loop", "Review-Refine Loop", "technical", ["feedback", "review", "loops"], 7,
    ["test-fix-loop"],
    "The Reviewer scores code quality; below 0.75 routes back to the Coder. Capped at 3 iterations, then escalates to human review."),
  mem("model-routing", "Model Cost Routing", "technical", ["models", "cost", "optimization"], 7,
    ["spec-parser-arch"],
    "Generation agents (Coder, TestWriter) use claude-opus-4-8; validation agents (SpecParser, Reviewer) use claude-haiku-4-5. Prompts are cached."),
  mem("task-fib-fixed", "Fibonacci: bug auto-fixed", "task", ["completed", "feedback", "testing"], 6,
    ["test-fix-loop"],
    "Task nth fibonacci completed. First attempt returned b (off-by-one); the test-fix loop caught it and the second attempt passed all tests. Final review score 1.0."),
  mem("task-vrp-escalated", "Vehicle routing: escalated", "task", ["escalated", "review"], 5,
    ["review-refine-loop"],
    "Task multi-depot vehicle routing solver could not reach the quality threshold after 3 review-refine iterations and was escalated to human review with a full context bundle."),
  mem("pref-design", "Design Preferences", "preference", ["ui", "design", "theme"], 6,
    ["mission-control"],
    "Operator prefers a dark void background, cyan/violet neon accents, Orbitron for display type, glassmorphism panels, and 60fps animations."),
  mem("pref-backend", "Backend Preference", "preference", ["models", "cost"], 5,
    ["model-routing"],
    "Default to the deterministic offline backend for demos (zero cost, reproducible). Switch to the anthropic backend only when real generation is required."),
];

const CAT_COLOR: Record<string, string> = {
  technical: "#00D2FF",
  project: "#7B2FFF",
  task: "#00FF88",
  preference: "#FF9500",
  error: "#FF3366",
};

export const MOCK_GRAPH: MemoryGraphT = buildGraph(MOCK_MEMORIES);

function mem(
  id: string, title: string, category: string, tags: string[],
  importance: number, linked: string[], content: string
): MemoryRecord {
  const now = new Date().toISOString();
  return { id, title, category, tags, importance, linked, content, created: now, updated: now };
}

function buildGraph(mems: MemoryRecord[]): MemoryGraphT {
  const ids = new Set(mems.map((m) => m.id));
  const nodes = mems.map((m) => ({
    id: m.id, title: m.title, category: m.category,
    color: CAT_COLOR[m.category] ?? "#00D2FF", importance: m.importance, tags: m.tags,
  }));
  const seen = new Set<string>();
  const edges: MemoryGraphT["edges"] = [];
  const add = (a: string, b: string, kind: "explicit" | "tag") => {
    if (a === b || !ids.has(a) || !ids.has(b)) return;
    const key = [a, b].sort().join("__");
    if (seen.has(key)) return;
    seen.add(key);
    edges.push({ id: key, source: key.split("__")[0], target: key.split("__")[1], kind });
  };
  for (const m of mems) for (const l of m.linked) add(m.id, l, "explicit");
  const byTag: Record<string, string[]> = {};
  for (const m of mems) for (const t of m.tags) (byTag[t] ??= []).push(m.id);
  for (const members of Object.values(byTag))
    for (let i = 0; i < members.length; i++)
      for (let j = i + 1; j < members.length; j++) add(members[i], members[j], "tag");
  return { nodes, edges };
}
