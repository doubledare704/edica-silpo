import os
import sys
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str:
    """Use example env in tests to avoid leaking real secrets from .env.

    When running under pytest (pytest in sys.modules or PYTEST_CURRENT_TEST set),
    load `.env.example` instead of `.env`. Production (uvicorn, direct run) keeps `.env`.
    Falls back to `.env` if `.env.example` not found.
    """
    is_test = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None
    if is_test:
        # Search for .env.example from repo root and backend parent
        candidates = [
            Path(".env.example"),  # cwd = repo root (uv run pytest)
            Path(__file__).resolve().parents[2] / ".env.example",  # backend/app/config.py -> repo root
            Path(__file__).resolve().parents[3] / ".env.example",
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)
        # Fallback: still avoid real .env
        return ".env.example"
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TTS_ENABLED: bool = True
    TTS_MOCK_MODE: bool = False
    RESPEECHER_API_KEY: str = ""
    RESPEECHER_VOICE_ID: str = "olesia-conversation"
    RESPEECHER_MODEL: Literal["ua-rt", "en-rt"] = "ua-rt"
    MCP_MOCK_MODE: bool = True
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TTS_MODEL: str = "gemini-3.1-flash-tts-preview"
    TTS_PROVIDER: Literal["respeecher", "gemini"] = "respeecher"
    GEMINI_MOCK_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    MAX_PICKER_STEPS: int = 8
    MIN_ITEM_PRICE_FLOOR: float = 15.0


settings = Settings()
