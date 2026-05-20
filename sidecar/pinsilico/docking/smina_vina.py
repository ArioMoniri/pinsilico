"""Smina / AutoDock Vina adapter.

Both engines share the same CLI surface (Vina is the upstream; Smina is
a Vina fork with better scoring). We wrap them in one adapter
parametrised by binary name and engine slug. The integration test that
runs the real binary against 1HSG + indinavir lives in
``tests/integration/`` and is gated by the ``SMINA_BIN`` / ``VINA_BIN``
env vars.

Receptor and ligand preparation use Open Babel internally
(``_prepare_*_pdbqt`` are thin wrappers — Phase 12 bundles ``obabel``
into ``sidecar/resources/binaries/``). For Phase 3 unit tests, the
helpers are patched to point at fixture files.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pinsilico.docking.base import DockingBox, DockingError, DockingResult, Pose

_REMARK_RE = re.compile(
    r"REMARK\s+VINA\s+RESULT:\s+(?P<aff>[-+]?\d+\.\d+)\s+"
    r"(?P<lb>[-+]?\d+\.\d+)\s+(?P<ub>[-+]?\d+\.\d+)",
)
_MODEL_RE = re.compile(r"^MODEL\s+\d+", re.MULTILINE)


def _resolve_obabel() -> str:
    """Find the obabel binary.

    Looks in this order:
    1. ``$OBABEL_BIN`` env override — useful for CI / per-user installs.
    2. ``sidecar/resources/binaries/obabel`` — Phase 12 bundled drop.
    3. ``shutil.which("obabel")`` — system PATH fallback.

    Raises :class:`DockingError` if none of the candidates exist; the
    route layer converts that to a user-facing 422.
    """
    env = os.environ.get("OBABEL_BIN")
    if env and Path(env).exists():
        return env
    bundled = Path(__file__).resolve().parents[2] / "resources" / "binaries" / "obabel"
    if bundled.exists():
        return str(bundled)
    on_path = shutil.which("obabel")
    if on_path is not None:
        return on_path
    msg = (
        "obabel binary not found. Install Open Babel and either put it on PATH, "
        "set the OBABEL_BIN environment variable, or drop a copy under "
        "sidecar/resources/binaries/obabel."
    )
    raise DockingError(msg, engine="obabel")


def _prepare_ligand_pdbqt(smiles: str, workdir: Path) -> Path:
    """Convert a SMILES string to a PDBQT file via Open Babel.

    Adds explicit hydrogens (``-h``) and generates 3D coordinates
    (``--gen3d``) so the docking engine has a sensible starting pose.
    Output goes to ``workdir/ligand.pdbqt``.
    """
    obabel = _resolve_obabel()
    out_path = workdir / "ligand.pdbqt"
    try:
        result = subprocess.run(  # noqa: S603 — args are not user-supplied shell text
            [obabel, f"-:{smiles}", "-O", str(out_path), "-h", "--gen3d"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise DockingError(
            f"obabel binary not executable: {obabel}",
            engine="obabel",
            original=exc,
        ) from exc
    if result.returncode != 0 or not out_path.exists():
        raise DockingError(
            f"obabel ligand prep failed ({result.returncode}): {result.stderr.strip()}",
            engine="obabel",
        )
    return out_path


def _prepare_receptor_pdbqt(pdb_text: str, workdir: Path) -> Path:
    """Convert a receptor PDB to PDBQT via Open Babel.

    Uses ``-xr`` (rigid receptor) and writes to ``workdir/receptor.pdbqt``.
    The input PDB text is written to a scratch ``.pdb`` file first because
    obabel reads from disk.
    """
    obabel = _resolve_obabel()
    pdb_path = workdir / "receptor.pdb"
    pdb_path.write_text(pdb_text, encoding="utf-8")
    out_path = workdir / "receptor.pdbqt"
    try:
        result = subprocess.run(  # noqa: S603
            [obabel, str(pdb_path), "-O", str(out_path), "-xr"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise DockingError(
            f"obabel binary not executable: {obabel}",
            engine="obabel",
            original=exc,
        ) from exc
    if result.returncode != 0 or not out_path.exists():
        raise DockingError(
            f"obabel receptor prep failed ({result.returncode}): {result.stderr.strip()}",
            engine="obabel",
        )
    return out_path


def _parse_pdbqt_output(text: str) -> list[Pose]:
    """Parse a Smina/Vina output PDBQT into a list of :class:`Pose`."""
    if not text.strip():
        return []
    model_starts = [m.start() for m in _MODEL_RE.finditer(text)]
    if not model_starts:
        return []
    model_starts.append(len(text))
    poses: list[Pose] = []
    for i in range(len(model_starts) - 1):
        block = text[model_starts[i] : model_starts[i + 1]]
        m = _REMARK_RE.search(block)
        if not m:
            continue
        poses.append(
            Pose(
                rank=i + 1,
                affinity_kcal_mol=float(m.group("aff")),
                rmsd_lb=float(m.group("lb")),
                rmsd_ub=float(m.group("ub")),
                pose_pdbqt=block.strip("\n"),
            )
        )
    return poses


@dataclass
class SminaVinaAdapter:
    """Shared adapter for Smina and AutoDock Vina.

    Args:
        engine_name: Slug returned by :meth:`engine` — ``"smina"`` or ``"vina"``.
        binary_path: Path to the Smina or Vina executable.
        workdir: Scratch directory for prep + run artefacts.
    """

    engine_name: str
    binary_path: str
    workdir: Path
    _version_cache: str = ""

    @property
    def engine(self) -> str:
        return self.engine_name

    def version(self) -> str:
        """Return ``<engine> --version`` output, cached after first call."""
        if self._version_cache:
            return self._version_cache
        try:
            result = subprocess.run(  # noqa: S603 - bundled binary
                [self.binary_path, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return "0.0.0"
        self._version_cache = (result.stdout or result.stderr or "0.0.0").strip()
        return self._version_cache

    def dock(
        self,
        *,
        receptor_pdb: str,
        ligand_smiles: str,
        box: DockingBox,
        exhaustiveness: int = 8,
        num_modes: int = 9,
        seed: int | None = None,
    ) -> DockingResult:
        """Run docking and return the parsed result."""
        ligand_pdbqt = _prepare_ligand_pdbqt(ligand_smiles, self.workdir)
        receptor_pdbqt = _prepare_receptor_pdbqt(receptor_pdb, self.workdir)
        out_pdbqt = self.workdir / "out.pdbqt"

        cmd: list[str] = [
            self.binary_path,
            "--receptor",
            str(receptor_pdbqt),
            "--ligand",
            str(ligand_pdbqt),
            "--out",
            str(out_pdbqt),
            "--center_x",
            f"{box.center_xyz[0]:.3f}",
            "--center_y",
            f"{box.center_xyz[1]:.3f}",
            "--center_z",
            f"{box.center_xyz[2]:.3f}",
            "--size_x",
            f"{box.size_xyz[0]:.3f}",
            "--size_y",
            f"{box.size_xyz[1]:.3f}",
            "--size_z",
            f"{box.size_xyz[2]:.3f}",
            "--exhaustiveness",
            str(exhaustiveness),
            "--num_modes",
            str(num_modes),
        ]
        if seed is not None:
            cmd.extend(["--seed", str(seed)])

        try:
            result = subprocess.run(  # noqa: S603 - bundled binary
                cmd,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            msg = f"{self.engine_name} binary not found at {self.binary_path!r}"
            raise DockingError(msg, engine=self.engine_name, original=exc) from exc

        if result.returncode != 0:
            msg = (
                f"{self.engine_name} exited {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
            raise DockingError(msg, engine=self.engine_name)

        if not out_pdbqt.exists():
            msg = f"{self.engine_name} did not produce an output file at {out_pdbqt}"
            raise DockingError(msg, engine=self.engine_name)

        poses = tuple(_parse_pdbqt_output(out_pdbqt.read_text("utf-8")))
        if not poses:
            msg = f"{self.engine_name} produced no poses"
            raise DockingError(msg, engine=self.engine_name)

        return DockingResult(
            engine=self.engine_name,
            engine_version=self.version(),
            receptor_id="",
            ligand_smiles=ligand_smiles,
            pocket_id=None,
            box=box,
            poses=poses,
        )
