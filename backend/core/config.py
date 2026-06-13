"""Central configuration for the Z.E.R.O backend.

All settings are loaded from environment variables (see ``.env.example``).
Secrets are never hard-coded; missing keys degrade gracefully so the system
still boots even when an integration has not been configured yet.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project root (…/backend) and load the local .env file early so
# that every module that imports ``settings`` sees the same values.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True

    # --- AI brain ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    claude_max_tokens: int = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))

    # --- Storage ---
    data_dir: Path = Path(os.getenv("ZERO_DATA_DIR", str(BACKEND_ROOT / "data")))
    database_url: str = ""

    # --- Voice ---
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    tts_engine: str = os.getenv("TTS_ENGINE", "pyttsx3")  # pyttsx3 | elevenlabs
    wake_word: str = os.getenv("WAKE_WORD", "zero")
    voice_enabled: bool = os.getenv("VOICE_ENABLED", "false").lower() == "true"

    # --- Briefing ---
    briefing_hour: int = int(os.getenv("BRIEFING_HOUR", "8"))
    briefing_minute: int = int(os.getenv("BRIEFING_MINUTE", "0"))

    # --- Integrations ---
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    openweather_city: str = os.getenv("OPENWEATHER_CITY", "San Francisco")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    spotify_client_id: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    google_credentials_file: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "")
    notion_api_key: str = os.getenv("NOTION_API_KEY", "")
    slack_token: str = os.getenv("SLACK_TOKEN", "")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            db_path = self.data_dir / "zero.db"
            self.database_url = f"sqlite+aiosqlite:///{db_path}"

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
