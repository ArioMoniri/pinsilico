"""FastAPI application factory and the /health route.

Phase 0 surface area is intentionally minimal — only /health, no auth, no
routers. Phase 1 introduces the auth dependency, the structured logger
middleware, and the route modules under :mod:`pinsilico.routes`.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from pinsilico import __version__


class HealthResponse(BaseModel):
    """Liveness probe response.

    Field invariants locked by tests in ``tests/unit/test_health.py``:
        * ``status`` is always the literal string ``"ok"``.
        * ``version`` equals :data:`pinsilico.__version__`.

    Phase 1 may add additive fields (e.g. ``uptime_seconds``, ``build_sha``)
    but must never remove these two.
    """

    status: str = Field(
        default="ok",
        description="Liveness state. Always 'ok' when the response is 200.",
        examples=["ok"],
    )
    version: str = Field(
        default=__version__,
        description="Sidecar package version. Matches pinsilico.__version__.",
        examples=[__version__],
    )


def create_app() -> FastAPI:
    """Construct the FastAPI application.

    Kept as a factory rather than a module-level singleton so tests can spin
    up isolated instances and so Phase 1's auth + logging middleware can be
    injected without monkey-patching a shared global.
    """
    app = FastAPI(
        title="PInSilico Sidecar",
        version=__version__,
        description=(
            "Local-only FastAPI sidecar for the PInSilico desktop app. "
            "Wraps chemistry, docking, pocket detection, and simulation. "
            "Never exposed beyond 127.0.0.1."
        ),
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Liveness probe",
        description=(
            "Returns 200 with `{status: 'ok', version: <pkg-version>}` when "
            "the sidecar is ready to accept requests. Polled by the Tauri "
            "shell during launch (Phase 6) and intentionally unauthenticated "
            "so the shell can probe before it knows the auth token."
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

    return app


# Module-level singleton for ASGI servers (`uvicorn pinsilico.server:app`).
# Tests should call :func:`create_app` directly for isolation.
app = create_app()
