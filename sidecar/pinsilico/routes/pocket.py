"""``/pocket/*`` routes.

Wraps :class:`pinsilico.pocket.fpocket.FpocketDetector`. Phase 5 limits
the surface to one POST: detect pockets in a supplied PDB block.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from pinsilico.pocket.base import Pocket, PocketDetectionError
from pinsilico.pocket.fpocket import FpocketDetector

router = APIRouter(prefix="/pocket", tags=["pocket"])


class DetectRequest(BaseModel):
    pdb_text: str = Field(min_length=1, description="Raw PDB block")
    binary_path: str = Field(
        default="fpocket",
        description="Override fpocket binary path (Phase 6 wires the bundled path)",
    )


class PocketResponse(BaseModel):
    identifier: str
    centroid_xyz: tuple[float, float, float]
    volume_a3: float
    hydrophobicity: float
    druggability_score: float
    residue_ids: tuple[str, ...]

    @classmethod
    def from_dataclass(cls, p: Pocket) -> PocketResponse:
        return cls(
            identifier=p.identifier,
            centroid_xyz=tuple(float(x) for x in p.centroid_xyz),  # type: ignore[arg-type]
            volume_a3=p.volume_a3,
            hydrophobicity=p.hydrophobicity,
            druggability_score=p.druggability_score,
            residue_ids=p.residue_ids,
        )


class DetectResponse(BaseModel):
    pockets: list[PocketResponse]


@router.post(
    "/detect",
    response_model=DetectResponse,
    summary="Detect binding pockets via fpocket",
    description=(
        "Runs fpocket against the supplied PDB and returns the ranked "
        "pocket list. Pocket centroids are the simulation engine's "
        "binding-site coordinates (BUILD_PROMPT.md §8.2)."
    ),
    responses={
        200: {"description": "Pockets ranked by fpocket druggability."},
        500: {"description": "fpocket failed (binary missing, bad input, etc.)."},
    },
)
def pocket_detect(req: Annotated[DetectRequest, Body()]) -> DetectResponse:
    with tempfile.TemporaryDirectory(prefix="pinsilico-pocket-") as tmp:
        detector = FpocketDetector(binary_path=req.binary_path, workdir=Path(tmp))
        try:
            pockets = detector.detect(req.pdb_text)
        except PocketDetectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "POCKET_DETECTION_FAILED", "message": str(exc)},
            ) from exc
    return DetectResponse(pockets=[PocketResponse.from_dataclass(p) for p in pockets])


__all__: list[str] = ["router"]


_: Any = None  # silence ARG warnings in type-check passes
