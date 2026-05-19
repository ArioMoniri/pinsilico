"""Auth tests — per-launch token gating every route except ``/health``.

The token is the only thing keeping a curious neighbour process on the same
machine from poking at the sidecar's chemistry endpoints. The Tauri shell
(Phase 6) reads the token from the sidecar's stdout and sends it as
``X-Pinsilico-Token`` on every request.

Invariants locked here:

* A freshly generated token is URL-safe and ≥ 32 chars.
* ``/health`` is **always** unauthenticated (Phase 6 needs to probe before
  it has finished reading the token line from stdout).
* Every other route 401s when the header is missing, mismatched, or empty.
* The 401 body uses the standard error envelope (locked separately in
  ``test_errors.py``).
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pinsilico.auth import generate_token, verify_token
from pinsilico.server import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def token() -> str:
    return "test-token-1234567890abcdef"


@pytest.fixture
def client(token: str) -> Iterator[TestClient]:
    app = create_app(token=token)
    with TestClient(app) as c:
        yield c


class TestGenerateToken:
    def test_returns_string(self) -> None:
        assert isinstance(generate_token(), str)

    def test_minimum_length_32_chars(self) -> None:
        # secrets.token_urlsafe(32) yields ~43 base64-url chars
        assert len(generate_token()) >= 32

    def test_url_safe_characters_only(self) -> None:
        allowed = set(string.ascii_letters + string.digits + "-_")
        for _ in range(20):
            tok = generate_token()
            assert set(tok) <= allowed

    def test_two_calls_produce_distinct_tokens(self) -> None:
        # Cryptographic randomness: collisions are astronomically unlikely
        tokens = {generate_token() for _ in range(50)}
        assert len(tokens) == 50


class TestVerifyToken:
    def test_correct_token_passes(self, token: str) -> None:
        assert verify_token(token, expected=token) is True

    def test_wrong_token_fails(self, token: str) -> None:
        assert verify_token("wrong-token", expected=token) is False

    def test_none_header_fails(self, token: str) -> None:
        assert verify_token(None, expected=token) is False

    def test_empty_header_fails(self, token: str) -> None:
        assert verify_token("", expected=token) is False

    def test_case_sensitive(self, token: str) -> None:
        # secrets compare must be case-sensitive — tokens are not identifiers
        assert verify_token(token.upper(), expected=token) is False

    def test_whitespace_not_stripped(self, token: str) -> None:
        # Don't quietly accept padded headers — a buggy client should fail loud
        assert verify_token(f" {token}", expected=token) is False
        assert verify_token(f"{token} ", expected=token) is False


class TestRouteAuthGating:
    """``/health`` is the deliberate exception; everything else is gated."""

    def test_health_works_without_token(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_works_with_wrong_token(self, client: TestClient) -> None:
        response = client.get("/health", headers={"X-Pinsilico-Token": "bogus"})
        assert response.status_code == 200

    def test_version_route_requires_token(self, client: TestClient) -> None:
        response = client.get("/version")  # no header
        assert response.status_code == 401

    def test_version_route_rejects_wrong_token(self, client: TestClient) -> None:
        response = client.get("/version", headers={"X-Pinsilico-Token": "bogus"})
        assert response.status_code == 401

    def test_version_route_accepts_correct_token(self, client: TestClient, token: str) -> None:
        response = client.get("/version", headers={"X-Pinsilico-Token": token})
        assert response.status_code == 200

    def test_401_uses_error_envelope(self, client: TestClient) -> None:
        """Every error response uses the standard envelope shape (see
        ``test_errors.py``).
        """
        body = client.get("/version").json()
        assert "error" in body
        assert body["error"]["code"] == "MISSING_TOKEN"
        assert isinstance(body["error"]["message"], str)
        assert body["error"]["message"]

    def test_401_for_wrong_token_uses_invalid_code(self, client: TestClient) -> None:
        body = client.get("/version", headers={"X-Pinsilico-Token": "bogus"}).json()
        assert body["error"]["code"] == "INVALID_TOKEN"


class TestAppFactoryAcceptsToken:
    def test_explicit_token_overrides_default(self, token: str) -> None:
        app = create_app(token=token)
        with TestClient(app) as c:
            response = c.get("/version", headers={"X-Pinsilico-Token": token})
            assert response.status_code == 200

    def test_omitting_token_generates_one(self) -> None:
        app = create_app()
        # The generated token is not exposed via the API; we just confirm the
        # app boots and protected routes 401 without a header.
        with TestClient(app) as c:
            response = c.get("/version")
            assert response.status_code == 401
