"""``/sim/*`` routes.

Phase 5 exposes two endpoints over the Phase 4 simulator:

* ``POST /sim/fast_forward`` — sample ``n_events`` binding events from
  the cached-ΔG categorical distribution. Returns the per-site count
  dict in one shot.
* ``POST /sim/run`` — synchronously runs ``n_frames`` of integration
  and returns the final particle positions. (The streaming SSE path
  for live animation lands with Phase 6 sidecar wiring; Phase 5 ships
  the request/response surface so the Phase 7 frontend stores can be
  written against a stable contract.)
"""

from __future__ import annotations

from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from pinsilico.sim.engine import BindingSite, Particle, SimConfig, Simulator

router = APIRouter(prefix="/sim", tags=["sim"])


class SiteSpec(BaseModel):
    identifier: str
    centroid_xyz: tuple[float, float, float]
    radius_a: float = Field(gt=0.0)
    dg_kcal_mol: float


class ParticleSpec(BaseModel):
    position: tuple[float, float, float]


class SimRunRequest(BaseModel):
    sites: list[SiteSpec]
    particles: list[ParticleSpec] = Field(default_factory=list)
    protein_centers: list[tuple[float, float, float]] = Field(default_factory=list)
    protein_radii: list[float] = Field(default_factory=list)
    diffusion_coeff_a2_per_frame: float = Field(default=1.0, gt=0.0)
    temperature_k: float = Field(default=298.0, gt=0.0)
    box_size_a: float = Field(default=200.0, gt=0.0)
    use_attraction: bool = True
    tau0_frames: float = Field(default=10.0, ge=0.0)
    seed: int = 0
    n_frames: int = Field(default=200, ge=1, le=100_000)
    mode: Literal["inhibitor_only", "ligand_only", "competition"] = "competition"


class SimRunResponse(BaseModel):
    final_positions: list[tuple[float, float, float]]
    bound_site_ids: list[str | None]
    frames_executed: int


class FastForwardRequest(BaseModel):
    sites: list[SiteSpec]
    temperature_k: float = Field(default=298.0, gt=0.0)
    seed: int = 0
    n_events: int = Field(ge=1, le=1_000_000)


class FastForwardResponse(BaseModel):
    counts: dict[str, int]
    n_events: int


def _build_simulator(
    sites: list[SiteSpec],
    *,
    protein_centers: list[tuple[float, float, float]] | None = None,
    protein_radii: list[float] | None = None,
    diffusion_coeff_a2_per_frame: float = 1.0,
    temperature_k: float = 298.0,
    box_size_a: float = 200.0,
    use_attraction: bool = True,
    tau0_frames: float = 10.0,
    seed: int = 0,
) -> Simulator:
    cfg = SimConfig(
        sites=tuple(
            BindingSite(
                identifier=s.identifier,
                centroid=np.array(s.centroid_xyz, dtype=np.float64),
                radius_a=s.radius_a,
                dg_kcal_mol=s.dg_kcal_mol,
            )
            for s in sites
        ),
        protein_centers=tuple(np.array(c, dtype=np.float64) for c in (protein_centers or [])),
        protein_radii=tuple(protein_radii or []),
        diffusion_coeff_a2_per_frame=diffusion_coeff_a2_per_frame,
        temperature_k=temperature_k,
        box_size_a=box_size_a,
        use_attraction=use_attraction,
        tau0_frames=tau0_frames,
        seed=seed,
    )
    return Simulator(cfg)


@router.post(
    "/run",
    response_model=SimRunResponse,
    summary="Synchronous simulation run",
    description=(
        "Executes `n_frames` of integration and returns the final state. "
        "Streaming SSE for live animation lands with Phase 6 wiring."
    ),
)
def sim_run(req: Annotated[SimRunRequest, Body()]) -> SimRunResponse:
    sim = _build_simulator(
        req.sites,
        protein_centers=req.protein_centers,
        protein_radii=req.protein_radii,
        diffusion_coeff_a2_per_frame=req.diffusion_coeff_a2_per_frame,
        temperature_k=req.temperature_k,
        box_size_a=req.box_size_a,
        use_attraction=req.use_attraction,
        tau0_frames=req.tau0_frames,
        seed=req.seed,
    )
    sim.spawn_particles(
        [Particle(position=np.array(p.position, dtype=np.float64)) for p in req.particles],
    )
    for _ in range(req.n_frames):
        sim.step()
    return SimRunResponse(
        final_positions=[
            (float(p.position[0]), float(p.position[1]), float(p.position[2]))
            for p in sim.particles
        ],
        bound_site_ids=[p.bound_site_id for p in sim.particles],
        frames_executed=req.n_frames,
    )


@router.post(
    "/fast_forward",
    response_model=FastForwardResponse,
    summary="Categorical event sampling (skip integration)",
    description=(
        "Samples `n_events` binding events directly from the cached-ΔG "
        "distribution. The SimPanel fast-forward button calls this for "
        "long-tail statistics that would otherwise take wall-clock minutes."
    ),
)
def sim_fast_forward(req: Annotated[FastForwardRequest, Body()]) -> FastForwardResponse:
    sim = _build_simulator(req.sites, temperature_k=req.temperature_k, seed=req.seed)
    counts = sim.fast_forward(req.n_events)
    return FastForwardResponse(counts=counts, n_events=req.n_events)


__all__: list[str] = ["router"]
