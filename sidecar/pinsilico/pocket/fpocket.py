"""fpocket adapter.

Wraps the fpocket binary (bundled by Phase 12 packaging at
``sidecar/resources/binaries/fpocket``). For unit tests, ``subprocess.run``
is mocked; an integration test in ``tests/integration/`` uses the real
binary when the ``FPOCKET_BIN`` env var is set.

fpocket's output layout::

    <workdir>/<receptor>_out/
        <receptor>_info.txt          # per-pocket scores
        pockets/
            pocket1_vert.pqr         # alpha-sphere vertices for pocket 1
            pocket2_vert.pqr
            …

This module parses ``info.txt`` for druggability + volume +
hydrophobic-density scores, and ``pocketN_vert.pqr`` for the centroid
(mean xyz of the alpha-sphere vertices).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pinsilico.pocket.base import Pocket, PocketDetectionError

# ---------------------------------------------------------------------- regex
# fpocket's info.txt has stable enough formatting that regex is reliable.
_POCKET_HEADER = re.compile(r"^Pocket\s+(\d+)\s*:", re.MULTILINE)
_FIELD_LINE = re.compile(r"^\s*([A-Za-z][\w ]+?)\s*:\s*([-+]?\d*\.?\d+)", re.MULTILINE)

# fpocket vertex PQR lines look like:
# ATOM      1  C   STP A 999      24.500  18.300  12.100  0.00  3.50
_PQR_XYZ_COLS = (30, 38, 38, 46, 46, 54)  # x[30:38], y[38:46], z[46:54]


def _stem_for_text(pdb_text: str) -> str:
    """Stable temp-receptor stem from a hash of the input text."""
    h = hashlib.sha1(pdb_text.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"probe_{h[:8]}"


def _parse_info_txt(text: str) -> list[dict[str, Any]]:
    """Parse fpocket's ``*_info.txt`` into a per-pocket list of dicts.

    Each dict has keys ``pocket_number``, ``druggability``, ``score``,
    ``volume``, ``hydrophobic_density``. Missing fields default to 0.0
    rather than raising — fpocket occasionally omits unstable metrics.
    """
    if not text.strip():
        return []
    out: list[dict[str, Any]] = []
    headers = list(_POCKET_HEADER.finditer(text))
    for i, header in enumerate(headers):
        pocket_number = int(header.group(1))
        block_start = header.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]
        fields: dict[str, float] = {}
        for m in _FIELD_LINE.finditer(block):
            label = m.group(1).strip().lower()
            try:
                fields[label] = float(m.group(2))
            except ValueError:
                continue
        out.append(
            {
                "pocket_number": pocket_number,
                "score": fields.get("score", 0.0),
                "druggability": fields.get("druggability score", 0.0),
                "volume": fields.get("volume", 0.0),
                "hydrophobic_density": fields.get(
                    "mean local hydrophobic density",
                    0.0,
                ),
            }
        )
    return out


def _pocket_centroid(pqr_path: Path) -> np.ndarray:
    """Return the mean xyz of alpha-sphere vertices in a fpocket PQR file."""
    if not pqr_path.exists():
        msg = f"fpocket PQR file missing: {pqr_path}"
        raise PocketDetectionError(msg)
    coords: list[tuple[float, float, float]] = []
    for line in pqr_path.read_text("utf-8").splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except (ValueError, IndexError):
            continue
        coords.append((x, y, z))
    if not coords:
        msg = f"fpocket PQR file had no parseable atoms: {pqr_path}"
        raise PocketDetectionError(msg)
    arr = np.array(coords, dtype=np.float64)
    centroid: np.ndarray = arr.mean(axis=0)
    return centroid


@dataclass
class FpocketDetector:
    """fpocket adapter.

    Args:
        binary_path: Path to the fpocket executable. Defaults to ``"fpocket"``
            on PATH; the bundled binary path is supplied by Phase 6 sidecar
            wiring.
        workdir: Directory where fpocket will write its ``<receptor>_out/``
            subtree. Defaults to a fresh per-call temp dir created by the
            caller; the test fixtures use ``tmp_path``.
    """

    binary_path: str = "fpocket"
    workdir: Path | None = None

    def detect(self, pdb_text: str) -> list[Pocket]:
        """Run fpocket against an in-memory PDB block."""
        if self.workdir is None:
            msg = "workdir must be set before calling detect()"
            raise PocketDetectionError(msg)
        stem = _stem_for_text(pdb_text)
        receptor_path = self.workdir / f"{stem}.pdb"
        receptor_path.write_text(pdb_text)
        return self.detect_from_path(receptor_path)

    def detect_from_path(self, receptor_path: Path) -> list[Pocket]:
        """Run fpocket against a PDB file on disk and parse its output."""
        if self.workdir is None:
            self.workdir = receptor_path.parent
        receptor_name = receptor_path.stem
        try:
            result = subprocess.run(  # noqa: S603 - binary path is trusted (bundled)
                [self.binary_path, "-f", str(receptor_path)],
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            msg = f"fpocket binary not found at {self.binary_path!r}"
            raise PocketDetectionError(msg, original=exc) from exc
        if result.returncode != 0:
            msg = f"fpocket exited {result.returncode}: {result.stderr.strip()}"
            raise PocketDetectionError(msg)

        out_dir = self.workdir / f"{receptor_name}_out"
        info_path = out_dir / f"{receptor_name}_info.txt"
        info_text = info_path.read_text("utf-8") if info_path.exists() else ""
        parsed = _parse_info_txt(info_text)

        pockets_dir = out_dir / "pockets"
        results: list[Pocket] = []
        for entry in parsed:
            n = entry["pocket_number"]
            vert = pockets_dir / f"pocket{n}_vert.pqr"
            if not vert.exists():
                continue
            centroid = _pocket_centroid(vert)
            results.append(
                Pocket(
                    identifier=f"pocket-{n}",
                    centroid_xyz=centroid,
                    volume_a3=entry["volume"],
                    hydrophobicity=entry["hydrophobic_density"],
                    druggability_score=entry["druggability"],
                    residue_ids=(),
                )
            )
        # fpocket already ranks by score; surface in that order.
        return results
