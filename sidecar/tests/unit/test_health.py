"""Contract tests for the /health endpoint.

Phase 0 DoD requires the sidecar to respond 200 OK with a stable JSON shape
to `GET /health`. The shape is locked here so future phases can't quietly
drop fields the Tauri shell's health-check loop (Phase 6) relies on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from pinsilico.server import app

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Fresh TestClient per test — keeps state isolation cheap and explicit."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """`GET /health` is the readiness gate the Tauri shell polls at launch."""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_json_content_type(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["content-type"].startswith("application/json")

    def test_body_has_expected_shape(self, client: TestClient) -> None:
        """The contract: exactly these two keys. Phase 1 may add more
        (`uptime`, `build`) but must never remove `status` or `version`."""
        body = client.get("/health").json()
        assert body == {"status": "ok", "version": "0.0.1"}

    def test_status_field_is_ok_string(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_version_field_matches_sidecar_package_version(
        self, client: TestClient
    ) -> None:
        """The /health version must equal pinsilico.__version__ — Phase 12
        adds a four-way CI check across Cargo / package.json / pyproject /
        this constant."""
        import pinsilico

        body = client.get("/health").json()
        assert body["version"] == pinsilico.__version__

    def test_no_auth_required_on_health(self, client: TestClient) -> None:
        """The health probe must never require the X-Pinsilico-Token header.
        Phase 1 wires token auth onto every other route; /health is the
        deliberate exception so the Tauri shell can verify liveness before
        it knows the token (Phase 6 reads the token AFTER /health flips
        to 200)."""
        response = client.get("/health")  # no header set
        assert response.status_code == 200
