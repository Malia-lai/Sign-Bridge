"""Structured logging utilities for the agent service."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # merge any extra fields attached to the record
        for key, value in getattr(record, "__dict__", {}).items():
            if key.startswith("_") or key in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName", "taskName",
            }:
                continue
            if key not in payload:
                payload[key] = value
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")


def _resolve_level(level: Optional[str] = None) -> int:
    value = (level if level is not None else getattr(settings, "log_level", os.getenv("LOG_LEVEL", "INFO"))).upper()
    # also allow env override at call time
    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        value = env_level.upper()
    return getattr(logging, value, logging.INFO)


def _resolve_format(fmt: Optional[str] = None) -> str:
    value = (fmt if fmt is not None else getattr(settings, "log_format", os.getenv("LOG_FORMAT", "console"))).lower()
    env_fmt = os.getenv("LOG_FORMAT")
    if env_fmt:
        value = env_fmt.lower()
    return value


def configure_logging(level: Optional[str] = None, log_format: Optional[str] = None) -> None:
    """Configure root logging handlers based on env/settings."""
    root = logging.getLogger()
    # remove existing handlers to avoid duplicates
    for handler in list(root.handlers):
        root.removeHandler(handler)

    resolved_level = _resolve_level(level)
    resolved_format = _resolve_format(log_format)

    handler = logging.StreamHandler(sys.stdout)
    if resolved_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root.addHandler(handler)
    root.setLevel(resolved_level)

    # keep noisy third-party libs quieter
    logging.getLogger("uvicorn.access").setLevel(resolved_level)


def setup_logging(*args, **kwargs) -> None:
    return configure_logging(*args, **kwargs)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    # ensure configured at least once
    root = logging.getLogger()
    if not root.handlers:
        configure_logging()
    logger = logging.getLogger(name if name else "agent")
    try:
        logger.setLevel(_resolve_level())
    except Exception:
        pass
    return logger


# aliases
getLogger = get_logger
configure = configure_logging
setup = setup_logging

# Auto-configure on import using current settings (best effort)
try:
    configure_logging()
except Exception:  # pragma: no cover
    pass

logger = get_logger("agent")