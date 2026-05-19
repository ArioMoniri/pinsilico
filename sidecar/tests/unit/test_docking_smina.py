"""Smina / AutoDock Vina adapter tests with subprocess fully mocked.

Smina and Vina share the same CLI surface (Vina is the upstream; Smina is
a fork with better scoring); we wrap them in one adapter parametrised by
binary name. The integration test that actually invokes the binary
against 1HSG + indinavir lives in tests/integration/ and is skipped
unless SMINA_BIN / VINA_BIN are set.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from pinsilico.docking.base import DockingBox, DockingError
from pinsilico.docking.smina_vina import (
    SminaVinaAdapter,
    _parse_pdbqt_output,
)

# Fixture Vina output: 2 poses with REMARK VINA RESULT lines, plus a tiny
# atom record so the pose isn't completely empty.
_FAKE_PDBQT_OUT = """\
MODEL 1
REMARK VINA RESULT:      -9.4      0.000      0.000
ATOM      1  C   LIG A   1      12.345  23.456  34.567  0.00  0.00     0.000 C
ENDMDL
MODEL 2
REMARK VINA RESULT:      -8.7      1.234      2.345
ATOM      1  C   LIG A   1      12.500  23.500  34.700  0.00  0.00     0.000 C
ENDMDL
"""


class TestParsePdbqtOutput:
    def test_extracts_two_poses(self) -> None:
        poses = _parse_pdbqt_output(_FAKE_PDBQT_OUT)
        assert len(poses) == 2

    def test_affinities_correct(self) -> None:
        poses = _parse_pdbqt_output(_FAKE_PDBQT_OUT)
        assert poses[0].affinity_kcal_mol == pytest.approx(-9.4)
        assert poses[1].affinity_kcal_mol == pytest.approx(-8.7)

    def test_rmsds_correct(self) -> None:
        poses = _parse_pdbqt_output(_FAKE_PDBQT_OUT)
        assert poses[0].rmsd_lb == pytest.approx(0.0)
        assert poses[1].rmsd_lb == pytest.approx(1.234)
        assert poses[1].rmsd_ub == pytest.approx(2.345)

    def test_ranks_are_one_indexed(self) -> None:
        poses = _parse_pdbqt_output(_FAKE_PDBQT_OUT)
        assert poses[0].rank == 1
        assert poses[1].rank == 2

    def test_empty_input_returns_empty(self) -> None:
        assert _parse_pdbqt_output("") == []

    def test_pose_text_preserved(self) -> None:
        poses = _parse_pdbqt_output(_FAKE_PDBQT_OUT)
        assert "REMARK VINA RESULT" in poses[0].pose_pdbqt
        assert "ATOM" in poses[0].pose_pdbqt


@pytest.fixture
def receptor_pdb() -> str:
    return "HEADER  FAKE\nATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n"


@pytest.fixture
def docking_box() -> DockingBox:
    return DockingBox(
        center_xyz=np.array([10.0, 10.0, 10.0]),
        size_xyz=np.array([20.0, 20.0, 20.0]),
    )


class TestSminaVinaAdapterDock:
    def test_returns_docking_result_with_poses(
        self, tmp_path: Path, receptor_pdb: str, docking_box: DockingBox
    ) -> None:
        adapter = SminaVinaAdapter(
            engine_name="smina",
            binary_path="smina",
            workdir=tmp_path,
        )

        # Mock subprocess.run so it writes our fake output to wherever the
        # adapter asked for --out, returns 0.
        def fake_run(cmd: list[str], **_kw: object) -> object:
            # Find --out target
            out_path = None
            for i, arg in enumerate(cmd):
                if arg == "--out":
                    out_path = cmd[i + 1]
                    break
            if out_path is not None:
                Path(out_path).write_text(_FAKE_PDBQT_OUT)

            class _Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return _Result()

        with (
            patch(
                "pinsilico.docking.smina_vina._prepare_ligand_pdbqt",
                return_value=tmp_path / "lig.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina._prepare_receptor_pdbqt",
                return_value=tmp_path / "rec.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina.subprocess.run",
                side_effect=fake_run,
            ),
        ):
            (tmp_path / "lig.pdbqt").write_text("dummy\n")
            (tmp_path / "rec.pdbqt").write_text("dummy\n")
            result = adapter.dock(
                receptor_pdb=receptor_pdb,
                ligand_smiles="CCO",
                box=docking_box,
                exhaustiveness=4,
                num_modes=2,
                seed=42,
            )

        assert result.engine == "smina"
        assert len(result.poses) == 2
        assert result.best_affinity_kcal_mol == pytest.approx(-9.4)
        assert result.ligand_smiles == "CCO"

    def test_nonzero_exit_raises(
        self, tmp_path: Path, receptor_pdb: str, docking_box: DockingBox
    ) -> None:
        adapter = SminaVinaAdapter(
            engine_name="smina",
            binary_path="smina",
            workdir=tmp_path,
        )

        class _BadResult:
            returncode = 1
            stdout = ""
            stderr = "smina: invalid receptor"

        with (
            patch(
                "pinsilico.docking.smina_vina._prepare_ligand_pdbqt",
                return_value=tmp_path / "lig.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina._prepare_receptor_pdbqt",
                return_value=tmp_path / "rec.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina.subprocess.run",
                return_value=_BadResult(),
            ),
        ):
            (tmp_path / "lig.pdbqt").write_text("dummy\n")
            (tmp_path / "rec.pdbqt").write_text("dummy\n")
            with pytest.raises(DockingError) as exc:
                adapter.dock(
                    receptor_pdb=receptor_pdb,
                    ligand_smiles="CCO",
                    box=docking_box,
                )
            assert exc.value.engine == "smina"

    def test_missing_binary_raises(
        self, tmp_path: Path, receptor_pdb: str, docking_box: DockingBox
    ) -> None:
        adapter = SminaVinaAdapter(
            engine_name="vina",
            binary_path="vina",
            workdir=tmp_path,
        )
        (tmp_path / "lig.pdbqt").write_text("dummy\n")
        (tmp_path / "rec.pdbqt").write_text("dummy\n")
        with (
            patch(
                "pinsilico.docking.smina_vina._prepare_ligand_pdbqt",
                return_value=tmp_path / "lig.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina._prepare_receptor_pdbqt",
                return_value=tmp_path / "rec.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina.subprocess.run",
                side_effect=FileNotFoundError("not found"),
            ),
            pytest.raises(DockingError, match="binary"),
        ):
            adapter.dock(
                receptor_pdb=receptor_pdb,
                ligand_smiles="CCO",
                box=docking_box,
            )

    def test_engine_property(self, tmp_path: Path) -> None:
        smina = SminaVinaAdapter(engine_name="smina", binary_path="smina", workdir=tmp_path)
        vina = SminaVinaAdapter(engine_name="vina", binary_path="vina", workdir=tmp_path)
        assert smina.engine == "smina"
        assert vina.engine == "vina"

    def test_no_poses_raises(
        self, tmp_path: Path, receptor_pdb: str, docking_box: DockingBox
    ) -> None:
        adapter = SminaVinaAdapter(
            engine_name="smina",
            binary_path="smina",
            workdir=tmp_path,
        )

        def fake_run_empty(cmd: list[str], **_kw: object) -> object:
            for i, arg in enumerate(cmd):
                if arg == "--out":
                    Path(cmd[i + 1]).write_text("")  # no poses
                    break

            class _Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return _Result()

        with (
            patch(
                "pinsilico.docking.smina_vina._prepare_ligand_pdbqt",
                return_value=tmp_path / "lig.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina._prepare_receptor_pdbqt",
                return_value=tmp_path / "rec.pdbqt",
            ),
            patch(
                "pinsilico.docking.smina_vina.subprocess.run",
                side_effect=fake_run_empty,
            ),
        ):
            (tmp_path / "lig.pdbqt").write_text("dummy\n")
            (tmp_path / "rec.pdbqt").write_text("dummy\n")
            with pytest.raises(DockingError, match="no poses"):
                adapter.dock(
                    receptor_pdb=receptor_pdb,
                    ligand_smiles="CCO",
                    box=docking_box,
                )
