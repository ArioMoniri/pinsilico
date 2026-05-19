"""Shared types for docking adapters.

Every adapter implements :class:`DockingAdapter` and returns a
:class:`DockingResult`. The Phase 5 route layer dispatches by engine name
and surfaces the result to the webview.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class DockingError(RuntimeError):
    """Raised when a docking adapter fails."""

    def __init__(self, message: str, *, engine: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.engine = engine
        self.original = original


@dataclass(frozen=True, slots=True)
class DockingBox:
    """Docking search box.

    Attributes:
        center_xyz: 3-vector centre in Å (typically the pocket centroid).
        size_xyz: 3-vector box dimensions in Å. 20 Å is a common default
            for inhibitor-sized ligands.
    """

    center_xyz: NDArray[np.float64]
    size_xyz: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Pose:
    """One predicted ligand pose.

    Attributes:
        rank: 1-indexed pose rank within the result set.
        affinity_kcal_mol: Predicted binding affinity in kcal/mol. More
            negative = stronger binding.
        rmsd_lb: RMSD lower bound vs the best pose (Å); 0 for rank 1.
        rmsd_ub: RMSD upper bound vs the best pose (Å); 0 for rank 1.
        pose_pdbqt: Raw PDBQT block for this pose. Empty when the adapter
            only returned affinities (e.g. Boltz-2).
    """

    rank: int
    affinity_kcal_mol: float
    rmsd_lb: float
    rmsd_ub: float
    pose_pdbqt: str


@dataclass(frozen=True, slots=True)
class DockingResult:
    """A complete docking run result."""

    engine: str
    engine_version: str
    receptor_id: str
    ligand_smiles: str
    pocket_id: str | None
    box: DockingBox
    poses: tuple[Pose, ...]

    @property
    def best_affinity_kcal_mol(self) -> float:
        """Most-negative affinity across all poses. Lower = stronger."""
        if not self.poses:
            msg = "DockingResult has no poses"
            raise ValueError(msg)
        return min(p.affinity_kcal_mol for p in self.poses)


class DockingAdapter(Protocol):
    """Protocol every docking adapter implements."""

    @property
    def engine(self) -> str:
        """Short slug ('smina', 'vina', 'diffdock', 'boltz')."""
        ...

    def version(self) -> str:
        """Engine version string (or '0.0.0' if unknown)."""
        ...

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
        """Run docking. Raise :class:`DockingError` on failure."""
        ...
