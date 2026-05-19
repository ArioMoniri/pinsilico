"""fpocket adapter tests with subprocess fully mocked.

The real fpocket binary is bundled by Phase 12 packaging. For unit
tests we mock ``subprocess.run`` and lay down fixture files matching
the directory layout fpocket actually produces:

    <out_dir>/<receptor>_info.txt
    <out_dir>/pockets/pocket{n}_vert.pqr

A separate integration test (Phase 3 DoD calls for the 1HSG pocket
inside 3 Å of the indinavir centre of mass) lives in
``tests/integration/`` and is skipped unless ``FPOCKET_BIN`` is set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import numpy as np
import pytest
from pinsilico.pocket.base import Pocket, PocketDetectionError
from pinsilico.pocket.fpocket import FpocketDetector, _parse_info_txt, _pocket_centroid

if TYPE_CHECKING:
    from pathlib import Path


# Minimal-but-valid fpocket info.txt for two pockets, ranked by druggability.
_INFO_TXT = """\
Pocket 1 :
\tScore : \t\t\t0.9300
\tDruggability Score : \t0.9543
\tNumber of Alpha Spheres : \t75
\tTotal SASA : \t\t171.4
\tPolar SASA : \t\t51.2
\tApolar SASA : \t\t120.1
\tVolume : \t\t\t893.2
\tMean local hydrophobic density : \t\t54.0

Pocket 2 :
\tScore : \t\t\t0.6100
\tDruggability Score : \t0.4210
\tNumber of Alpha Spheres : \t31
\tTotal SASA : \t\t82.7
\tPolar SASA : \t\t28.1
\tApolar SASA : \t\t54.6
\tVolume : \t\t\t312.5
\tMean local hydrophobic density : \t\t31.0
"""

# Tiny PQR vertex file. fpocket alpha-sphere lines look like:
# ATOM      1  C   STP A 999      24.500  18.300  12.100  0.00  3.50
_POCKET_1_VERT_PQR = """\
ATOM      1  C   STP A 999      24.500  18.300  12.100  0.00  3.50
ATOM      2  C   STP A 999      25.000  19.000  12.500  0.00  3.20
ATOM      3  C   STP A 999      24.000  18.700  12.300  0.00  3.40
"""

_POCKET_2_VERT_PQR = """\
ATOM      1  C   STP A 999       5.000   8.000   2.000  0.00  3.50
ATOM      2  C   STP A 999       5.500   8.300   2.200  0.00  3.20
"""


def _make_fpocket_output(workdir: Path, receptor_name: str = "receptor") -> Path:
    """Build a fake fpocket output tree under ``workdir``."""
    out_dir = workdir / f"{receptor_name}_out"
    out_dir.mkdir(parents=True)
    (out_dir / f"{receptor_name}_info.txt").write_text(_INFO_TXT)
    pockets_dir = out_dir / "pockets"
    pockets_dir.mkdir()
    (pockets_dir / "pocket1_vert.pqr").write_text(_POCKET_1_VERT_PQR)
    (pockets_dir / "pocket2_vert.pqr").write_text(_POCKET_2_VERT_PQR)
    return out_dir


class TestParseInfoTxt:
    def test_extracts_two_pockets(self) -> None:
        parsed = _parse_info_txt(_INFO_TXT)
        assert len(parsed) == 2
        assert parsed[0]["pocket_number"] == 1
        assert parsed[0]["druggability"] == pytest.approx(0.9543)
        assert parsed[0]["volume"] == pytest.approx(893.2)
        assert parsed[1]["pocket_number"] == 2
        assert parsed[1]["druggability"] == pytest.approx(0.421)
        assert parsed[1]["volume"] == pytest.approx(312.5)

    def test_extracts_hydrophobic_density(self) -> None:
        parsed = _parse_info_txt(_INFO_TXT)
        assert parsed[0]["hydrophobic_density"] == pytest.approx(54.0)
        assert parsed[1]["hydrophobic_density"] == pytest.approx(31.0)

    def test_empty_input_returns_empty_list(self) -> None:
        assert _parse_info_txt("") == []


class TestPocketCentroid:
    def test_centroid_is_mean_of_atom_xyz(self, tmp_path: Path) -> None:
        pqr = tmp_path / "p.pqr"
        pqr.write_text(_POCKET_1_VERT_PQR)
        c = _pocket_centroid(pqr)
        # Mean of (24.5, 25.0, 24.0), (18.3, 19.0, 18.7), (12.1, 12.5, 12.3)
        assert c == pytest.approx(np.array([24.5, 18.6667, 12.3]), rel=1e-2)

    def test_missing_pqr_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PocketDetectionError):
            _pocket_centroid(tmp_path / "nope.pqr")

    def test_empty_pqr_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.pqr"
        empty.write_text("")
        with pytest.raises(PocketDetectionError):
            _pocket_centroid(empty)


class TestFpocketDetector:
    def test_detect_parses_full_output(self, tmp_path: Path) -> None:
        # Lay down the receptor on disk
        receptor = tmp_path / "receptor.pdb"
        receptor.write_text("HEADER fake\nEND\n")

        # Pre-build the fpocket output tree that the subprocess will "produce"
        _make_fpocket_output(tmp_path, receptor_name="receptor")

        det = FpocketDetector(binary_path="fpocket", workdir=tmp_path)
        # Mock subprocess.run to return successfully without doing anything;
        # the output tree is already on disk.
        with patch("pinsilico.pocket.fpocket.subprocess.run") as run:
            run.return_value.returncode = 0
            pockets = det.detect_from_path(receptor)

        assert len(pockets) == 2
        assert isinstance(pockets[0], Pocket)
        # Pocket 1 (most druggable) ranks first
        assert pockets[0].identifier == "pocket-1"
        assert pockets[0].druggability_score == pytest.approx(0.9543)
        assert pockets[0].volume_a3 == pytest.approx(893.2)
        # Centroid in real receptor coords
        assert pockets[0].centroid_xyz[0] == pytest.approx(24.5, rel=1e-2)

    def test_nonzero_exit_raises(self, tmp_path: Path) -> None:
        receptor = tmp_path / "r.pdb"
        receptor.write_text("HEADER\nEND\n")
        det = FpocketDetector(binary_path="fpocket", workdir=tmp_path)
        with patch("pinsilico.pocket.fpocket.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "fpocket: bad receptor"
            with pytest.raises(PocketDetectionError):
                det.detect_from_path(receptor)

    def test_missing_binary_raises(self, tmp_path: Path) -> None:
        receptor = tmp_path / "r.pdb"
        receptor.write_text("HEADER\nEND\n")
        det = FpocketDetector(binary_path="fpocket", workdir=tmp_path)
        with (
            patch(
                "pinsilico.pocket.fpocket.subprocess.run",
                side_effect=FileNotFoundError("no such binary"),
            ),
            pytest.raises(PocketDetectionError, match="binary"),
        ):
            det.detect_from_path(receptor)

    def test_no_pockets_returns_empty_list(self, tmp_path: Path) -> None:
        receptor = tmp_path / "receptor.pdb"
        receptor.write_text("HEADER\nEND\n")
        # Build an empty out_dir (fpocket ran but found nothing)
        out_dir = tmp_path / "receptor_out"
        out_dir.mkdir()
        (out_dir / "receptor_info.txt").write_text("")
        (out_dir / "pockets").mkdir()

        det = FpocketDetector(binary_path="fpocket", workdir=tmp_path)
        with patch("pinsilico.pocket.fpocket.subprocess.run") as run:
            run.return_value.returncode = 0
            pockets = det.detect_from_path(receptor)
        assert pockets == []

    def test_detect_from_string_writes_temp_file(self, tmp_path: Path) -> None:
        det = FpocketDetector(binary_path="fpocket", workdir=tmp_path)
        # Pre-build output tree under the deterministic receptor name fpocket
        # will produce from the temp file the detector creates.
        # The detector hashes the input to pick a stable temp filename.
        with patch("pinsilico.pocket.fpocket.subprocess.run") as run:
            run.return_value.returncode = 0
            # Build out_dir matching whatever receptor name the detector
            # picks. Easiest: patch _stem_for_text to a known value.
            with patch(
                "pinsilico.pocket.fpocket._stem_for_text",
                return_value="probe",
            ):
                _make_fpocket_output(tmp_path, receptor_name="probe")
                pockets = det.detect("HEADER\nATOM      1  CA  ALA A 1     0.0 0.0 0.0\nEND")
        assert len(pockets) == 2
