# Z.E.R.O

### Zero-latency Executive Reasoning Operator

An AI-powered desktop assistant — a local-first JARVIS — that runs natively on
macOS, Windows and Linux. Z.E.R.O combines a Python reasoning backend, a
real-time React/Three.js control center, and an Electron desktop shell.

```
┌──────────────────────────────────────────────────────────────┐
│  Electron shell  →  spawns Python backend  →  serves React UI  │
│                                                                │
│   React + Three.js  ◀── WebSocket / REST ──▶  FastAPI brain    │
│   (neural brain UI)                            Claude + agents  │
└──────────────────────────────────────────────────────────────┘
```

---

## Features

- **AI brain** — Claude (`claude-sonnet-4-6`) with a tool-use loop that can
  control the OS, manage tasks, run background agents, search the web and
  recall long-term memory. Falls back to a deterministic offline mode when no
  API key is set.
- **Voice control** — wake word ("Hey ZERO"), Whisper transcription, and TTS
  via offline `pyttsx3` or premium ElevenLabs.
- **System control** — launch/kill apps, system stats, files, clipboard,
  screenshots, and power management (with confirmation gates).
- **Task management** — natural-language task creation with automatic priority
  and due-date inference, plus a drag-and-drop Kanban board.
- **Background agents** — Research, Draft, Monitor, Calendar, Email and Focus
  agents running concurrently and reporting live to the UI.
- **Persistent memory** — ZERO extracts and stores durable facts about you and
  surfaces them across sessions.
- **Daily briefing** — a morning overlay with weather, calendar, top tasks and
  overnight agent results.
- **Neural brain visual** — a 220-node Three.js network that breathes when idle
  and surges with activity.

---

## Project structure

```
The-system/
├── backend/                 # Python · FastAPI · SQLAlchemy · APScheduler
│   ├── main.py              # App entrypoint (REST + WebSocket on :8000)
│   ├── core/                # config, database, events, brain, memory, tools
│   ├── agents/              # system, task, voice, reminder, background agents
│   ├── models/              # SQLAlchemy models (Task, ContextMemory, …)
│   ├── api/                 # REST routes + WebSocket endpoint
│   ├── integrations/        # external service connectors
│   └── requirements.txt
└── frontend/                # Electron + React + Vite + Three.js + Tailwind
    ├── src/components/       # NeuralBrain, CommandBar, TaskBoard, …
    ├── src/pages/            # Dashboard, Tasks, Agents, Memory, Settings
    ├── electron/             # main.js (spawns backend), preload.js
    └── package.json
```

---

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then add your ANTHROPIC_API_KEY
```

Optional voice extras (heavy; only if you want speech):

```bash
pip install openai-whisper SpeechRecognition pyttsx3 sounddevice numpy pyautogui
```

Run the backend standalone:

```bash
python main.py        # http://127.0.0.1:8000  (docs at /docs)
```

### 2. Frontend

```bash
cd frontend
npm install
```

Run the full desktop app (spawns the backend automatically via Electron):

```bash
npm start
```

Or develop the UI in the browser against a separately-running backend:

```bash
npm run dev           # http://localhost:5173
```

### 3. Build a production desktop bundle

```bash
cd frontend
npm run build         # builds the React bundle into dist/
npm run electron      # launches Electron against the built bundle
```

---

## Configuration

All backend configuration lives in `backend/.env` (see `backend/.env.example`).
Keys you can set:

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude reasoning core (required for full intelligence) |
| `VOICE_ENABLED` | `true` to start wake-word listening |
| `WHISPER_MODEL` | `tiny`…`large` transcription model |
| `TTS_ENGINE` | `pyttsx3` (offline) or `elevenlabs` |
| `OPENWEATHER_API_KEY` | Weather for the daily briefing |
| `BRAVE_SEARCH_API_KEY` | Web search for the Research agent (falls back to DuckDuckGo) |
| `GITHUB_TOKEN`, `SPOTIFY_*`, `GOOGLE_CREDENTIALS_FILE`, `NOTION_API_KEY`, `SLACK_TOKEN`, `ELEVENLABS_*` | Optional integrations |

Every integration degrades gracefully: a missing key shows as "not connected"
in the Connections hub instead of breaking the app.

---

## How it fits together

- **Startup**: Electron spawns `backend/main.py`, waits for `:8000`, then loads
  the React shell. The UI shows a Z.E.R.O splash, connects over WebSocket, and
  the neural brain comes alive.
- **Commands**: text/voice input → `POST /api/chat` → `brain.think()` runs the
  Claude tool loop → tools mutate state and publish events → the WebSocket
  pushes updates to every panel in real time.
- **Agents**: `run_agent` (tool or `POST /api/agents`) spawns an async worker
  that streams its lifecycle (`running → done/error`) to the orb display.
- **Memory**: after each exchange ZERO extracts durable facts and stores them;
  they are injected into the system prompt on the next turn.

---

## Security notes

- The backend binds to `127.0.0.1` only — it is not exposed to the network.
- Destructive system actions (`delete_file`, `restart`, `sleep`, `lock`)
  require an explicit `confirmed` flag, surfaced as a confirmation gate in the
  UI before execution.
- Secrets are read from environment variables only and are never committed
  (`.env` is git-ignored).
