"""Voice agent — fully offline voice I/O.

Pipeline (no external APIs, no keys):
  * wake word detection with **vosk** (small offline model, CPU-friendly),
  * record until silence (RMS energy gate on the mic stream),
  * transcribe the captured command with **openai-whisper** "tiny" (local),
  * speak responses with **pyttsx3** (offline TTS).

Everything is lazy-imported and guarded: if a model, the mic, or a library is
missing, the agent reports a clear status and the rest of the system runs
normally. Voice runs in its own daemon thread; results are handed back to the
asyncio command processor via a thread-safe bridge.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Any, Callable, Optional

from ..events import bus
from .base import Agent

# Where to look for the vosk model (download instructions in the README).
_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "vosk")
_SAMPLE_RATE = 16000


class VoiceAgent(Agent):
    """Offline wake-word + speech-to-text + text-to-speech."""

    name = "voice"

    def __init__(self, wake_word: str = "hey system") -> None:
        super().__init__()
        self.wake_word = wake_word.lower()
        self._handler: Optional[Callable[[str], str]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._tts_lock = threading.Lock()
        self._engine: Any = None
        self._whisper: Any = None
        self.available = False

    # ------------------------------------------------------------------ #
    # Text-to-speech (usable even if mic/STT is unavailable)
    # ------------------------------------------------------------------ #
    def speak(self, text: str) -> None:
        """Speak ``text`` aloud (offline). Safe no-op if pyttsx3 is missing."""
        from .. import config

        cfg = config.load().get("voice", {})
        if not cfg.get("enabled", True):
            return
        with self._tts_lock:
            try:
                if self._engine is None:
                    import pyttsx3

                    self._engine = pyttsx3.init()
                self._engine.setProperty("rate", cfg.get("rate", 175))
                self._engine.setProperty("volume", float(cfg.get("volume", 1.0)))
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:  # noqa: BLE001
                pass  # TTS unavailable — silent fallback

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def set_handler(self, handler: Callable[[str], str]) -> None:
        """Register the sync command handler (text -> spoken response)."""
        self._handler = handler

    def start_thread(self) -> None:
        """Launch the listening loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="voice")
        self._thread.start()

    def stop(self) -> None:
        """Signal the listener thread to stop."""
        self._stop.set()

    # ------------------------------------------------------------------ #
    # Listening loop
    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        """Wake-word loop. Degrades gracefully if anything is missing."""
        try:
            import json

            import sounddevice as sd
            import vosk
        except Exception as exc:  # noqa: BLE001
            self.set_status("idle", last_action=f"voice libs not installed ({exc})")
            bus.broadcast_threadsafe("voice_status", {"available": False,
                                                      "reason": "libraries not installed"})
            return

        if not os.path.isdir(_MODEL_DIR):
            self.set_status("idle", last_action="vosk model missing (see README)")
            bus.broadcast_threadsafe("voice_status", {"available": False,
                                                      "reason": "vosk model not downloaded"})
            return

        try:
            model = vosk.Model(_MODEL_DIR)
            rec = vosk.KaldiRecognizer(model, _SAMPLE_RATE)
        except Exception as exc:  # noqa: BLE001
            self.set_status("error", last_action=f"vosk init failed: {exc}")
            return

        self.available = True
        self.set_status("running", last_action="listening for wake word",
                        next_action=f'"{self.wake_word}"')
        bus.broadcast_threadsafe("voice_status", {"available": True, "wake_word": self.wake_word})

        q: "queue.Queue[bytes]" = queue.Queue()

        def cb(indata, _frames, _t, _status):
            q.put(bytes(indata))

        try:
            with sd.RawInputStream(samplerate=_SAMPLE_RATE, blocksize=8000, dtype="int16",
                                   channels=1, callback=cb):
                while not self._stop.is_set():
                    data = q.get()
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "")
                        if self.wake_word in text.lower():
                            self._on_wake(sd, q)
        except Exception as exc:  # noqa: BLE001
            self.set_status("error", last_action=f"mic error: {exc}")

    def _on_wake(self, sd: Any, q: "queue.Queue[bytes]") -> None:
        """Wake word heard — record until silence, transcribe, dispatch."""
        bus.broadcast_threadsafe("voice_status", {"listening": True})
        self.set_status("running", last_action="wake word detected — listening")
        audio = self._record_until_silence(q)
        if not audio:
            return
        bus.broadcast_threadsafe("voice_status", {"listening": False, "transcribing": True})
        text = self._transcribe(audio)
        if not text:
            return
        bus.broadcast_threadsafe("transcript", {"text": text})
        self.set_status("running", last_action=f'heard: "{text}"')
        if self._handler:
            try:
                response = self._handler(text)
                if response:
                    self.speak(response)
            except Exception:  # noqa: BLE001
                pass

    def _record_until_silence(self, q: "queue.Queue[bytes]", max_seconds: float = 8.0) -> bytes:
        """Capture audio until ~1.2s of silence (RMS gate) or a max duration."""
        import audioop

        frames: list[bytes] = []
        silent_for = 0.0
        started = time.time()
        # Drain queued frames, accumulate, watch energy.
        while time.time() - started < max_seconds:
            try:
                data = q.get(timeout=max_seconds)
            except queue.Empty:
                break
            frames.append(data)
            rms = audioop.rms(data, 2)
            if rms < 350:  # quiet frame
                silent_for += len(data) / 2 / _SAMPLE_RATE
                if silent_for > 1.2 and len(frames) > 3:
                    break
            else:
                silent_for = 0.0
        return b"".join(frames)

    def _transcribe(self, audio: bytes) -> str:
        """Transcribe raw int16 PCM with whisper 'tiny'."""
        try:
            import numpy as np

            if self._whisper is None:
                import whisper

                self._whisper = whisper.load_model("tiny")
            samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            result = self._whisper.transcribe(samples, fp16=False, language="en")
            return str(result.get("text", "")).strip()
        except Exception as exc:  # noqa: BLE001
            self.set_status("error", last_action=f"transcription failed: {exc}")
            return ""
