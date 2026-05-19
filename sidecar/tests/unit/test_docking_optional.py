"""DiffDock + Boltz-2 adapter tests.

Both adapters require downloaded weights (BUILD_PROMPT.md §3: "DiffDock and
Boltz-2 weights are optional, gated behind an explicit 'Download extra
engines' action"). When the weights aren't present they raise
DockingError with code ENGINE_NOT_AVAILABLE so the Phase 5 route layer
can return a 409 with a download URL.

When weights *are* present, the adapter shells out to the inference
binary; Phase 12 wires that path with real model invocation. For Phase
3 we test the gate + the path-resolution helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from pinsilico.docking.base import DockingBox, DockingError
from pinsilico.docking.boltz import BoltzAdapter
from pinsilico.docking.diffdock import DiffDockAdapter

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def box() -> DockingBox:
    return DockingBox(
        center_xyz=np.array([10.0, 10.0, 10.0]),
        size_xyz=np.array([20.0, 20.0, 20.0]),
    )


class TestDiffDockAdapter:
    def test_engine_slug(self, tmp_path: Path) -> None:
        a = DiffDockAdapter(weights_dir=tmp_path, workdir=tmp_path)
        assert a.engine == "diffdock"

    def test_missing_weights_raises_engine_not_available(
        self, tmp_path: Path, box: DockingBox
    ) -> None:
        nowhere = tmp_path / "no-such-weights"
        a = DiffDockAdapter(weights_dir=nowhere, workdir=tmp_path)
        with pytest.raises(DockingError) as exc:
            a.dock(receptor_pdb="HEADER\nEND\n", ligand_smiles="CCO", box=box)
        assert exc.value.engine == "diffdock"
        assert "ENGINE_NOT_AVAILABLE" in str(exc.value) or "weights" in str(exc.value).lower()

    def test_present_weights_pass_the_gate(self, tmp_path: Path, box: DockingBox) -> None:
        weights = tmp_path / "weights"
        weights.mkdir()
        (weights / "model.ckpt").write_bytes(b"")
        a = DiffDockAdapter(weights_dir=weights, workdir=tmp_path)
        # The inference path lands behind Phase 12 wiring; for now we
        # assert that the weights gate accepts the dir without raising.
        with pytest.raises(DockingError, match="inference path lands"):
            a.dock(receptor_pdb="HEADER\nEND\n", ligand_smiles="CCO", box=box)

    def test_version_safe_when_weights_missing(self, tmp_path: Path) -> None:
        a = DiffDockAdapter(weights_dir=tmp_path / "nope", workdir=tmp_path)
        assert a.version() == "0.0.0"


class TestBoltzAdapter:
    def test_engine_slug(self, tmp_path: Path) -> None:
        a = BoltzAdapter(weights_dir=tmp_path, workdir=tmp_path)
        assert a.engine == "boltz"

    def test_missing_weights_raises_engine_not_available(
        self, tmp_path: Path, box: DockingBox
    ) -> None:
        a = BoltzAdapter(weights_dir=tmp_path / "nope", workdir=tmp_path)
        with pytest.raises(DockingError) as exc:
            a.dock(receptor_pdb="HEADER\nEND\n", ligand_smiles="CCO", box=box)
        assert exc.value.engine == "boltz"

    def test_affinity_only_no_poses_in_result_shape(self) -> None:
        # Phase 5 routes need to know that Boltz returns affinity but no
        # 3D poses (best_affinity exposed; poses can be a single
        # synthetic pose with empty pose_pdbqt).
        # Verified at the docstring level here; structural assertion
        # lives in the Phase 12 integration test when real weights run.
        assert BoltzAdapter.AFFINITY_ONLY is True
