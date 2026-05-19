"""FastAPI application factory.

Phase 0 only exposed ``/health``. Phase 1 adds:

* Per-launch token gating via :mod:`pinsilico.auth` (everything except
  ``/health``).
* The standard error envelope from :mod:`pinsilico.errors`.
* A simple token-gated ``/version`` route the Tauri shell uses to verify
  it has the right token before mounting the webview.

Phase 1 does **not** add chemistry routes yet - those land in Phases 2-5.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from pinsilico import __version__
from pinsilico.auth import make_token_verifier, resolve_token
from pinsilico.errors import install_handlers


class HealthResponse(BaseModel):
    """Liveness probe response.

    Field invariants locked by ``tests/unit/test_health.py``:

    * ``status`` is always the literal string ``"ok"``.
    * ``version`` equals :data:`pinsilico.__version__`.

    Phase 2+ may add additive fields (``uptime_seconds``, ``build_sha``) but
    must never remove these two.
    """

    status: str = Field(default="ok", examples=["ok"])
    version: str = Field(default=__version__, examples=[__version__])


class VersionResponse(BaseModel):
    """Authenticated identity probe."""

    version: str = Field(examples=[__version__])
    schema_version: str = Field(
        default="1",
        description="HTTP API schema version. Bumped only on breaking changes.",
        examples=["1"],
    )


def create_app(*, token: str | None = None) -> FastAPI:
    """Construct the FastAPI application.

    Args:
        token: Explicit token override. Tests pass a deterministic value;
            production code lets :func:`resolve_token` fall through to the
            env var or a freshly generated value.
    """
    active_token = resolve_token(token)
    verifier = make_token_verifier(active_token)

    app = FastAPI(
        title="PInSilico Sidecar",
        version=__version__,
        description=(
            "Local-only FastAPI sidecar for the PInSilico desktop app. "
            "Wraps chemistry, docking, pocket detection, and simulation. "
            "Never exposed beyond 127.0.0.1. Every route except /health "
            "requires the X-Pinsilico-Token header."
        ),
    )
    install_handlers(app)

    # Store the token on app state so tests / Phase 6 wiring can introspect.
    app.state.token = active_token

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Liveness probe (unauthenticated)",
        description=(
            "Returns 200 with `{status: 'ok', version: <pkg-version>}` when "
            "the sidecar is ready. Polled by the Tauri shell during launch "
            "(Phase 6) — intentionally unauthenticated so the shell can "
            "probe before reading the token line from stdout."
        ),
        responses={
            200: {
                "description": "Sidecar is ready.",
                "content": {
                    "application/json": {
                        "example": {"status": "ok", "version": __version__},
                    },
                },
            },
        },
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get(
        "/version",
        response_model=VersionResponse,
        summary="Version + API schema (token-gated)",
        description=(
            "Returns the sidecar package version and the HTTP API schema "
            "version. The Tauri shell calls this immediately after /health "
            "to verify it has the right token before mounting the webview."
        ),
        dependencies=[Depends(verifier)],
        responses={
            200: {
                "description": "Token accepted.",
                "content": {
                    "application/json": {
                        "example": {"version": __version__, "schema_version": "1"},
                    },
                },
            },
            401: {
                "description": "Missing or invalid token.",
                "content": {
                    "application/json": {
                        "example": {
                            "error": {
                                "code": "INVALID_TOKEN",
                                "message": "The X-Pinsilico-Token header did not match the expected value.",
                                "details": {},
                            },
                        },
                    },
                },
            },
        },
    )
    def version() -> VersionResponse:
        return VersionResponse(version=__version__, schema_version="1")

    return app


# Module-level singleton for ASGI servers (`uvicorn pinsilico.server:app`).
# In production the token is read from PINSILICO_TOKEN (set by __main__.py
# before uvicorn imports this module).
app = create_app()
