"""CLI entrypoint.

``python -m pinsilico`` (or the installed ``pinsilico-sidecar`` script)
launches uvicorn against :mod:`pinsilico.server`.

Phase 1 stdout-as-IPC contract — the Tauri shell (Phase 6) parses four
lines from this script's stdout, in order, before anything else:

    PINSILICO_HOST=127.0.0.1
    PINSILICO_PORT=51234
    PINSILICO_VERSION=0.0.1
    PINSILICO_TOKEN=<urlsafe-token>

After these four lines uvicorn's own logs begin. The shell ignores
everything after the token line.
"""

from __future__ import annotations

import os
import socket
import sys

import uvicorn

from pinsilico.auth import resolve_token
from pinsilico.config import SidecarConfig


def _resolve_port(host: str, requested: int) -> int:
    """Bind a probe socket to pick an ephemeral port when ``requested == 0``.

    Returns the actual port (either the requested one or the OS-assigned
    free port). Doing this up front lets us print ``PINSILICO_PORT=<port>``
    *before* uvicorn's own log noise.
    """
    if requested != 0:
        return requested
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        port: int = probe.getsockname()[1]
        return port


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code.

    The ``argv`` parameter is reserved for future CLI flags (``--log-level``,
    ``--token-out=PATH``); Phase 1 ignores it.
    """
    _ = argv
    cfg = SidecarConfig()
    port = _resolve_port(cfg.host, cfg.port)
    token = resolve_token()

    # Export the token in the process env so the uvicorn-spawned worker
    # picks it up when it imports `pinsilico.server` and runs create_app().
    os.environ["PINSILICO_TOKEN"] = token

    # Stdout-as-IPC: order matters. Tauri shell parses these lines top-down.
    sys.stdout.write(f"PINSILICO_HOST={cfg.host}\n")
    sys.stdout.write(f"PINSILICO_PORT={port}\n")
    sys.stdout.write(f"PINSILICO_VERSION={cfg.version}\n")
    sys.stdout.write(f"PINSILICO_TOKEN={token}\n")
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
