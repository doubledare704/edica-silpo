import logging

from app.config import Settings


def test_default_log_level_is_info() -> None:
    assert Settings().LOG_LEVEL == "INFO"


def test_log_level_env_override(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    assert Settings().LOG_LEVEL == "DEBUG"


def test_configure_logging_sets_info_level() -> None:
    from app.logging_config import configure_logging

    configure_logging("INFO")
    assert logging.getLogger().level == logging.INFO
    assert logging.getLogger("app").level in (logging.INFO, logging.NOTSET)
    assert logging.getLogger("uvicorn.error").level in (logging.INFO, logging.NOTSET)


def test_configure_logging_invalid_falls_back_to_info() -> None:
    from app.logging_config import configure_logging

    assert configure_logging("NOPE") == "INFO"
    assert logging.getLogger().level == logging.INFO


def test_app_logger_emits_at_info(capsys) -> None:
    import logging as std_logging

    from app.logging_config import configure_logging

    configure_logging("INFO")
    std_logging.getLogger("app.test_info_probe").info("info-visible-probe")
    assert "info-visible-probe" in capsys.readouterr().err
