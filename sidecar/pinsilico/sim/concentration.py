"""Concentration ↔ particle-count helpers.

BUILD_PROMPT.md §4 calls for ``particles_for(concentration_uM, volume_L)``
that converts µM to particle count under a configurable scaling
constant. We expose both directions so the UI can show "this concentration
≈ N particles in the chosen scene volume" and round-trip cleanly.

Pure functions; ≥ 95 % coverage gate.
"""

from __future__ import annotations

#: Avogadro's number (mol⁻¹).
AVOGADRO: float = 6.02214076e23


def _validate(*, concentration_uM: float, volume_litres: float) -> None:
    if concentration_uM < 0.0:
        msg = f"concentration must be non-negative, got {concentration_uM}"
        raise ValueError(msg)
    if volume_litres <= 0.0:
        msg = f"volume must be positive, got {volume_litres}"
        raise ValueError(msg)


def particle_count_for(*, concentration_uM: float, volume_litres: float) -> int:
    """Round ``concentration_uM · 10⁻⁶ · N_A · V`` to the nearest int."""
    _validate(concentration_uM=concentration_uM, volume_litres=volume_litres)
    n_float = concentration_uM * 1e-6 * AVOGADRO * volume_litres
    return round(n_float)


def uM_for_count(*, particle_count: int, volume_litres: float) -> float:
    """Inverse of :func:`particle_count_for`."""
    if particle_count < 0:
        msg = f"particle_count must be non-negative, got {particle_count}"
        raise ValueError(msg)
    if volume_litres <= 0.0:
        msg = f"volume must be positive, got {volume_litres}"
        raise ValueError(msg)
    return particle_count / (AVOGADRO * volume_litres) / 1e-6
