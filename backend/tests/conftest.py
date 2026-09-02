import pytest
from app.services import gemini_service


@pytest.fixture(autouse=True)
def isolate_example_env(monkeypatch):
    """Enforce tests use .env.example, not real .env with secrets.

    - Clears real secret env vars that would override .env.example defaults.
    - Resets Gemini singleton client between tests.
    - Ensures config singleton reflects example env (empty keys) unless test explicitly patches.
    """
    # Remove secrets that could be set in shell or by previous tests via os.environ
    # Note: monkeypatch.delenv will be restored after test, so isolation is per-test.
    for key in [
        "GEMINI_API_KEY",
        "GEMINI_MOCK_MODE",
        "GEMINI_MODEL",
        "GEMINI_TTS_MODEL",
        "TTS_PROVIDER",
        "TTS_ENABLED",
        "TTS_MOCK_MODE",
        "RESPEECHER_API_KEY",
        "RESPEECHER_VOICE_ID",
        "MCP_MOCK_MODE",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Reset lazy singleton so next get_genai_client re-evaluates settings
    gemini_service._client = None

    # Also reset app.config.settings singleton attributes to example defaults
    # by re-reading .env.example via fresh Settings instance and copying values.
    # This ensures global settings doesn't leak real .env values from pre-test import.
    from pathlib import Path

    from app.config import Settings, settings

    example_path = Path(".env.example")
    if not example_path.exists():
        example_path = Path(__file__).resolve().parents[2] / ".env.example"
    # Load example values via explicit _env_file, but don't set env vars
    example_settings = Settings(_env_file=str(example_path) if example_path.exists() else None)  # type: ignore[call-arg]
    # Copy example values to global singleton for test isolation
    for field in Settings.model_fields:
        # Use monkeypatch to ensure restoration after test
        monkeypatch.setattr(settings, field, getattr(example_settings, field))

    yield

    gemini_service._client = None
