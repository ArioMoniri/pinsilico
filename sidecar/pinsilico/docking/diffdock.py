"""DiffDock adapter.

Optional engine — weights (~3 GB) are not bundled by default.
BUILD_PROMPT.md §3 / §1 P3 require:

* If weights are not under :attr:`weights_dir`, ``dock()`` raises
  :class:`DockingError` with code ``ENGINE_NOT_AVAILABLE`` and a
  download URL in ``details``. The Phase 5 route layer maps this to a
  409 Conflict the frontend can confirm before fetching weights.
* If weights are present, the real inference path runs (Phase 12 wires
  the actual diffdock-cli invocation).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pinsilico.docking.base import DockingBox, DockingError, DockingResult

DIFFDOCK_WEIGHTS_URL = "https://github.com/gcorso/DiffDock/releases/download/v1.1.2/weights.zip"


def _weights_present(weights_dir: Path) -> bool:
    """Return True iff ``weights_dir`` exists and contains at least one .ckpt."""
    if not weights_dir.exists() or not weights_dir.is_dir():
        return False
    return any(weights_dir.glob("*.ckpt"))


@dataclass
class DiffDockAdapter:
    """DiffDock docking via the bundled diffdock-cli (Phase 12 wires the call)."""

    weights_dir: Path
    workdir: Path
    engine_name: str = "diffdock"

    @property
    def engine(self) -> str:
        return self.engine_name

    def version(self) -> str:
        """Best-effort version. Returns ``0.0.0`` when weights are missing.

        DiffDock's version is encoded in the weights bundle; we don't try
        to dig it out before the user has agreed to download the weights.
        """
        return "0.0.0" if not _weights_present(self.weights_dir) else "1.1.2"

    def dock(
        self,
        *,
        receptor_pdb: str,  # noqa: ARG002 - signature placeholder for Phase 12
        ligand_smiles: str,  # noqa: ARG002
        box: DockingBox,  # noqa: ARG002
        exhaustiveness: int = 8,  # noqa: ARG002
        num_modes: int = 9,  # noqa: ARG002
        seed: int | None = None,  # noqa: ARG002
    ) -> DockingResult:
        if not _weights_present(self.weights_dir):
            msg = (
                f"DiffDock weights not found under {self.weights_dir}. "
                "ENGINE_NOT_AVAILABLE — user must accept the download "
                f"({DIFFDOCK_WEIGHTS_URL}) before docking."
            )
            raise DockingError(msg, engine=self.engine_name)

        # Weights present, but the actual diffdock-cli invocation lands
        # with Phase 12 binary bundling. Until then, fail loud so callers
        # don't silently get an empty result.
        msg = (
            "DiffDock weights present, but the inference path lands "
            "with Phase 12 sidecar wiring."
        )
        raise DockingError(msg, engine=self.engine_name)
