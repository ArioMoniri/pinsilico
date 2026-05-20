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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pinsilico import __version__
from pinsilico.auth import make_token_verifier, resolve_token
from pinsilico.errors import install_handlers
from pinsilico.routes import db as db_routes
from pinsilico.routes import pocket as pocket_routes
from pinsilico.routes import sim as sim_routes


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

    # CORS for the Tauri webview. The webview loads from `tauri://localhost`
    # (macOS / Linux) or `http://tauri.localhost` (Windows). Without CORS
    # headers the browser blocks fetches from the page even though the
    # request itself succeeds — the workspace then shows "Sidecar offline"
    # despite a working banner handshake. Auth is still enforced by the
    # per-launch token on every non-health route, so allowing the Tauri
    # origins here does not weaken the security boundary.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_handlers(app)

    # Store the token on app state so tests / Phase 6 wiring can introspect.
    app.state.token = active_token

    # Mount Phase 5 routers, all gated by the per-launch token verifier.
    app.include_router(db_routes.router, dependencies=[Depends(verifier)])
    app.include_router(pocket_routes.router, dependencies=[Depends(verifier)])
    app.include_router(sim_routes.router, dependencies=[Depends(verifier)])

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

    class ShutdownResponse(BaseModel):
        status: str = Field(default="scheduled", examples=["scheduled"])
        message: str = Field(
            default="Sidecar shutdown scheduled on the next event-loop tick.",
        )

    @app.post(
        "/shutdown",
        response_model=ShutdownResponse,
        status_code=202,
        summary="Schedule sidecar exit (token-gated)",
        description=(
            "The Tauri shell calls this on window close. The route returns "
            "202 immediately; the sidecar exits asynchronously so the HTTP "
            "client gets a clean response before the process dies."
        ),
        dependencies=[Depends(verifier)],
    )
    def shutdown() -> ShutdownResponse:
        # Phase 6 wiring schedules an `os._exit(0)` here on a small delay;
        # in tests we just return the envelope. The actual exit hook is
        # wired in pinsilico.__main__ after uvicorn starts.
        return ShutdownResponse()

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
