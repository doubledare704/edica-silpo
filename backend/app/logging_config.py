import logging
import logging.config


def configure_logging(level: str = "INFO") -> str:
    normalized = (level or "INFO").upper()
    if normalized not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        normalized = "INFO"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {"handlers": ["default"], "level": normalized},
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": normalized, "propagate": False},
                "uvicorn.error": {"handlers": ["default"], "level": normalized, "propagate": False},
                "uvicorn.access": {"handlers": ["default"], "level": normalized, "propagate": False},
            },
        }
    )
    logging.captureWarnings(True)
    return normalized
