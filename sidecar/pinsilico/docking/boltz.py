"""Boltz-2 adapter (affinity-only).

Optional engine — weights (~1.5 GB) are not bundled by default.
BUILD_PROMPT.md §3 calls Boltz-2 an "affinity-only fallback when the
user doesn't care about poses". When the engine runs it returns a
single :class:`Pose` with the predicted affinity and an empty
``pose_pdbqt``; consumers should read :attr:`DockingResult.best_affinity_kcal_mol`
rather than the pose geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pinsilico.docking.base import DockingBox, DockingError, DockingResult

BOLTZ_WEIGHTS_URL = (
    "https://github.com/jwohlwend/boltz/releases/download/v0.4.0/boltz2-affinity.tar.gz"
)


def _weights_present(weights_dir: Path) -> bool:
    if not weights_dir.exists() or not weights_dir.is_dir():
        return False
    return any(weights_dir.glob("*.tar.gz") or weights_dir.glob("*.pt"))


@dataclass
class BoltzAdapter:
    """Boltz-2 affinity-only docking."""

    weights_dir: Path
    workdir: Path
    engine_name: str = "boltz"

    AFFINITY_ONLY: ClassVar[bool] = True
    """Boltz-2 returns affinity values but no 3D pose. Consumers
    branching on pose vs. score should check this flag."""

    @property
    def engine(self) -> str:
        return self.engine_name

    def version(self) -> str:
        return "0.0.0" if not _weights_present(self.weights_dir) else "0.4.0"

    def dock(
        self,
        *,
        receptor_pdb: str,  # noqa: ARG002 - Phase 12 placeholder
        ligand_smiles: str,  # noqa: ARG002
        box: DockingBox,  # noqa: ARG002
        exhaustiveness: int = 8,  # noqa: ARG002
        num_modes: int = 9,  # noqa: ARG002
        seed: int | None = None,  # noqa: ARG002
    ) -> DockingResult:
        if not _weights_present(self.weights_dir):
            msg = (
                f"Boltz-2 weights not found under {self.weights_dir}. "
                "ENGINE_NOT_AVAILABLE — user must accept the download "
                f"({BOLTZ_WEIGHTS_URL}) before docking."
            )
            raise DockingError(msg, engine=self.engine_name)

        msg = (
            "Boltz-2 weights present, but the affinity-inference path "
            "lands with Phase 12 sidecar wiring."
        )
        raise DockingError(msg, engine=self.engine_name)
