from app.config import Settings, settings


def test_default_settings() -> None:
    config = Settings()
    assert config.TTS_ENABLED is True
    assert config.TTS_MOCK_MODE is False


def test_global_settings_instance() -> None:
    assert isinstance(settings, Settings)
    assert settings.TTS_ENABLED is True
    assert settings.TTS_MOCK_MODE is False


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("TTS_ENABLED", "true")
    monkeypatch.setenv("TTS_MOCK_MODE", "false")
    config = Settings()
    assert config.TTS_ENABLED is True
    assert config.TTS_MOCK_MODE is False
