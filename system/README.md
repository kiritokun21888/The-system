# Multi-Agent Code Generation & Review System

A production-grade, multi-agent orchestration system where specialized agents
collaborate to turn a natural-language coding task into **validated, tested,
reviewed code** — with validation, feedback loops, failure recovery, and
scalability built in.

It runs **fully offline** out of the box (a deterministic LLM backend serves a
task catalog so the whole pipeline, including real test execution, runs with no
API key and reproducibly), and switches to the **real Claude API**
(`claude-opus-4-8` for generation, `claude-haiku-4-5` for validation) by
flipping one config value.

```
python main.py demo                                   # run the built-in batch
python main.py "Write a function to reverse a string" # run one task
python main.py resume                                 # resume checkpointed tasks
python -m pytest -q                                   # run the test suite (36 tests)
```

---

## DELIVERABLE 1 — Architecture Flowchart

```
                                  ┌─────────────────────────────────────────────┐
                                  │ FAILURE HANDLER (unified, all categories)   │
                                  │  TRANSIENT→backoff  DATA→spec repair         │
                                  │  LOGIC→refine       CRITICAL→freeze+alert    │
                                  │  TIMEOUT→checkpoint                          │
                                  └───────────────▲──────────────┬──────────────┘
                                   any exception  │              │ recover / escalate
                                                  │              ▼
 [INPUT: Task{prompt,priority}]                   │      [HUMAN REVIEW]  (escalate)
        │                                         │      [ABORT]         (give up)
        ▼ (priority queue 1..5)                   │      [FROZEN]        (critical)
 ┌──────────────────┐   spec        ┌─────────────┴───┐   [CHECKPOINT]   (timeout, resumable)
 │ ORCHESTRATOR     │──────────────▶│ SpecParser      │
 │ (router + state) │               │  role: validate │
 │                  │◀──────────────│  -> Spec        │
 └──────────────────┘   AgentOutput └────────┬────────┘
        │  {spec.function_name?} ─── NO ──────┘ (DATA: empty/malformed prompt → repair/retry)
        │ YES
        ▼  ════════ PARALLEL FAN-OUT (no inter-dependency) ════════
   ┌─────────────────────┐                      ┌─────────────────────┐
   │ Coder  role:generate│   code               │ TestWriter role:gen │  tests
   │  -> code (module)   │                      │  -> test module     │
   └──────────┬──────────┘                      └──────────┬──────────┘
              │  code + tests                              │
              ▼                                            │
        ┌───────────────────────────┐                     │
        │ TestRunner  role: none    │◀────────────────────┘
        │  executes code vs tests   │
        │  -> pass/fail + report    │
        └────────────┬──────────────┘
                     │
              {all tests pass?}
            ┌────────┴─────────┐
         NO │                  │ YES
            ▼                  ▼
   ╔═══════════════════╗   {spec.trivial AND early_termination?}
   ║ TEST-FIX LOOP     ║      ┌──────────┴──────────┐
   ║ failure context → ║   YES│                     │ NO
   ║ Coder (refine)    ║      ▼                     ▼
   ║ max 4 iterations  ║   [COMPLETE]        ┌──────────────────┐  review
   ║ diverge→ESCALATE  ║   (review skipped)  │ Reviewer         │
   ╚═════════▲═════════╝                     │  role: validate  │
             │ regenerated code              │  -> score+issues │
             └───────────────────────────────└────────┬─────────┘
                                                       │
                                            {score >= quality_threshold?}
                                          ┌────────────┴────────────┐
                                       NO │                         │ YES
                                          ▼                         ▼
                                ╔═══════════════════╗          [COMPLETE]
                                ║ REVIEW-REFINE LOOP║          (validated code,
                                ║ issues → Coder    ║           tests, review)
                                ║ max 3 iterations  ║
                                ║ diverge→ESCALATE  ║
                                ╚═════════▲═════════╝
                                          │ regenerated code → re-test → re-review
                                          └──────────────── (back to Coder)

ENTRY:  Task enters the priority queue → a worker hands it to the Orchestrator.
EXITS:  COMPLETE (success) · ESCALATE (human review) · ABORT (give up) ·
        FROZEN (critical, preserved) · CHECKPOINT (timeout, resumable).
EVERY agent failure routes through the FAILURE HANDLER (top) which classifies,
logs, preserves state, alerts, recovers, or escalates.
```

---

## DELIVERABLE 2 — Agent Specifications

All agents inherit `BaseAgent` and implement
`async def process(self, task, state) -> AgentOutput`. The base class provides
caching, per-agent timeout, transient backoff, metrics, cost accounting, and
turns any raised exception into a **classified** failure output (no silent
failures). `state` accompanies `task` so feedback-loop agents can read
accumulated artifacts (spec, prior code, failure context).

### Agent: SpecParser  (`agents/spec_parser.py`)
- **Role**: Convert the natural-language prompt into a structured, validated `Spec`.
- **Trigger**: First stage of the pipeline (task dequeued).
- **Inputs**: `Task{prompt: str, language: str, priority: int}`.
- **Processing**: Validate prompt length → LLM (validation model) → parse JSON → build `Spec`.
- **Decision logic**: prompt < 3 chars → `DataValidationError`; spec missing `function_name` → `DataValidationError`; quality = 0.4 + 0.3·has_requirements + 0.2·has_examples + 0.1·has_signature.
- **Outputs**: `AgentOutput{payload: {spec}, quality_score}`.
- **Passes to**: Coder + TestWriter (parallel) when `quality_score ≥ 0.6`.
- **Failure modes**: empty/short prompt (DATA); malformed LLM JSON (DATA); LLM transient (TRANSIENT).
- **On failure**: DATA → retry parse (≤2); TRANSIENT → backoff retry; exhaustion → escalate.
- **Performance target**: ~50–500 ms (validation model); cacheable on prompt.
- **Scalability**: stateless; cache keyed on prompt → identical prompts free.

### Agent: Coder  (`agents/coder.py`)
- **Role**: Produce (and refine) the implementation that satisfies the `Spec`.
- **Trigger**: After SpecParser; and on every feedback-loop refinement.
- **Inputs**: `state.artifacts.spec`, `state.failure_reason` (refinement context), combined loop attempt.
- **Processing**: Build a prompt from the spec + failure feedback → LLM (generation model) → extract `code`.
- **Decision logic**: no spec → DATA; empty code → DATA; quality = 0.6·has_def + 0.1·has_docstring. The cache key embeds the attempt counter so refinements are **never** short-circuited by the cache.
- **Outputs**: `AgentOutput{payload: {code, language}}`.
- **Passes to**: TestRunner (via the pipeline).
- **Failure modes**: missing spec (DATA); empty code (DATA); LLM transient (TRANSIENT).
- **On failure**: classified + routed by the orchestrator; refinement target of both loops.
- **Performance target**: ~1–8 s (generation model); **bottleneck — load-balanced (2 instances)**.
- **Scalability**: stateless; round-robin dispatcher fans requests across instances.

### Agent: TestWriter  (`agents/test_writer.py`)
- **Role**: Write an executable test module (plain-`assert` `test_*` functions) encoding the spec.
- **Trigger**: After SpecParser (runs in parallel with Coder on the first pass).
- **Inputs**: `state.artifacts.spec`.
- **Processing**: Prompt from spec → LLM (generation model) → extract `test_code`.
- **Decision logic**: no spec → DATA; no `def test` → DATA; quality = 0.4 + 0.2·n_tests.
- **Outputs**: `AgentOutput{payload: {test_code, n_tests}}`.
- **Passes to**: TestRunner.
- **Failure modes**: missing spec (DATA); no tests produced (DATA); transient.
- **On failure**: classified + routed; cached on the spec (re-runs in refinement loops are cache hits).
- **Performance target**: ~1–5 s; cacheable on spec.
- **Scalability**: stateless; single instance (not a bottleneck — output is cached).

### Agent: TestRunner  (`agents/test_runner.py`)  — *not an LLM agent*
- **Role**: Produce the objective pass/fail signal by **executing** code against tests.
- **Trigger**: After code + tests exist.
- **Inputs**: `state.artifacts.code`, `state.artifacts.test_code`.
- **Processing**: Write `solution.py` + `test_solution.py` + harness to a temp dir → run in a subprocess with a hard timeout → parse JSON report.
- **Decision logic**: import/syntax error → LOGIC; any failing test → LOGIC (with failing traces as context); all pass → SUCCESS, quality = pass-rate.
- **Outputs**: `AgentOutput{payload: {report, pass_rate}}` (stored on success **and** failure).
- **Passes to**: Reviewer (on pass) or Coder (on fail, via the test-fix loop).
- **Failure modes**: missing artifacts (DATA); failing tests (LOGIC); slow code (TIMEOUT).
- **On failure**: LOGIC → test-fix loop → Coder; TIMEOUT → checkpoint.
- **Performance target**: subprocess + hard timeout (config 30 s); **bottleneck — 2 instances**.
- **Scalability**: stateless; each run is fully isolated in its own temp dir.

### Agent: Reviewer  (`agents/reviewer.py`)
- **Role**: Holistic quality verdict on code that already passes its tests.
- **Trigger**: After tests pass (unless skipped by early termination).
- **Inputs**: `state.artifacts.code`, `state.artifacts.pass_rate`.
- **Processing**: LLM (validation model) judges quality → `{quality_score, issues, approved}`.
- **Decision logic**: stub code → decisive 0.4 reject; else 0.6 + 0.2·docstring + 0.2·tests_passing.
- **Outputs**: `AgentOutput{payload: {quality_score, issues, approved}}`.
- **Passes to**: COMPLETE (≥ threshold) or Coder (below threshold, via review-refine loop).
- **Failure modes**: missing code (DATA); transient.
- **On failure**: classified + routed; cached on the exact code.
- **Performance target**: ~0.5–3 s (validation model — cost optimization).
- **Scalability**: stateless; cached on code.

---

## DELIVERABLE 3 — Routing Logic

The `Orchestrator` (`agents/orchestrator.py`) is the central router and state
manager. For each agent output it evaluates completion criteria against the
configured thresholds and routes to the next agent, a feedback loop, or a
terminal state — logging every decision with a timestamp and reason.

```python
def route(stage, output, state):
    if output.is_failure:
        return route_failure(stage, output, state)   # by FailureCategory
    if output.quality_score >= threshold(stage):
        return route_success(stage, state)            # advance / complete / early-term
    return route_quality_miss(stage, output, state)   # refine or retry

# route_quality_miss (the spec's canonical shape):
#   if output.quality_score >= threshold:  route_to(NEXT_AGENT)
#   elif retry_count < MAX_RETRIES:         route_to(REFINEMENT_AGENT, context=reason)
#   else:                                   escalate_to(HUMAN_REVIEW, context=full_trace)
```

- **Tracks state** across the whole pipeline in `TaskState`, persisted after
  every step (`StateManager`) → stop/resume without data loss.
- **Enforces retry limits** per agent (`agents.<name>.max_retries`, default 3)
  and per-loop iteration caps.
- **Escalates** to human review on exhaustion (`router.escalate_on_exhaustion`),
  preserving a full context bundle.
- **Logs** every routing decision into `state.routing_log`
  (`{timestamp, stage, decision, reason, quality_score}`) and to the structured
  logger — a complete audit trail.

---

## DELIVERABLE 4 — Feedback Loops

| | **Test-Fix Loop** | **Review-Refine Loop** |
|---|---|---|
| **Trigger** | TestRunner reports any failing test (LOGIC) | Reviewer score < `quality_threshold` (0.75) |
| **Agents** | TestRunner → Coder → TestRunner | Reviewer → Coder → TestRunner → Reviewer |
| **What changes** | Coder regenerates code using the failing-test traces as `failure_reason` | Coder regenerates code using the reviewer's issues as `failure_reason` |
| **Convergence** | `pass_rate == 1.0` (`convergence_pass_rate`) | `score ≥ convergence_quality` (0.75) |
| **Divergence protection** | hard cap `max_iterations: 4` | hard cap `max_iterations: 3` |
| **Max iterations** | 4 | 3 |
| **Exit on success** | → Reviewer (or COMPLETE if early-terminated) | → COMPLETE |
| **Exit on failure** | → ESCALATE (human review, full trace) | → ESCALATE (human review, full trace) |

Both loops are **counter-bounded** (`state.loop_counts`), so neither can run
forever — the convergence guarantee. The attempt counter feeds the Coder's
cache key, so each iteration is a genuine fresh generation.

---

## DELIVERABLE 5 — Failure Handling System

`core/failure_handler.py` is the unified layer. Every category and its action:

| Category | Trigger | Action |
|---|---|---|
| **TRANSIENT** | timeout / rate-limit / temporary unavailability (`TransientLLMError`) | exponential backoff retry **1s, 2s, 4s, 8s** |
| **DATA** | malformed input, missing fields, type mismatch (`DataValidationError`) | route to **spec repair** (re-parse), or retry the parser |
| **LOGIC** | agent produced output that failed a quality/test check | route to **Coder** (refinement) with failure context |
| **CRITICAL** | crash / unrecoverable / corruption (`CriticalAgentError`, any unknown) | **freeze** task state, **alert** human, **preserve** full bundle |
| **TIMEOUT** | task exceeded `system.task_timeout_seconds` | **checkpoint** state → resumable / restartable |

For **every** failure the layer: **logs** (agent, type, input, error, timestamp);
**preserves** the complete `TaskState`; **notifies** via configurable channels
(`log` / `webhook` / `email`); **recovers** automatically by category; and
**escalates** to human review with a full context bundle when recovery is
exhausted. Unknown exceptions default to CRITICAL — nothing fails silently.

---

## DELIVERABLE 6 — Optimization Layer

- **Parallel execution** — `optimization.parallel_execution.groups` lists
  stages with no mutual dependency; the orchestrator runs them with
  `asyncio.gather`. Default group: `[coder, test_writer]` (both depend only on
  the spec). Automatically disabled during refinement loops (only the Coder
  re-runs). **Dependency graph:**
  ```
  SpecParser ─┬─▶ Coder ──────┐
              └─▶ TestWriter ──┴─▶ TestRunner ──▶ Reviewer
              (Coder ∥ TestWriter — independent)
  ```
- **Caching** — `core/cache.py`, per-agent TTL (`agents.<name>.cache_ttl_seconds`).
  Identical inputs return cached output; keys are stable hashes (sorted JSON),
  so there are no silent misses. TestRunner sets TTL 0 (never cache execution).
- **Load balancing** — bottleneck agents (`optimization.load_balancing`) are
  instantiated N times behind a `RoundRobinDispatcher`. Default: `coder: 2`,
  `test_runner: 2`.
- **Priority queue** — tasks enter at priority 1 (highest)..5; higher priority
  is dequeued first, preempting lower-priority work at the queue boundary.
- **Early termination** — when the spec is `trivial` and all tests pass, the
  Reviewer stage is **skipped** (`optimization.early_termination`), and the task
  completes immediately. The skip condition is logged.
- **Token/cost optimization** — prompts are cached; **validation tasks**
  (SpecParser, Reviewer) use the smaller `claude-haiku-4-5`; **generation tasks**
  (Coder, TestWriter) use `claude-opus-4-8`; cost is logged per task and per
  agent (the dashboard's `$` column and `total_cost_usd`).

---

## DELIVERABLE 7 — Scalability Design

- **Horizontal scaling** — every agent is **stateless**; all state lives in the
  central `StateManager` (SQLite locally; swap for Redis — the interface is
  `save`/`load`/`delete`/`all_ids`). Any worker can pick up any task, and a
  brand-new orchestrator can **resume** a checkpointed task (see
  `test_checkpointed_task_can_resume`).
- **Queue-based routing** — agents are dispatched from an `asyncio`
  `PriorityQueue` (`core/queue_manager.py`), not direct calls; the minimal
  `put`/`get`/`depth` interface swaps cleanly for Redis Queue / RabbitMQ.
- **Monitoring** — every agent emits metrics (tasks/min, avg latency, error
  rate, queue depth, tokens, cost); `core/metrics.py` renders a live terminal
  dashboard.
- **Configuration** — **every** threshold, limit, timeout, retry count, and
  model choice lives in `config.yaml`. No hardcoded operational values anywhere.

---

## DELIVERABLE 8 — Code Layout

```
system/
  main.py                 # entrypoint: queue + worker pool + dashboard + CLI
  config.yaml             # all configurable parameters (single source of truth)
  requirements.txt
  README.md
  conftest.py             # pytest fixtures / path setup
  pytest.ini
  agents/
    base_agent.py         # abstract base: caching, timeout, metrics, failure capture
    orchestrator.py       # central router + state manager + AgentRegistry
    spec_parser.py        # Spec extraction
    coder.py              # code generation + refinement
    test_writer.py        # test synthesis
    test_runner.py        # subprocess test execution (objective signal)
    reviewer.py           # quality review
  core/
    config.py             # YAML config loader (dotted access)
    logger.py             # structured JSON logging
    metrics.py            # metrics + terminal dashboard
    state_manager.py      # SQLite task-state persistence
    queue_manager.py      # asyncio priority queue
    failure_handler.py    # unified failure handling (5 categories)
    cache.py              # TTL cache
    llm_client.py         # pluggable LLM (deterministic | anthropic)
    catalog.py            # offline task catalog (drives the deterministic backend)
    json_util.py          # robust JSON extraction from model output
    load_balancer.py      # round-robin dispatcher for bottleneck agents
  models/
    task.py               # Task, TaskState, Spec
    agent_output.py       # AgentOutput, OutputStatus, FailureCategory
  tests/
    test_agents.py        # unit tests for every agent (incl. every failure path)
    test_routing.py       # integration tests for routing + feedback loops
    test_failure.py       # failure-scenario tests (every category)
```

---

## Setup & Run

```bash
cd system
pip install -r requirements.txt          # PyYAML (+ pytest for the suite)

# Offline (default) — no API key needed:
python main.py demo                       # 5 demo tasks: convergence, early-term, escalation
python main.py "Implement an is_prime primality test"

# Real Claude API:
#   1. set llm.backend: "anthropic" in config.yaml
#   2. export ANTHROPIC_API_KEY=sk-ant-...
python main.py "Write a function that flattens a nested list"

# Tests:
python -m pytest -q                       # 36 tests, ~1.5s, fully offline
```

### Adding a new agent (no core changes)
1. Create `agents/<name>.py` with a `class implementing BaseAgent._run`.
2. Register it under `agents:` in `config.yaml` (`module`, `class_name`,
   thresholds, model role, instances).
3. If it joins the main flow, add its stage to `pipeline.order`.

The `AgentRegistry` imports and instantiates it from config — the orchestrator,
router, and feedback machinery need no edits.

---

## Quality Bar — how each guarantee is met

- **No silent failures** — `BaseAgent.process` converts every exception into a
  classified `AgentOutput`; unknown errors default to CRITICAL.
- **No infinite loops** — every feedback loop is counter-bounded by a configured
  `max_iterations`; exceeding it escalates.
- **Full audit trail** — every routing decision is appended to
  `state.routing_log` with a timestamp + reason and logged structurally.
- **Stop/resume without data loss** — state is persisted after every step;
  `python main.py resume` (and `test_checkpointed_task_can_resume`) prove it.
- **Pluggable agents** — one file + one config block, no core edits.

> **Note on executing generated code:** TestRunner runs model-generated code in
> a subprocess with a hard timeout and an isolated temp directory. This is
> appropriate for an authorized, sandboxed development setting; harden the
> sandbox (container, seccomp, resource limits, network egress controls) before
> running untrusted prompts in production.
