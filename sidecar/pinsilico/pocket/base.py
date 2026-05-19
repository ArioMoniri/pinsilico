"""Shared types for the pocket-detection layer.

A detector implements :class:`PocketDetector` and returns a ranked list
of :class:`Pocket`. The Phase 5 route layer doesn't care whether the
underlying tool is fpocket, GETArea, MD-pocket, or a learned model — it
just consumes the typed records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class PocketDetectionError(RuntimeError):
    """Raised when a detector fails or finds no pockets."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


@dataclass(frozen=True, slots=True)
class Pocket:
    """A predicted binding pocket.

    Attributes:
        identifier: Detector-specific id (e.g. ``"pocket-1"``).
        centroid_xyz: 3-vector of pocket centroid in Å, in the receptor's
            coordinate frame.
        volume_a3: Estimated pocket volume in Å³.
        hydrophobicity: Detector-reported hydrophobicity score. Range and
            sign depend on the detector; consumers should not assume a
            normalised scale.
        druggability_score: Detector-reported druggability score. Higher
            is more druggable. Always in [0, 1] for fpocket; other
            detectors may use different scales.
        residue_ids: Tuple of residue identifiers lining the pocket, in
            ``"chain:resnum:resname"`` form. May be empty when the
            detector doesn't surface residue info.
    """

    identifier: str
    centroid_xyz: NDArray[np.float64]
    volume_a3: float
    hydrophobicity: float
    druggability_score: float
    residue_ids: tuple[str, ...]


class PocketDetector(Protocol):
    """Protocol every detector implements."""

    def detect(self, pdb_text: str) -> list[Pocket]:
        """Return a ranked list of pockets for the given PDB.

        Ranking is detector-specific (fpocket sorts by druggability).
        Implementations should raise :class:`PocketDetectionError` on
        failure rather than returning an empty list — an empty list
        means "the detector ran and found no pockets", which is a
        valid (if disappointing) outcome.
        """
        ...
