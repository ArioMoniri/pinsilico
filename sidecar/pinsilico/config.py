"""Runtime configuration for the sidecar.

Phase 0 keeps this intentionally tiny: the host, the port (0 = ephemeral,
filled in by uvicorn on bind), and the package version surfaced via /health.
Phase 1 adds the auth token, log level, and cache directory.

Configuration sources, in priority order (highest first):

1. Constructor kwargs / explicit overrides (tests use this)
2. Environment variables prefixed ``PINSILICO_``
3. Defaults defined here
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pinsilico import __version__

# Well-known TCP port range upper bound (RFC 6056). Kept as a named constant
# so :class:`SidecarConfig.__post_init__` doesn't trip Ruff's PLR2004 magic-
# number lint and so it can be reused in tests.
_MAX_TCP_PORT = 65535


def _bool_env(name: str, *, default: bool) -> bool:
    """Return a truthy reading of an environment variable.

    Accepts ``1/true/yes/on`` (case-insensitive) as true; everything else is
    false. Keyword-only ``default`` matches Ruff's FBT positional-bool style.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class SidecarConfig:
    """Immutable sidecar configuration.

    Attributes:
        host: Bind address. Always ``127.0.0.1`` in production — the sidecar
            must never be reachable from another machine.
        port: TCP port. ``0`` means "ask the OS for an ephemeral port"; the
            Tauri shell reads the chosen port back from stdout (Phase 6).
        version: Package version string returned by ``/health``.
        reload: Hot-reload on source change. Only honoured in dev.
    """

    host: str = field(
        default_factory=lambda: os.environ.get("PINSILICO_HOST", "127.0.0.1"),
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("PINSILICO_PORT", "0")),
    )
    version: str = field(default=__version__)
    reload: bool = field(
        default_factory=lambda: _bool_env("PINSILICO_RELOAD", default=False),
    )

    def __post_init__(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            msg = (
                f"PInSilico sidecar must bind to loopback, got {self.host!r}. "
                "Remote exposure is forbidden by design (see BUILD_PROMPT.md §8.10)."
            )
            raise ValueError(msg)
        if not (0 <= self.port <= _MAX_TCP_PORT):
            msg = f"port out of range: {self.port}"
            raise ValueError(msg)
