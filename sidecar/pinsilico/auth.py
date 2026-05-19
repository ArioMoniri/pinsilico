"""Per-launch token auth for the sidecar.

The token is generated once at process start (or supplied by the parent
process via ``PINSILICO_TOKEN`` / a CLI flag) and printed on stdout as
``PINSILICO_TOKEN=<token>``. The Tauri shell (Phase 6) reads that line and
sends the token as ``X-Pinsilico-Token`` on every request.

Two-line security model
-----------------------

The sidecar binds to loopback only (validated in :class:`SidecarConfig`),
so the remaining concern is *other processes on the same machine* poking
at the chemistry endpoints. The per-launch token defeats that without
needing OS-level process gating — a curious process would have to
read the parent's stdout to recover it.

The ``/health`` endpoint is the **only** unauthenticated route. Phase 6
needs to probe liveness before it has finished reading the
``PINSILICO_TOKEN`` line from stdout.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Header, HTTPException, status


def generate_token() -> str:
    """Return a fresh URL-safe token suitable for use as an auth bearer.

    Uses :func:`secrets.token_urlsafe` with 32 random bytes, yielding ~43
    characters of base64url. Distinct on every call.
    """
    return secrets.token_urlsafe(32)


def resolve_token(explicit: str | None = None) -> str:
    """Pick the active token, in priority order.

    1. ``explicit`` argument (tests supply this).
    2. ``PINSILICO_TOKEN`` environment variable.
    3. Freshly generated token from :func:`generate_token`.
    """
    if explicit is not None:
        return explicit
    env = os.environ.get("PINSILICO_TOKEN")
    if env:
        return env
    return generate_token()


def verify_token(provided: str | None, *, expected: str) -> bool:
    """Constant-time equality check.

    Returns ``False`` for ``None``, the empty string, mismatches in case, or
    any whitespace padding. Uses :func:`secrets.compare_digest` so a timing
    side-channel can't reveal the token byte-by-byte to a local attacker.
    """
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


def make_token_verifier(expected_token: str) -> Callable[[str | None], None]:
    """Build a FastAPI dependency closure bound to the per-launch token.

    Returning a closure (rather than a class instance with ``__call__``)
    keeps FastAPI's dependency-injection signature inspection clean — it
    sees only the single ``Header`` parameter and doesn't trip over ``self``.

    Usage::

        verifier = make_token_verifier(token)


        @app.get("/protected", dependencies=[Depends(verifier)])
        def protected() -> dict[str, str]: ...
    """

    def _verifier(
        x_pinsilico_token: Annotated[
            str | None,
            Header(
                alias="X-Pinsilico-Token",
                description="Per-launch auth token printed by the sidecar on stdout.",
            ),
        ] = None,
    ) -> None:
        """Raise 401 with the standard error envelope on a bad/missing token."""
        if x_pinsilico_token is None or x_pinsilico_token == "":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "MISSING_TOKEN",
                    "message": (
                        "Request did not include the X-Pinsilico-Token "
                        "header. Every route except /health requires it."
                    ),
                },
            )
        if not verify_token(x_pinsilico_token, expected=expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": "The X-Pinsilico-Token header did not match the expected value.",
                },
            )

    return _verifier
