"""
Structured logging setup. Called once from main.py at startup. Uses the
standard library's logging module configured for JSON-ish structured
output — no external dependency (structlog/loguru) needed for the
foundation stage; see README "Future improvements" for when to reconsider.

Per .cursor/prompts/05-security.md: never log passwords, tokens, or
verification codes. Callers are responsible for not passing them — this
module only formats what it's given.
"""
import logging
import sys

from app.core.config import get_settings

settings = get_settings()

_LOG_FORMAT = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"message":"%(message)s"}'
)


def configure_logging() -> None:
    """Call once, at app startup (main.py)."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    # Quiet noisy third-party loggers unless we're actively debugging.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if not settings.DEBUG else logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.DEBUG else logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
