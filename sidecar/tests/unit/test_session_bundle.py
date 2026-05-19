"""Tests for the .pinsilico session bundle.

Phase 10 ships a zip-based session format with round-trip property
tests per BUILD_PROMPT.md §10. Determinism: same input → same bytes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pinsilico.session.bundle import (
    SessionBundle,
    SessionLigand,
    SessionPocket,
    SessionProtein,
    load_bundle,
    save_bundle,
)

if TYPE_CHECKING:
    from pathlib import Path


def _sample_bundle() -> SessionBundle:
    return SessionBundle(
        version="0.0.1",
        seed=42,
        proteins=[
            SessionProtein(
                identifier="1HSG",
                source="rcsb",
                role="target",
                pdb_text="HEADER\nATOM      1  CA  ALA A   1\nEND\n",
                pockets=[
                    SessionPocket(
                        identifier="pocket-1",
                        centroid_xyz=(24.5, 18.7, 12.3),
                        volume_a3=893.2,
                        hydrophobicity=54.0,
                        druggability_score=0.95,
                        residue_ids=("A:25:ASP", "A:28:ILE"),
                    ),
                ],
            ),
        ],
        ligands=[
            SessionLigand(
                identifier="indinavir",
                source="chembl",
                smiles="CC(C)(C)N",
                is_inhibitor=True,
                is_natural_ligand=False,
            ),
        ],
    )


class TestRoundTrip:
    def test_basic_round_trip(self, tmp_path: Path) -> None:
        original = _sample_bundle()
        path = tmp_path / "session.pinsilico"
        save_bundle(original, path)
        assert path.exists()
        loaded = load_bundle(path)
        assert loaded == original

    def test_deterministic_bytes(self, tmp_path: Path) -> None:
        a = tmp_path / "a.pinsilico"
        b = tmp_path / "b.pinsilico"
        save_bundle(_sample_bundle(), a)
        save_bundle(_sample_bundle(), b)
        # Bundle structure is deterministic; the zip's mtime field is
        # zeroed by save_bundle so two saves yield identical bytes.
        assert a.read_bytes() == b.read_bytes()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_bundle(tmp_path / "no-such-file.pinsilico")

    def test_corrupt_bundle_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.pinsilico"
        path.write_bytes(b"not a zip file")
        with pytest.raises(ValueError, match="bundle"):
            load_bundle(path)

    def test_empty_bundle_round_trip(self, tmp_path: Path) -> None:
        empty = SessionBundle(version="0.0.1", seed=0, proteins=[], ligands=[])
        path = tmp_path / "empty.pinsilico"
        save_bundle(empty, path)
        assert load_bundle(path) == empty


@settings(
    max_examples=10,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    is_inhibitor=st.booleans(),
)
def test_round_trip_property(seed: int, is_inhibitor: bool, tmp_path: Path) -> None:
    """Property test: arbitrary seed + flag survives the round trip."""
    bundle = SessionBundle(
        version="0.0.1",
        seed=seed,
        proteins=[],
        ligands=[
            SessionLigand(
                identifier="lig",
                source="upload",
                smiles="CCO",
                is_inhibitor=is_inhibitor,
                is_natural_ligand=False,
            ),
        ],
    )
    path = tmp_path / "p.pinsilico"
    save_bundle(bundle, path)
    loaded = load_bundle(path)
    assert loaded.seed == seed
    assert loaded.ligands[0].is_inhibitor == is_inhibitor
