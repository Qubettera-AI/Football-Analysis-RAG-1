"""Centralized application logging for local and deployed processes."""

from __future__ import annotations

import logging
import os

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_HANDLER_MARKER = "_football_rag_handler"


def configure_logging(level: str | None = None) -> None:
    """Configure timestamped stream logging once for the application process."""
    requested_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, requested_level, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    if any(getattr(handler, _HANDLER_MARKER, False) for handler in root_logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z"))
    setattr(handler, _HANDLER_MARKER, True)
    root_logger.addHandler(handler)
