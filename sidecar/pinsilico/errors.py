"""Standard error envelope shared by every non-2xx response.

Every error body has the shape::

    {
        "error": {
            "code": "<UPPER_SNAKE_SLUG>",
            "message": "<human-readable>",
            "details": {...},  # optional, defaults to {}
        }
    }

The Tauri shell pattern-matches on ``error.code`` to decide whether to
prompt the user (e.g. ``ENGINE_NOT_AVAILABLE`` → offer download) or just
surface ``error.message`` in a toast.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Inner ``error`` object of the standard envelope."""

    code: str = Field(
        description="Upper-snake-case slug. Stable across releases.",
        examples=["MISSING_TOKEN", "INVALID_TOKEN", "ENGINE_NOT_AVAILABLE"],
    )
    message: str = Field(description="Human-readable explanation.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured payload (engine name, file path, …).",
    )


class ErrorEnvelope(BaseModel):
    """Top-level non-2xx response body."""

    error: ErrorBody


def envelope(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Build a payload matching :class:`ErrorEnvelope`.

    Used by both FastAPI exception handlers and any module that wants to
    surface an error via a non-HTTPException path (e.g. SSE error frames).
    """
    return {"error": {"code": code, "message": message, "details": details}}


def install_handlers(app: FastAPI) -> None:
    """Wire the envelope-emitting handlers onto a FastAPI app.

    Handles three sources of non-2xx replies:

    * :class:`HTTPException` raised from a route / dependency. If the
      ``detail`` is already a dict with a ``code``, it is treated as the
      partial envelope body and the standard wrapper applied; otherwise the
      detail string becomes the ``message``.
    * :class:`RequestValidationError` from pydantic — surfaced as
      ``VALIDATION_ERROR`` with the pydantic error list under ``details``.
    * Any uncaught :class:`Exception` — surfaced as ``INTERNAL_ERROR`` with
      no stack-trace leak.
    """

    @app.exception_handler(HTTPException)
    async def _http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        # Starlette types `detail` as `str`, but FastAPI accepts any JSON-able
        # payload at runtime (we pass a dict from auth.py). Cast at the
        # boundary so mypy can narrow correctly without unreachable warnings.
        detail = cast(Any, exc.detail)
        if isinstance(detail, dict) and "code" in detail:
            body = envelope(
                code=str(detail.get("code", "HTTP_ERROR")),
                message=str(detail.get("message", "")),
                **{k: v for k, v in detail.items() if k not in {"code", "message"}},
            )
        else:
            body = envelope(code=f"HTTP_{exc.status_code}", message=str(detail))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope(
                code="VALIDATION_ERROR",
                message="Request payload failed schema validation.",
                errors=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        # Deliberately don't leak the str(exc) into the message — the sidecar
        # may surface error responses to a logged-out webview. Phase 1's
        # structured log captures the full trace separately.
        _ = exc  # consumed by the structured logger via middleware (Phase 1)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope(
                code="INTERNAL_ERROR",
                message="The sidecar encountered an unexpected error.",
            ),
        )
