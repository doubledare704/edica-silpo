import os

import pytest
from app.services import tts_service

_REAL_KEY = os.getenv("RESPEECHER_API_KEY")
_REAL_VOICE_ID = os.getenv("RESPEECHER_VOICE_ID")
_REAL_MODEL = os.getenv("RESPEECHER_MODEL")

pytestmark = pytest.mark.skipif(
    not _REAL_KEY,
    reason="Set RESPEECHER_API_KEY to run the live Respeecher smoke test",
)


@pytest.mark.asyncio
async def test_respeecher_bytes_real_integration(monkeypatch, tmp_path) -> None:
    assert _REAL_KEY, "live smoke test requires RESPEECHER_API_KEY"

    monkeypatch.setattr(tts_service.settings, "RESPEECHER_API_KEY", _REAL_KEY)
    if _REAL_VOICE_ID:
        monkeypatch.setattr(tts_service.settings, "RESPEECHER_VOICE_ID", _REAL_VOICE_ID)
    if _REAL_MODEL:
        monkeypatch.setattr(tts_service.settings, "RESPEECHER_MODEL", _REAL_MODEL)
    monkeypatch.setattr(tts_service, "_get_audio_dir", lambda: tmp_path)

    audio_url = await tts_service.generate_audio_respeecher("Перевірка озвучення")

    assert audio_url is not None
    assert audio_url.startswith("/static/audio/")
    assert audio_url.endswith(".wav")
    saved = next(iter(tmp_path.iterdir()))
    assert saved.read_bytes().startswith(b"RIFF")
