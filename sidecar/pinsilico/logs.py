"""Structured-logging setup.

Every sidecar event is emitted as a single JSON line with a stable shape
(``timestamp``, ``level``, ``event``, plus any bound context). Two sinks:

* **stdout** — for ``make dev`` and PyInstaller-bundled launches; greppable
  with ``jq``.
* **rotating file** — under ``~/.pinsilico/logs/sidecar.log`` in production
  (configurable). 10 MB per file, 5 historical files. Caps disk usage at
  ~60 MB total without manual intervention.

Module name is :mod:`pinsilico.logs` rather than :mod:`pinsilico.logging`
to avoid shadowing the stdlib ``logging`` module in IDE auto-imports and
in any future ``import logging`` line inside this package.
"""

from __future__ import annotations

import logging as _stdlib_logging
import sys
from logging.handlers import RotatingFileHandler
from typing import IO, TYPE_CHECKING, Any

import structlog
from structlog.types import EventDict, Processor

if TYPE_CHECKING:
    from pathlib import Path

# Defaults align with BUILD_PROMPT.md §1 Phase 1 "log rotation under
# ~/.pinsilico/logs/". A 10 MB cap x 5 backups = ~60 MB peak.
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5
_LOG_FILE_NAME = "sidecar.log"


def _level_to_int(level: str) -> int:
    """Map a string level name (case-insensitive) to its stdlib int value."""
    mapping = {
        "debug": _stdlib_logging.DEBUG,
        "info": _stdlib_logging.INFO,
        "warning": _stdlib_logging.WARNING,
        "warn": _stdlib_logging.WARNING,
        "error": _stdlib_logging.ERROR,
        "critical": _stdlib_logging.CRITICAL,
    }
    key = level.lower()
    if key not in mapping:
        msg = f"unknown log level: {level!r}"
        raise ValueError(msg)
    return mapping[key]


def _build_processors() -> list[Processor]:
    """Return the shared processor chain for both sinks."""
    return [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
    ]


class _JsonFormatter(_stdlib_logging.Formatter):
    """stdlib Formatter that returns the message verbatim.

    structlog already produces a JSON string; the stdlib handler doesn't
    need to wrap or decorate it further.
    """

    def format(self, record: _stdlib_logging.LogRecord) -> str:
        # ``record.msg`` is the JSON string produced by structlog's
        # JSONRenderer. Just hand it back; no %-substitution.
        if isinstance(record.msg, str):
            return record.msg
        return str(record.msg)


def configure_logger(
    *,
    level: str = "info",
    log_dir: Path,
    stream: IO[str] | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
) -> None:
    """Wire structlog + stdlib logging with stdout + rotating-file sinks.

    Args:
        level: Minimum level to emit. Anything below is dropped before sinks.
        log_dir: Directory for the rotating ``sidecar.log`` file. Created
            with ``mkdir -p`` semantics if absent.
        stream: Stream for the stdout sink. Defaults to :data:`sys.stdout`.
            Tests pass a :class:`io.StringIO` for inspection.
        max_bytes: Per-file size cap before rotation (default 10 MB).
        backup_count: Number of rotated siblings to keep (default 5).
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILE_NAME

    int_level = _level_to_int(level)

    # --- stdlib root logger setup -----------------------------------------
    root = _stdlib_logging.getLogger()
    # Clear any handlers from previous configure_logger calls (re-entrancy
    # matters for tests that call us many times).
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(int_level)

    formatter = _JsonFormatter()

    stream_handler = _stdlib_logging.StreamHandler(stream=stream or sys.stdout)
    stream_handler.setLevel(int_level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(int_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # --- structlog config -------------------------------------------------
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            *_build_processors(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(int_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> Any:
    """Return a structlog logger optionally pre-bound with context.

    Annotated as ``Any`` because structlog's runtime logger type depends on
    the wrapper_class configured in :func:`configure_logger` (a filtering
    bound logger), not the static ``BoundLogger`` stub. Callers treat the
    result as duck-typed (``.info()``, ``.bind()``, …).
    """
    log = structlog.get_logger(name)
    if initial_context:
        return log.bind(**initial_context)
    return log


__all__ = ["configure_logger", "get_logger"]


# ----------------------------------------------------------------------
# Type-only re-export so callers can spell `logs.EventDict` rather than
# digging through structlog.types.
EventDict = EventDict  # noqa: PLW0127  # explicit re-export
