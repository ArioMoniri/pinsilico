"""Contract test for the /shutdown route.

Phase 6 wiring: the Tauri shell sends POST /shutdown on window close
and falls back to SIGKILL if the sidecar hasn't exited in 1 second.
The route returns 202 Accepted immediately and schedules the shutdown
on the next event-loop tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pinsilico.server import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator

_TOKEN = "phase6-shutdown-token"  # noqa: S105 - fixture


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(token=_TOKEN)
    with TestClient(app) as c:
        yield c


class TestShutdown:
    def test_requires_token(self, client: TestClient) -> None:
        r = client.post("/shutdown")
        assert r.status_code == 401

    def test_returns_202_with_envelope_friendly_body(self, client: TestClient) -> None:
        r = client.post("/shutdown", headers={"X-Pinsilico-Token": _TOKEN})
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "scheduled"
        assert "message" in body
