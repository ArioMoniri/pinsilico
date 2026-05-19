"""Pure rules functions for the kinetic simulation.

These are the *only* functions the BUILD_PROMPT.md §5 95 %-coverage
gate covers — they encode the simulation's contract with reality:

* Residence times are Boltzmann-scaled from docking ΔG.
* The Boltzmann ratio is correct within 1 % (BUILD_PROMPT.md §6).
* Monotonicity in -ΔG.

No state, no randomness, no I/O — just arithmetic. The Phase 4 engine
(:mod:`pinsilico.sim.engine`) composes these into the per-frame
integrator.
"""

from __future__ import annotations

import math

#: Gas constant in kcal·mol⁻¹·K⁻¹. ΔG everywhere in PInSilico is kcal/mol
#: (docking-engine convention), so the matching R value lives here.
GAS_CONSTANT_KCAL_PER_MOL_K: float = 0.0019872041


def boltzmann_factor(*, dg_kcal_mol: float, temperature_k: float) -> float:
    """Return ``exp(-ΔG / RT)``.

    Args:
        dg_kcal_mol: Free-energy difference in kcal/mol. More negative =
            more favourable.
        temperature_k: Absolute temperature in K. Must be positive.

    Returns:
        The dimensionless Boltzmann factor. ΔG = 0 → 1.0.

    Raises:
        ValueError: when ``temperature_k`` is not positive.
    """
    if temperature_k <= 0.0:
        msg = f"temperature must be positive, got {temperature_k}"
        raise ValueError(msg)
    return math.exp(-dg_kcal_mol / (GAS_CONSTANT_KCAL_PER_MOL_K * temperature_k))


def residence_time(
    *,
    dg_kcal_mol: float,
    temperature_k: float,
    tau0_frames: float,
) -> float:
    """Return ``τ₀ · exp(-ΔG / RT)`` in simulation frames.

    Args:
        dg_kcal_mol: Docking ΔG in kcal/mol.
        temperature_k: Absolute temperature in K. Must be positive.
        tau0_frames: Baseline residence time at ΔG = 0, in frames.
            Must be non-negative.

    Raises:
        ValueError: on non-positive temperature or negative ``tau0``.
    """
    if tau0_frames < 0.0:
        msg = f"tau0_frames must be non-negative, got {tau0_frames}"
        raise ValueError(msg)
    return tau0_frames * boltzmann_factor(dg_kcal_mol=dg_kcal_mol, temperature_k=temperature_k)
