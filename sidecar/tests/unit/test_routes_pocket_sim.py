"""Tests for /pocket/detect and /sim/* routes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pinsilico.pocket.base import Pocket, PocketDetectionError
from pinsilico.server import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator

import numpy as np

_TOKEN = "phase5-pocket-sim-token"  # noqa: S105 - fixture, not a credential


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(token=_TOKEN)
    with TestClient(app) as c:
        yield c


def _hdr() -> dict[str, str]:
    return {"X-Pinsilico-Token": _TOKEN}


class TestPocketDetect:
    def test_requires_token(self, client: TestClient) -> None:
        r = client.post("/pocket/detect", json={"pdb_text": "HEADER\n"})
        assert r.status_code == 401

    def test_calls_detector_and_returns_pockets(self, client: TestClient) -> None:
        fake_pockets = [
            Pocket(
                identifier="pocket-1",
                centroid_xyz=np.array([24.5, 18.7, 12.3]),
                volume_a3=893.2,
                hydrophobicity=54.0,
                druggability_score=0.9543,
                residue_ids=(),
            ),
        ]
        with patch(
            "pinsilico.routes.pocket.FpocketDetector",
        ) as factory:
            instance = factory.return_value
            instance.detect.return_value = fake_pockets
            r = client.post(
                "/pocket/detect",
                json={"pdb_text": "HEADER\nEND\n", "binary_path": "fpocket"},
                headers=_hdr(),
            )
        assert r.status_code == 200
        body = r.json()
        assert len(body["pockets"]) == 1
        p = body["pockets"][0]
        assert p["identifier"] == "pocket-1"
        assert p["centroid_xyz"] == [24.5, 18.7, 12.3]
        assert p["druggability_score"] == pytest.approx(0.9543)

    def test_empty_pdb_validation_error(self, client: TestClient) -> None:
        r = client.post("/pocket/detect", json={"pdb_text": ""}, headers=_hdr())
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_detection_failure_500(self, client: TestClient) -> None:
        with patch("pinsilico.routes.pocket.FpocketDetector") as factory:
            factory.return_value.detect.side_effect = PocketDetectionError("binary missing")
            r = client.post(
                "/pocket/detect",
                json={"pdb_text": "HEADER\nEND\n"},
                headers=_hdr(),
            )
        assert r.status_code == 500
        assert r.json()["error"]["code"] == "POCKET_DETECTION_FAILED"


class TestSimFastForward:
    def test_returns_counts(self, client: TestClient) -> None:
        body = {
            "sites": [
                {
                    "identifier": "strong",
                    "centroid_xyz": [0.0, 0.0, 0.0],
                    "radius_a": 5.0,
                    "dg_kcal_mol": -9.0,
                },
                {
                    "identifier": "weak",
                    "centroid_xyz": [10.0, 0.0, 0.0],
                    "radius_a": 5.0,
                    "dg_kcal_mol": -3.0,
                },
            ],
            "n_events": 500,
            "seed": 42,
            "temperature_k": 298.0,
        }
        r = client.post("/sim/fast_forward", json=body, headers=_hdr())
        assert r.status_code == 200
        out = r.json()
        assert out["n_events"] == 500
        assert sum(out["counts"].values()) == 500
        # Strong site should win the majority
        assert out["counts"]["strong"] > out["counts"]["weak"]

    def test_deterministic_under_seed(self, client: TestClient) -> None:
        body = {
            "sites": [
                {"identifier": "a", "centroid_xyz": [0, 0, 0], "radius_a": 5, "dg_kcal_mol": -6},
                {"identifier": "b", "centroid_xyz": [10, 0, 0], "radius_a": 5, "dg_kcal_mol": -6},
            ],
            "n_events": 200,
            "seed": 123,
        }
        a = client.post("/sim/fast_forward", json=body, headers=_hdr()).json()
        b = client.post("/sim/fast_forward", json=body, headers=_hdr()).json()
        assert a == b

    def test_invalid_n_events_422(self, client: TestClient) -> None:
        r = client.post(
            "/sim/fast_forward",
            json={"sites": [], "n_events": 0},
            headers=_hdr(),
        )
        assert r.status_code == 422


class TestSimRun:
    def test_runs_and_returns_final_state(self, client: TestClient) -> None:
        body = {
            "sites": [],
            "particles": [{"position": [0.0, 0.0, 0.0]}],
            "diffusion_coeff_a2_per_frame": 1.0,
            "n_frames": 10,
            "seed": 1,
            "box_size_a": 200.0,
            "use_attraction": False,
        }
        r = client.post("/sim/run", json=body, headers=_hdr())
        assert r.status_code == 200
        out = r.json()
        assert out["frames_executed"] == 10
        assert len(out["final_positions"]) == 1
        assert len(out["bound_site_ids"]) == 1
        assert out["bound_site_ids"][0] is None  # no sites → unbound

    def test_requires_token(self, client: TestClient) -> None:
        r = client.post("/sim/run", json={"sites": [], "n_frames": 1})
        assert r.status_code == 401
