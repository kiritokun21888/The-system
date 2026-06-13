"""Voice control engine — wake-word listening, Whisper transcription, TTS.

Heavy audio dependencies (sounddevice, whisper, speech_recognition, pyttsx3)
are imported lazily so the backend boots even when they are not installed.
The agent runs its blocking audio loop in a worker thread and publishes
transcripts back onto the event loop for the brain to process.
"""
from __future__ import annotations

import asyncio
import logging
import threading

from core.config import settings
from core.events import event_bus

logger = logging.getLogger("zero.voice")


class VoiceAgent:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._whisper = None
        self._tts = None

    # --- Lifecycle ---

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if not settings.voice_enabled:
            logger.info("Voice disabled (set VOICE_ENABLED=true to activate).")
            return
        self._loop = loop
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Voice agent listening for wake word '%s'.", settings.wake_word)

    def stop(self) -> None:
        self._running = False

    # --- Speech output ---

    def speak(self, text: str) -> None:
        """Synthesize speech. Prefers ElevenLabs, falls back to offline pyttsx3."""
        if not text:
            return
        if settings.tts_engine == "elevenlabs" and settings.elevenlabs_api_key:
            try:
                self._speak_elevenlabs(text)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ElevenLabs TTS failed, falling back: %s", exc)
        self._speak_offline(text)

    def _speak_offline(self, text: str) -> None:
        try:
            import pyttsx3
            if self._tts is None:
                self._tts = pyttsx3.init()
            self._tts.say(text)
            self._tts.runAndWait()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Offline TTS unavailable: %s", exc)

    def _speak_elevenlabs(self, text: str) -> None:
        import httpx
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/"
               f"{settings.elevenlabs_voice_id or 'EXAVITQu4vr4xnSDxMaL'}")
        headers = {"xi-api-key": settings.elevenlabs_api_key}
        payload = {"text": text, "model_id": "eleven_turbo_v2"}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            from core.config import settings as s
            out = s.data_dir / "tts_last.mp3"
            out.write_bytes(resp.content)
        self._play_audio(out)

    def _play_audio(self, path) -> None:
        import platform
        import subprocess
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["afplay", str(path)])
            elif system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=True)
            else:
                subprocess.Popen(["aplay", str(path)])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Audio playback failed: %s", exc)

    # --- Listening loop (runs in a worker thread) ---

    def _ensure_whisper(self):
        if self._whisper is None:
            import whisper
            self._whisper = whisper.load_model(settings.whisper_model)
        return self._whisper

    def _publish(self, event_type: str, payload: dict) -> None:
        if self._loop:
            event_bus.publish_threadsafe(self._loop, event_type, payload)

    def _listen_loop(self) -> None:
        try:
            import speech_recognition as sr
        except Exception as exc:  # noqa: BLE001
            logger.error("SpeechRecognition unavailable: %s", exc)
            return

        recognizer = sr.Recognizer()
        try:
            mic = sr.Microphone()
        except Exception as exc:  # noqa: BLE001
            logger.error("Microphone unavailable: %s", exc)
            return

        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

        wake = settings.wake_word.lower()
        while self._running:
            try:
                with mic as source:
                    audio = recognizer.listen(source, phrase_time_limit=8)
                text = self._transcribe(recognizer, audio).lower().strip()
                if not text:
                    continue
                if wake in text:
                    self._publish("voice.wake", {})
                    command = text.split(wake, 1)[-1].strip()
                    if not command:
                        # Wake word only — capture the following utterance.
                        with mic as source:
                            audio = recognizer.listen(source, phrase_time_limit=12)
                        command = self._transcribe(recognizer, audio).strip()
                    if command:
                        self._publish("voice.command", {"text": command})
            except Exception as exc:  # noqa: BLE001
                logger.debug("Listen loop hiccup: %s", exc)

    def _transcribe(self, recognizer, audio) -> str:
        # Prefer local Whisper; fall back to the recognizer's built-in engine.
        try:
            import io
            import wave

            import numpy as np
            model = self._ensure_whisper()
            wav_bytes = audio.get_wav_data()
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            result = model.transcribe(samples, fp16=False)
            return result.get("text", "")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Whisper unavailable, trying fallback: %s", exc)
            try:
                return recognizer.recognize_google(audio)
            except Exception:  # noqa: BLE001
                return ""


voice_agent = VoiceAgent()
