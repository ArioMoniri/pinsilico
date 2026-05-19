"""Standard error-envelope contract tests.

Every non-2xx response from the sidecar wraps its body in::

    {"error": {"code": "...", "message": "...", "details": {...}}}

Locked here so the Tauri shell can pattern-match on ``error.code``
across releases without breaking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from pinsilico.errors import envelope, install_handlers
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterator


def _build_app_with_test_routes() -> FastAPI:
    """A bare FastAPI app that exercises every handler path in install_handlers."""
    app = FastAPI()
    install_handlers(app)

    @app.get("/raise/http-string")
    def _raise_http_string() -> None:
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT,
            detail="i am a teapot",
        )

    @app.get("/raise/http-envelope")
    def _raise_http_envelope() -> None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ENGINE_NOT_AVAILABLE",
                "message": "DiffDock weights not present",
                "engine": "diffdock",
                "download_url": "https://example.invalid/weights",
            },
        )

    @app.get("/raise/uncaught")
    def _raise_uncaught() -> None:
        msg = "kaboom"
        raise RuntimeError(msg)

    class Body(BaseModel):
        value: int

    @app.post("/raise/validation")
    def _raise_validation(_body: Body) -> dict[str, str]:
        return {"ok": "true"}

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # raise_server_exceptions=False so the 500 path goes through the
    # exception handler instead of bubbling out of the TestClient.
    with TestClient(_build_app_with_test_routes(), raise_server_exceptions=False) as c:
        yield c


class TestEnvelopeHelper:
    def test_basic_shape(self) -> None:
        e = envelope(code="X", message="m")
        assert e == {"error": {"code": "X", "message": "m", "details": {}}}

    def test_extra_details_flow_through(self) -> None:
        e = envelope(code="X", message="m", engine="vina", path="sample.pdb")
        assert e["error"]["details"] == {"engine": "vina", "path": "sample.pdb"}

    @given(
        code=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Nd"), whitelist_characters="_"),
            min_size=1,
            max_size=40,
        ),
        message=st.text(min_size=0, max_size=120),
    )
    def test_envelope_round_trips_arbitrary_strings(self, code: str, message: str) -> None:
        e = envelope(code=code, message=message)
        assert e["error"]["code"] == code
        assert e["error"]["message"] == message
        assert e["error"]["details"] == {}


class TestHTTPExceptionWithStringDetail:
    def test_status_passthrough(self, client: TestClient) -> None:
        r = client.get("/raise/http-string")
        assert r.status_code == 418

    def test_message_in_envelope(self, client: TestClient) -> None:
        body = client.get("/raise/http-string").json()
        assert body["error"]["code"] == "HTTP_418"
        assert body["error"]["message"] == "i am a teapot"
        assert body["error"]["details"] == {}


class TestHTTPExceptionWithEnvelopeDetail:
    def test_status_passthrough(self, client: TestClient) -> None:
        r = client.get("/raise/http-envelope")
        assert r.status_code == 409

    def test_code_and_message_extracted(self, client: TestClient) -> None:
        body = client.get("/raise/http-envelope").json()
        assert body["error"]["code"] == "ENGINE_NOT_AVAILABLE"
        assert body["error"]["message"] == "DiffDock weights not present"

    def test_extra_keys_become_details(self, client: TestClient) -> None:
        body = client.get("/raise/http-envelope").json()
        assert body["error"]["details"]["engine"] == "diffdock"
        assert body["error"]["details"]["download_url"] == "https://example.invalid/weights"


class TestUncaughtException:
    def test_status_500(self, client: TestClient) -> None:
        r = client.get("/raise/uncaught")
        assert r.status_code == 500

    def test_no_message_leak(self, client: TestClient) -> None:
        body = client.get("/raise/uncaught").json()
        # The Python exception said 'kaboom'; the envelope must not leak it.
        assert "kaboom" not in body["error"]["message"]
        assert body["error"]["code"] == "INTERNAL_ERROR"


class TestValidationError:
    def test_status_422(self, client: TestClient) -> None:
        r = client.post("/raise/validation", json={"value": "not-an-int"})
        assert r.status_code == 422

    def test_envelope_code(self, client: TestClient) -> None:
        body = client.post("/raise/validation", json={"value": "not-an-int"}).json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "errors" in body["error"]["details"]
        assert isinstance(body["error"]["details"]["errors"], list)
