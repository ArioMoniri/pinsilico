"""Tests for the concentration helpers.

µM → particle-count and back, plus the scaling constant the UI surfaces.
Pure functions, ≥ 95% coverage gate per BUILD_PROMPT.md §5.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pinsilico.sim.concentration import (
    AVOGADRO,
    particle_count_for,
    uM_for_count,
)


class TestParticleCountFor:
    def test_zero_concentration_yields_zero(self) -> None:
        assert particle_count_for(concentration_uM=0.0, volume_litres=1e-15) == 0

    def test_one_micromolar_in_one_femtolitre(self) -> None:
        # 1 µM = 1e-6 mol/L; in 1 fL (1e-15 L) → 6.022e2 molecules ≈ 602
        n = particle_count_for(concentration_uM=1.0, volume_litres=1e-15)
        assert n == pytest.approx(round(AVOGADRO * 1e-6 * 1e-15), abs=1)

    def test_negative_concentration_rejected(self) -> None:
        with pytest.raises(ValueError, match="concentration"):
            particle_count_for(concentration_uM=-1.0, volume_litres=1e-15)

    def test_zero_volume_rejected(self) -> None:
        with pytest.raises(ValueError, match="volume"):
            particle_count_for(concentration_uM=1.0, volume_litres=0.0)

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValueError, match="volume"):
            particle_count_for(concentration_uM=1.0, volume_litres=-1e-15)


class TestUMForCount:
    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="particle_count"):
            uM_for_count(particle_count=-1, volume_litres=1e-15)

    def test_zero_volume_rejected(self) -> None:
        with pytest.raises(ValueError, match="volume"):
            uM_for_count(particle_count=10, volume_litres=0.0)

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValueError, match="volume"):
            uM_for_count(particle_count=10, volume_litres=-1e-15)


class TestRoundTrip:
    @given(
        c=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
        v=st.floats(min_value=1e-18, max_value=1e-12, allow_nan=False, allow_infinity=False),
    )
    def test_concentration_round_trips_within_one_particle(self, c: float, v: float) -> None:
        n = particle_count_for(concentration_uM=c, volume_litres=v)
        back = uM_for_count(particle_count=n, volume_litres=v)
        # Within ±1 particle's worth of concentration
        single_particle_uM = 1.0 / (AVOGADRO * v * 1e-6)
        assert math.isclose(back, c, abs_tol=single_particle_uM)
