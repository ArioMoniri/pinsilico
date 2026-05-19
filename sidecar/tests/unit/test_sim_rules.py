"""Property tests for the simulation rules layer.

BUILD_PROMPT.md §4 calls out these invariants explicitly:

* Residence time is monotonic in -ΔG (more-negative ΔG → longer τ).
* Boltzmann ratio τ(A)/τ(B) ≈ exp(-(ΔG_A - ΔG_B)/RT) within 1 %.
* Concentration converts correctly between µM and particle count.

Pure functions, no external state. Coverage gate for this module is
≥ 95 % per BUILD_PROMPT.md §5 item 2.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pinsilico.sim.rules import (
    GAS_CONSTANT_KCAL_PER_MOL_K,
    boltzmann_factor,
    residence_time,
)


class TestResidenceTime:
    def test_zero_dg_gives_tau_naught(self) -> None:
        """ΔG = 0 → τ = τ₀ (no binding bonus)."""
        assert residence_time(dg_kcal_mol=0.0, temperature_k=298.0, tau0_frames=10.0) == (
            pytest.approx(10.0)
        )

    def test_more_negative_dg_means_longer_tau(self) -> None:
        t_weak = residence_time(dg_kcal_mol=-4.0, temperature_k=298.0, tau0_frames=10.0)
        t_strong = residence_time(dg_kcal_mol=-9.0, temperature_k=298.0, tau0_frames=10.0)
        assert t_strong > t_weak

    def test_positive_dg_shorter_than_baseline(self) -> None:
        # Positive ΔG is unfavourable: τ < τ₀.
        t = residence_time(dg_kcal_mol=+2.0, temperature_k=298.0, tau0_frames=10.0)
        assert t < 10.0

    def test_zero_temperature_rejected(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            residence_time(dg_kcal_mol=-9.0, temperature_k=0.0, tau0_frames=10.0)

    def test_negative_temperature_rejected(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            residence_time(dg_kcal_mol=-9.0, temperature_k=-1.0, tau0_frames=10.0)

    def test_negative_tau0_rejected(self) -> None:
        with pytest.raises(ValueError, match="tau0"):
            residence_time(dg_kcal_mol=-9.0, temperature_k=298.0, tau0_frames=-1.0)

    @given(
        dg=st.floats(min_value=-15.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        temp=st.floats(min_value=200.0, max_value=400.0, allow_nan=False),
        tau0=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, deadline=500)
    def test_monotonic_in_negative_dg(self, dg: float, temp: float, tau0: float) -> None:
        """For any (T, τ₀), τ is monotonically non-decreasing as ΔG drops."""
        t_at_dg = residence_time(dg_kcal_mol=dg, temperature_k=temp, tau0_frames=tau0)
        t_more_negative = residence_time(
            dg_kcal_mol=dg - 1.0,
            temperature_k=temp,
            tau0_frames=tau0,
        )
        assert t_more_negative >= t_at_dg


class TestBoltzmannFactor:
    def test_zero_dg_is_one(self) -> None:
        assert boltzmann_factor(dg_kcal_mol=0.0, temperature_k=298.0) == pytest.approx(1.0)

    def test_known_ratio_at_298k(self) -> None:
        # ΔG = -RT * ln(10) ≈ -1.364 kcal/mol at 298 K → factor 10
        rt298 = GAS_CONSTANT_KCAL_PER_MOL_K * 298.0
        dg = -rt298 * math.log(10)
        assert boltzmann_factor(dg_kcal_mol=dg, temperature_k=298.0) == pytest.approx(
            10.0, rel=1e-9
        )

    @given(
        dg_a=st.floats(min_value=-12.0, max_value=0.0, allow_nan=False, allow_infinity=False),
        dg_b=st.floats(min_value=-12.0, max_value=0.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, deadline=500)
    def test_ratio_within_one_percent_of_exp_formula(self, dg_a: float, dg_b: float) -> None:
        """τ_A / τ_B ≈ exp(-(ΔG_A - ΔG_B) / RT) within 1 %.

        BUILD_PROMPT.md §6 names this exact bound. We assert it on the
        Boltzmann factor (which residence_time multiplies by τ₀) so the
        property holds regardless of τ₀.
        """
        temp = 298.0
        rt = GAS_CONSTANT_KCAL_PER_MOL_K * temp
        expected = math.exp(-(dg_a - dg_b) / rt)
        observed = boltzmann_factor(dg_kcal_mol=dg_a, temperature_k=temp) / boltzmann_factor(
            dg_kcal_mol=dg_b, temperature_k=temp
        )
        # 1 % tolerance — math.exp is exact, so the only drift would be
        # floating-point noise. Generous bound for portability.
        assert observed == pytest.approx(expected, rel=0.01)
