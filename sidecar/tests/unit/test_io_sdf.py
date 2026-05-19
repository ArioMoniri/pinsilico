"""SDF/SMILES parser round-trip tests.

Phase 1 wraps RDKit's SDMolSupplier and SDWriter behind
:mod:`pinsilico.io.sdf` so downstream Phase 3 docking adapters can talk
to a typed dataclass-friendly interface rather than RDKit's mutable Mol.

Locked invariants:

* SMILES → Mol → canonical SMILES is idempotent (canonicalisation
  fixed-point at iteration 2).
* Round-trip SDF parse → write → parse preserves atom count, bond
  count, and canonical SMILES.
* Heavy-atom count is exposed for the docking layer.
* Parser raises a typed :class:`pinsilico.io.sdf.SdfParseError` on bad
  input, not an opaque RDKit exception.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pinsilico.io.sdf import (
    SdfParseError,
    canonical_smiles,
    count_heavy_atoms,
    mol_from_smiles,
    read_sdf,
    write_sdf,
)

if TYPE_CHECKING:
    from pathlib import Path


# Small molecules with stable canonical SMILES across RDKit versions.
_SAMPLE_SMILES = [
    ("water", "O"),
    ("methane", "C"),
    ("ethanol", "CCO"),
    ("benzene", "c1ccccc1"),
    ("aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
]


class TestMolFromSmiles:
    @pytest.mark.parametrize(("name", "smiles"), _SAMPLE_SMILES)
    def test_parses_known_smiles(self, name: str, smiles: str) -> None:
        mol = mol_from_smiles(smiles)
        assert mol is not None, f"failed to parse {name}: {smiles}"

    def test_raises_on_empty(self) -> None:
        with pytest.raises(SdfParseError):
            mol_from_smiles("")

    def test_raises_on_invalid(self) -> None:
        with pytest.raises(SdfParseError):
            mol_from_smiles("not-a-real-smiles-XYZQ12345")


class TestCanonicalSmiles:
    @pytest.mark.parametrize(("name", "smiles"), _SAMPLE_SMILES)
    def test_round_trips(self, name: str, smiles: str) -> None:
        canon = canonical_smiles(smiles)
        # Apply twice; the canonicaliser must be a fixed-point.
        assert canonical_smiles(canon) == canon

    def test_different_inputs_same_canon(self) -> None:
        # Both ethanol forms canonicalise to the same string.
        assert canonical_smiles("CCO") == canonical_smiles("OCC")


class TestCountHeavyAtoms:
    @pytest.mark.parametrize(
        ("smiles", "expected"),
        [
            ("O", 1),
            ("C", 1),
            ("CCO", 3),
            ("c1ccccc1", 6),
            ("CC(=O)Oc1ccccc1C(=O)O", 13),  # aspirin
        ],
    )
    def test_known_counts(self, smiles: str, expected: int) -> None:
        assert count_heavy_atoms(mol_from_smiles(smiles)) == expected


class TestSdfRoundTrip:
    @pytest.mark.parametrize(("name", "smiles"), _SAMPLE_SMILES)
    def test_round_trips_via_sdf_file(self, name: str, smiles: str, tmp_path: Path) -> None:
        out = tmp_path / f"{name}.sdf"
        mol = mol_from_smiles(smiles)
        write_sdf([mol], out)

        mols = read_sdf(out)
        assert len(mols) == 1
        # Heavy-atom and canonical-SMILES preserved
        assert count_heavy_atoms(mols[0]) == count_heavy_atoms(mol)
        assert canonical_smiles(mols[0]) == canonical_smiles(mol)

    def test_multimol_sdf_round_trip(self, tmp_path: Path) -> None:
        mols = [mol_from_smiles(s) for _, s in _SAMPLE_SMILES]
        out = tmp_path / "multi.sdf"
        write_sdf(mols, out)
        read_back = read_sdf(out)
        assert len(read_back) == len(mols)
        for a, b in zip(mols, read_back, strict=True):
            assert canonical_smiles(a) == canonical_smiles(b)


class TestSdfErrors:
    def test_read_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, SdfParseError)):
            read_sdf(tmp_path / "does_not_exist.sdf")

    def test_read_garbage_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "junk.sdf"
        p.write_text("this is not a valid SDF block at all\n")
        # RDKit returns an empty supplier; we surface that as a parse error.
        with pytest.raises(SdfParseError):
            read_sdf(p)


# Property test: a small SMILES alphabet round-trips through canonical → mol →
# canonical without drift.
@settings(
    max_examples=15,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(smiles=st.sampled_from([s for _, s in _SAMPLE_SMILES]))
def test_smiles_canonical_idempotent(smiles: str) -> None:
    once = canonical_smiles(smiles)
    twice = canonical_smiles(once)
    assert once == twice
