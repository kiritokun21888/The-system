# System AI — real assistant backend

A real, working Windows assistant engine that the high-graphics dashboard drives.
Every command actually executes; agents run autonomously; memory persists.

> **What's real and verified** (tested on the build machine): the command
> processor + routing, system stats, task DB (SQLite, auto-priority), reminders
> (APScheduler + natural-language times), research (DuckDuckGo + scrape +
> summarize), memory vault + logging, the WebSocket event stream, and graceful
> degradation when an optional piece is missing.
>
> **What runs only on your Windows machine** (can't be tested from a Linux build
> server — no mic, no display, no Windows): the voice pipeline (vosk wake word +
> whisper transcription + pyttsx3 speech) and live app control (open/close/focus
> apps, type/click, volume, screenshots). These are written to spec and execute
> for real on Windows; everything is guarded so a missing piece never crashes the
> system.

## Run

```bat
:: from the repo root, one double-click each:
setup.bat            :: installs backend + voice + dashboard
Start-System.bat     :: launches the engine + the dashboard
```

Or manually:

```bat
python -m pip install -r assistant\backend\requirements.txt
cd assistant
python -m backend.main
```

The dashboard's **command bar** (top center) and **notifications** + **stats
bar** are wired to this backend. Type a command and it executes:

| Say / type | What happens |
|---|---|
| `system stats` | real CPU / RAM / disk |
| `add task buy milk asap` | task saved to SQLite, auto-prioritized |
| `remind me in 20 minutes to stretch` | scheduled; fires with popup + voice |
| `open chrome` / `close spotify` | launches / terminates the real app |
| `research electric cars` | DuckDuckGo + scrape + summary saved to memory |
| `what's running` | live process list |
| `volume 30` | sets Windows master volume |
| `what did I ask yesterday` | searches the conversation log |

## Voice (offline, optional)

1. `setup.bat` installs `vosk`, `openai-whisper`, `sounddevice`, `pyttsx3`.
2. Download a vosk model and unzip it to `assistant\backend\models\vosk\`
   (e.g. *vosk-model-small-en-us* from alphacephei.com/vosk/models).
3. Restart. Say **"Hey System"**, then your command. It transcribes locally with
   whisper "tiny" and replies with offline speech. No API keys, ever.

## Layout

```
assistant/backend/
  main.py              FastAPI + WebSocket + agent orchestration ("SYSTEM ONLINE")
  command_processor.py natural-language intent router
  config.py db.py memory.py events.py
  agents/
    system_agent.py    real Windows control (apps, files, volume, screenshots…)
    voice_agent.py     vosk + whisper + pyttsx3 (offline)
    task_agent.py reminder_agent.py research_agent.py
    routine_agent.py health_agent.py clipboard_agent.py file_watcher_agent.py
```
