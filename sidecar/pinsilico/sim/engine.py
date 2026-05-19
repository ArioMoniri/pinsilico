"""Brownian-dynamics simulation engine.

Phase 4 deliverable per BUILD_PROMPT.md §1 P4 and §6 invariants:

* Overdamped Langevin / Brownian step:
  ``x(t+Δt) = x(t) + √(2·D·Δt)·ξ``
  (force-free for the unit-time formulation; the optional attractive
  potential and protein hard repulsion are added as deterministic
  shifts on top of the random step).
* Boltzmann-scaled residence times via :func:`pinsilico.sim.rules.residence_time`.
* Deterministic under a seed (BUILD_PROMPT.md §8.8).
* Competition / inhibitor-only / ligand-only modes via the same
  Simulator (mode is just "which subset of sites can bind which
  particles", and Phase 5 routes flip the toggle).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import numpy as np
from numpy.typing import NDArray

from pinsilico.sim.rules import boltzmann_factor, residence_time

# Default τ₀ for the per-particle binding timer, in frames. Tuned so a
# ΔG = -8 kcal/mol pocket holds the particle for ~10² frames at 298 K
# (typical visualisation window). Phase 9 SimPanel exposes this.
DEFAULT_TAU0_FRAMES: Final[float] = 10.0


@dataclass(frozen=True, slots=True)
class BindingSite:
    """A binding pocket the engine treats as a kinetic trap."""

    identifier: str
    centroid: NDArray[np.float64]
    radius_a: float  # Å — radius of the docking sphere
    dg_kcal_mol: float  # cached docking ΔG


@dataclass
class Particle:
    """A single diffusing ligand (or inhibitor) particle."""

    position: NDArray[np.float64]
    bound_site_id: str | None = None
    release_frame: int = 0  # frame number at which to release a bound particle


@dataclass(frozen=True, slots=True)
class SimConfig:
    """Immutable simulator configuration.

    Attributes:
        sites: Binding sites (pockets) the engine considers.
        protein_centers: Centres of protein bodies for excluded-volume.
        protein_radii: Radii of those bodies in Å.
        diffusion_coeff_a2_per_frame: D in Å²/frame for the Brownian step.
            ⟨r²⟩ = 6·D·t for a free 3D particle.
        temperature_k: Absolute temperature for the Boltzmann factor.
        box_size_a: Side length of the cubic simulation box (centred on origin).
        use_attraction: If True, particles get a weak deterministic shift
            toward the nearest unoccupied pocket (encounter accelerator).
        tau0_frames: Baseline residence time at ΔG = 0.
        seed: RNG seed; same seed + same inputs ⇒ bit-identical trace.
    """

    sites: tuple[BindingSite, ...]
    protein_centers: tuple[NDArray[np.float64], ...]
    protein_radii: tuple[float, ...]
    diffusion_coeff_a2_per_frame: float
    temperature_k: float
    box_size_a: float
    use_attraction: bool
    tau0_frames: float = DEFAULT_TAU0_FRAMES
    seed: int = 0


@dataclass
class Simulator:
    """Per-launch simulator state."""

    cfg: SimConfig
    particles: list[Particle] = field(default_factory=list)
    frame: int = 0
    _rng: np.random.Generator = field(init=False)
    _site_occupants: dict[str, str | None] = field(init=False)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.cfg.seed)
        self._site_occupants = {s.identifier: None for s in self.cfg.sites}

    # ------------------------------------------------------------------ API
    def spawn_particles(self, particles: list[Particle]) -> None:
        """Add particles to the scene. Positions are deep-copied."""
        for p in particles:
            self.particles.append(Particle(position=np.array(p.position, dtype=np.float64)))

    def step(self) -> None:
        """Advance the simulation by one frame."""
        self.frame += 1
        for idx, particle in enumerate(self.particles):
            if particle.bound_site_id is not None:
                # Bound: tick down toward release_frame
                if self.frame >= particle.release_frame:
                    self._release(particle)
                continue
            self._brownian_step(particle)
            self._apply_protein_exclusion(particle)
            self._maybe_bind(particle, idx)

    def fast_forward(self, n_events: int) -> dict[str, int]:
        """Sample binding events directly from the categorical distribution.

        Skips integration: weight each (site) by ``exp(-ΔG/RT)``,
        normalise, draw ``n_events`` samples, return the counts.

        Useful for the SimPanel's "fast-forward" button — long-tail
        statistical accumulation that would otherwise take minutes of
        wall-clock animation.
        """
        if not self.cfg.sites:
            return {}
        weights = np.array(
            [
                boltzmann_factor(dg_kcal_mol=s.dg_kcal_mol, temperature_k=self.cfg.temperature_k)
                for s in self.cfg.sites
            ],
        )
        probs = weights / weights.sum()
        draws = self._rng.choice(len(self.cfg.sites), size=n_events, p=probs)
        counts: dict[str, int] = {s.identifier: 0 for s in self.cfg.sites}
        for d in draws:
            counts[self.cfg.sites[d].identifier] += 1
        return counts

    # ------------------------------------------------------- per-frame parts
    def _brownian_step(self, particle: Particle) -> None:
        """Apply the overdamped Langevin random step.

        For a 3D free particle with diffusion coefficient D and timestep
        Δt = 1 frame, the displacement is N(0, 2·D·Δt) per axis, giving
        ⟨r²⟩ = 6·D·Δt — locked by the MSD property test.
        """
        sigma = (2.0 * self.cfg.diffusion_coeff_a2_per_frame) ** 0.5
        jitter = self._rng.standard_normal(3) * sigma
        new_pos = particle.position + jitter
        if self.cfg.use_attraction:
            new_pos = new_pos + self._attraction_to_nearest_unoccupied(particle.position)
        # Reflect off cubic box walls so particles can't escape.
        half = self.cfg.box_size_a / 2.0
        new_pos = np.where(np.abs(new_pos) > half, np.sign(new_pos) * half, new_pos)
        particle.position = new_pos

    def _attraction_to_nearest_unoccupied(
        self, position: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Weak deterministic shift toward the nearest unoccupied site.

        Honestly labelled in BUILD_PROMPT.md §8.4 as a kinetic accelerator,
        not real electrostatics.
        """
        best: BindingSite | None = None
        best_dist = float("inf")
        for s in self.cfg.sites:
            if self._site_occupants[s.identifier] is not None:
                continue
            d = float(np.linalg.norm(s.centroid - position))
            if d < best_dist:
                best = s
                best_dist = d
        if best is None or best_dist == 0.0:
            return np.zeros(3, dtype=np.float64)
        direction = (best.centroid - position) / best_dist
        # Scale ~D so attraction is on the same order as diffusion; clip
        # by the distance so we don't overshoot the centre.
        shift_mag = min(0.5 * self.cfg.diffusion_coeff_a2_per_frame, best_dist * 0.1)
        return direction * shift_mag

    def _apply_protein_exclusion(self, particle: Particle) -> None:
        """Project the particle outside every protein-body sphere."""
        for centre, radius in zip(self.cfg.protein_centers, self.cfg.protein_radii, strict=True):
            delta = particle.position - centre
            dist = float(np.linalg.norm(delta))
            if dist < radius and dist > 0.0:
                particle.position = centre + (delta / dist) * radius

    def _maybe_bind(self, particle: Particle, particle_idx: int) -> None:
        """Bind the particle to the first matching unoccupied site."""
        _ = particle_idx  # reserved for Phase 5 per-species accounting
        for site in self.cfg.sites:
            if self._site_occupants[site.identifier] is not None:
                continue
            if float(np.linalg.norm(particle.position - site.centroid)) <= site.radius_a:
                tau = residence_time(
                    dg_kcal_mol=site.dg_kcal_mol,
                    temperature_k=self.cfg.temperature_k,
                    tau0_frames=self.cfg.tau0_frames,
                )
                # Sample an exponential residence on top of the mean τ
                # so different binding events have different durations.
                # Tiny floor on the scale keeps the RNG happy when τ → 0
                # but doesn't artificially extend short residences.
                scale = max(tau, 1e-6)
                sampled = float(self._rng.exponential(scale=scale))
                particle.bound_site_id = site.identifier
                particle.release_frame = self.frame + max(1, round(sampled))
                particle.position = site.centroid.copy()
                self._site_occupants[site.identifier] = "particle"
                break

    def _release(self, particle: Particle) -> None:
        sid = particle.bound_site_id
        if sid is not None:
            self._site_occupants[sid] = None
        particle.bound_site_id = None
        particle.release_frame = 0
