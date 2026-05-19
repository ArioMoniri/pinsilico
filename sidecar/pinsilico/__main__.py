"""CLI entrypoint.

``python -m pinsilico`` (or the installed ``pinsilico-sidecar`` script)
launches uvicorn against :mod:`pinsilico.server`.

Phase 0 prints the bound host/port on stdout so a human (and, in Phase 6,
the Tauri shell) can discover where the sidecar is listening. Phase 1
extends this with the per-launch auth token line
``PINSILICO_TOKEN=<token>``.
"""

from __future__ import annotations

import socket
import sys

import uvicorn

from pinsilico.config import SidecarConfig


def _resolve_port(host: str, requested: int) -> int:
    """Bind a probe socket to pick an ephemeral port when ``requested == 0``.

    Returns the actual port (either the requested one or the OS-assigned
    free port). Uvicorn would do this internally too, but doing it up front
    lets us print ``PINSILICO_PORT=<port>`` *before* uvicorn's own log
    noise — important because the Tauri shell (Phase 6) parses the first
    matching line from stdout.
    """
    if requested != 0:
        return requested
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        port: int = probe.getsockname()[1]
        return port


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code.

    The ``argv`` parameter is reserved for Phase 1 CLI flags (``--log-level``,
    ``--token-out=PATH``); Phase 0 ignores it.
    """
    _ = argv  # silence ARG001 until Phase 1 reads CLI flags
    cfg = SidecarConfig()
    port = _resolve_port(cfg.host, cfg.port)

    # Stdout-as-IPC: print discovery lines before uvicorn starts so consumers
    # that parse stdout (the Tauri shell, Phase 6) see them first. The KEY=VALUE
    # format lets a tiny `awk -F=` reader extract them.
    sys.stdout.write(f"PINSILICO_HOST={cfg.host}\n")
    sys.stdout.write(f"PINSILICO_PORT={port}\n")
    sys.stdout.write(f"PINSILICO_VERSION={cfg.version}\n")
    sys.stdout.flush()

    uvicorn.run(
        "pinsilico.server:app",
        host=cfg.host,
        port=port,
        reload=cfg.reload,
        log_level="info",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
