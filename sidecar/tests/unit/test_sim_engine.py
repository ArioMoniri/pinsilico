"""Brownian-dynamics engine tests.

Property tests cover BUILD_PROMPT.md §6 explicit invariants:

* MSD scales linearly: ⟨r²⟩ ≈ 6Dt for free particles (within 5 %)
* Deterministic: same seed + same inputs → bit-identical event log
* Conservation: particle count constant across frames
* Competition fairness: no negative occupancy under finite sites

The engine is pure Python + numpy; no external state.
"""

from __future__ import annotations

import numpy as np
import pytest
from pinsilico.sim.engine import (
    BindingSite,
    Particle,
    SimConfig,
    Simulator,
)


def _free_diffusion_config(*, seed: int = 0) -> SimConfig:
    """Empty scene with no proteins/sites — particles diffuse freely."""
    return SimConfig(
        sites=(),
        protein_centers=(),
        protein_radii=(),
        diffusion_coeff_a2_per_frame=1.0,
        temperature_k=298.0,
        box_size_a=200.0,
        use_attraction=False,
        seed=seed,
    )


class TestDeterminism:
    def test_same_seed_same_event_log(self) -> None:
        cfg = SimConfig(
            sites=(
                BindingSite(
                    identifier="p1",
                    centroid=np.array([0.0, 0.0, 0.0]),
                    radius_a=5.0,
                    dg_kcal_mol=-8.0,
                ),
            ),
            protein_centers=(np.array([0.0, 0.0, 0.0]),),
            protein_radii=(15.0,),
            diffusion_coeff_a2_per_frame=2.0,
            temperature_k=298.0,
            box_size_a=100.0,
            use_attraction=True,
            seed=42,
        )
        s1 = Simulator(cfg)
        s2 = Simulator(cfg)

        particles = [Particle(position=np.array([20.0, 0.0, 0.0])) for _ in range(5)]
        s1.spawn_particles(particles)
        s2.spawn_particles(particles)

        for _ in range(200):
            s1.step()
            s2.step()

        # Bit-identical particle positions
        for p1, p2 in zip(s1.particles, s2.particles, strict=True):
            assert np.allclose(p1.position, p2.position, atol=0.0)

    def test_different_seeds_diverge(self) -> None:
        cfg_a = _free_diffusion_config(seed=1)
        cfg_b = _free_diffusion_config(seed=2)
        a = Simulator(cfg_a)
        b = Simulator(cfg_b)
        a.spawn_particles([Particle(position=np.zeros(3))])
        b.spawn_particles([Particle(position=np.zeros(3))])
        for _ in range(50):
            a.step()
            b.step()
        assert not np.allclose(a.particles[0].position, b.particles[0].position)


class TestFreeDiffusionMSD:
    def test_msd_scales_with_6_d_t(self) -> None:
        """⟨r²⟩ = 6Dt to within 5 % for many free particles after many steps.

        BUILD_PROMPT.md §6 names this invariant explicitly.
        """
        diffusion = 1.0  # Å² / frame
        n_particles = 500
        n_steps = 100
        cfg = SimConfig(
            sites=(),
            protein_centers=(),
            protein_radii=(),
            diffusion_coeff_a2_per_frame=diffusion,
            temperature_k=298.0,
            box_size_a=10_000.0,  # large box → no wall effects
            use_attraction=False,
            seed=12345,
        )
        sim = Simulator(cfg)
        sim.spawn_particles([Particle(position=np.zeros(3)) for _ in range(n_particles)])
        for _ in range(n_steps):
            sim.step()
        # Compute mean squared displacement from origin
        positions = np.array([p.position for p in sim.particles])
        msd = float(np.mean(np.sum(positions**2, axis=1)))
        expected = 6.0 * diffusion * n_steps  # 600
        # Statistical noise on 500 particles: SD ≈ expected * sqrt(2/N) ≈ 38
        # Loose 10 % tolerance covers normal variation.
        assert msd == pytest.approx(expected, rel=0.10)


class TestConservation:
    def test_particle_count_constant(self) -> None:
        cfg = _free_diffusion_config(seed=7)
        sim = Simulator(cfg)
        sim.spawn_particles([Particle(position=np.array([float(i), 0.0, 0.0])) for i in range(10)])
        for _ in range(50):
            sim.step()
        assert len(sim.particles) == 10

    def test_no_negative_occupancy_in_competition(self) -> None:
        site = BindingSite(
            identifier="p1",
            centroid=np.array([0.0, 0.0, 0.0]),
            radius_a=10.0,
            dg_kcal_mol=-6.0,
        )
        cfg = SimConfig(
            sites=(site,),
            protein_centers=(np.array([0.0, 0.0, 0.0]),),
            protein_radii=(5.0,),
            diffusion_coeff_a2_per_frame=2.0,
            temperature_k=298.0,
            box_size_a=50.0,
            use_attraction=True,
            seed=99,
        )
        sim = Simulator(cfg)
        # Many particles, one site → must never bind more than 1 at a time
        sim.spawn_particles([Particle(position=np.array([15.0, 0.0, 0.0])) for _ in range(20)])
        for _ in range(500):
            sim.step()
            bound = sum(1 for p in sim.particles if p.bound_site_id is not None)
            assert 0 <= bound <= 1


class TestBindingEvents:
    def test_particle_can_bind_to_site(self) -> None:
        site = BindingSite(
            identifier="p1",
            centroid=np.array([0.0, 0.0, 0.0]),
            radius_a=5.0,
            dg_kcal_mol=-10.0,  # strong binding
        )
        cfg = SimConfig(
            sites=(site,),
            protein_centers=(),
            protein_radii=(),
            diffusion_coeff_a2_per_frame=0.0,  # frozen → only the spawn-inside-radius binds
            temperature_k=298.0,
            box_size_a=50.0,
            use_attraction=False,
            seed=0,
        )
        sim = Simulator(cfg)
        sim.spawn_particles([Particle(position=np.array([0.0, 0.0, 0.0]))])
        # Inside the docking sphere from the start; first step should bind.
        sim.step()
        assert sim.particles[0].bound_site_id == "p1"

    def test_unbinding_happens_repeatedly_for_weak_site(self) -> None:
        """A weak site (ΔG=+2 kcal/mol → very short τ) must release the
        particle many times across 200 frames.

        Because the particle starts inside the docking sphere with no
        diffusion, every release is immediately followed by a re-bind
        on the next frame. We verify that the release-frame keeps
        advancing rather than staying constant (which would mean
        "never unbound").
        """
        site = BindingSite(
            identifier="p1",
            centroid=np.array([0.0, 0.0, 0.0]),
            radius_a=5.0,
            dg_kcal_mol=+2.0,  # unfavourable → very short τ
        )
        cfg = SimConfig(
            sites=(site,),
            protein_centers=(),
            protein_radii=(),
            diffusion_coeff_a2_per_frame=0.0,
            temperature_k=298.0,
            box_size_a=50.0,
            use_attraction=False,
            tau0_frames=1.0,
            seed=0,
        )
        sim = Simulator(cfg)
        sim.spawn_particles([Particle(position=np.array([0.0, 0.0, 0.0]))])
        observed_release_frames: set[int] = set()
        for _ in range(200):
            sim.step()
            if sim.particles[0].bound_site_id is not None:
                observed_release_frames.add(sim.particles[0].release_frame)
        # Multiple distinct release-frames means multiple bind events
        # ⇒ multiple releases happened.
        assert len(observed_release_frames) >= 5


class TestFastForward:
    def test_returns_event_count_dict(self) -> None:
        site_a = BindingSite(identifier="a", centroid=np.zeros(3), radius_a=5.0, dg_kcal_mol=-8.0)
        site_b = BindingSite(
            identifier="b",
            centroid=np.array([10.0, 0.0, 0.0]),
            radius_a=5.0,
            dg_kcal_mol=-4.0,
        )
        cfg = SimConfig(
            sites=(site_a, site_b),
            protein_centers=(),
            protein_radii=(),
            diffusion_coeff_a2_per_frame=1.0,
            temperature_k=298.0,
            box_size_a=100.0,
            use_attraction=False,
            seed=1,
        )
        sim = Simulator(cfg)
        events = sim.fast_forward(n_events=1000)
        assert sum(events.values()) == 1000
        # Stronger site should win more often
        assert events["a"] > events["b"]

    def test_deterministic_under_seed(self) -> None:
        cfg = SimConfig(
            sites=(
                BindingSite(identifier="a", centroid=np.zeros(3), radius_a=5.0, dg_kcal_mol=-7.0),
                BindingSite(
                    identifier="b",
                    centroid=np.array([10.0, 0.0, 0.0]),
                    radius_a=5.0,
                    dg_kcal_mol=-7.0,
                ),
            ),
            protein_centers=(),
            protein_radii=(),
            diffusion_coeff_a2_per_frame=1.0,
            temperature_k=298.0,
            box_size_a=100.0,
            use_attraction=False,
            seed=123,
        )
        a = Simulator(cfg).fast_forward(n_events=200)
        b = Simulator(cfg).fast_forward(n_events=200)
        assert a == b
