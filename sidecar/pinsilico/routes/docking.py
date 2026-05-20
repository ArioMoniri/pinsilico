"""HTTP route for the Smina / Vina docking dispatch.

Wraps :class:`SminaVinaAdapter` (Phase 3 docking adapter) for the
workspace UI. Two engines share the same code path — the request body
chooses Smina or Vina via the ``engine`` field, and the route resolves
the binary in the same precedence the lockfile uses:

1. ``$SMINA_BIN`` / ``$VINA_BIN`` environment override.
2. ``sidecar/resources/binaries/{smina,vina}`` — Phase 12 bundle drop.
3. ``shutil.which("smina" | "vina")`` — system PATH.

DiffDock and Boltz-2 adapters exist (``pinsilico.docking.diffdock``,
``pinsilico.docking.boltz``) but their model-weights workflows are
out of scope for v1.3 — the engine enum only exposes Smina/Vina here.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from pinsilico.docking.base import DockingBox, DockingError
from pinsilico.docking.smina_vina import SminaVinaAdapter

router = APIRouter(prefix="/docking", tags=["docking"])

EngineName = Literal["smina", "vina"]


class DockingRunRequest(BaseModel):
    engine: EngineName = "smina"
    receptor_pdb: str = Field(min_length=1, description="Raw PDB text of the receptor.")
    ligand_smiles: str = Field(min_length=1, description="Ligand SMILES.")
    center_xyz: tuple[float, float, float]
    size_xyz: tuple[float, float, float] = (20.0, 20.0, 20.0)
    exhaustiveness: int = Field(default=8, ge=1, le=64)
    num_modes: int = Field(default=9, ge=1, le=32)
    seed: int | None = None


class DockingPosePayload(BaseModel):
    rank: int
    affinity_kcal_mol: float
    rmsd_lb: float
    rmsd_ub: float


class DockingRunResponse(BaseModel):
    engine: EngineName
    poses: list[DockingPosePayload]


def _resolve_engine_binary(engine: EngineName) -> str:
    env_var = f"{engine.upper()}_BIN"
    env_path = os.environ.get(env_var)
    if env_path and Path(env_path).exists():
        return env_path
    bundled = Path(__file__).resolve().parents[2] / "resources" / "binaries" / engine
    if bundled.exists():
        return str(bundled)
    on_path = shutil.which(engine)
    if on_path is not None:
        return on_path
    msg = (
        f"{engine} binary not found. Install it and either put it on PATH, "
        f"set {env_var}, or drop a copy under sidecar/resources/binaries/{engine}."
    )
    raise DockingError(msg, engine=engine)


@router.post(
    "/run",
    response_model=DockingRunResponse,
    summary="Run a Smina / Vina docking against a receptor + ligand pair",
)
def docking_run(req: Annotated[DockingRunRequest, Body()]) -> DockingRunResponse:
    try:
        binary = _resolve_engine_binary(req.engine)
    except DockingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    with tempfile.TemporaryDirectory(prefix="pinsilico-docking-") as work_str:
        adapter = SminaVinaAdapter(
            engine_name=req.engine,
            binary_path=binary,
            workdir=Path(work_str),
        )
        box = DockingBox(
            center_xyz=np.asarray(req.center_xyz, dtype=np.float64),
            size_xyz=np.asarray(req.size_xyz, dtype=np.float64),
        )
        try:
            result = adapter.dock(
                receptor_pdb=req.receptor_pdb,
                ligand_smiles=req.ligand_smiles,
                box=box,
                exhaustiveness=req.exhaustiveness,
                num_modes=req.num_modes,
                seed=req.seed,
            )
        except DockingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    return DockingRunResponse(
        engine=req.engine,
        poses=[
            DockingPosePayload(
                rank=p.rank,
                affinity_kcal_mol=p.affinity_kcal_mol,
                rmsd_lb=p.rmsd_lb,
                rmsd_ub=p.rmsd_ub,
            )
            for p in result.poses
        ],
    )


__all__: list[str] = ["router"]
