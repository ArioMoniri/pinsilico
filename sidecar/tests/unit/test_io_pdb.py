"""PDB parser round-trip tests.

Phase 1 wraps Biopython's PDB parser/writer behind a thin
:mod:`pinsilico.io.pdb` interface so:

* Test fixtures can build deterministic minimal PDBs without an external
  download.
* Phase 5 routes (POST /io/import) get a typed adapter rather than
  exposing Biopython's globally-mutable Structure object.

Locked invariants:

* Round-trip: parse → write → parse yields the same atom set
  (same element, same xyz to 3 decimal places).
* Heavy-atom count is preserved (hydrogens may or may not be present;
  fpocket only needs heavy atoms anyway).
* Chains and residues survive the round-trip.
* Parser raises a typed :class:`pinsilico.io.pdb.PdbParseError` on
  empty input, not a Biopython internal exception.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pinsilico.io.pdb import PdbParseError, count_heavy_atoms, parse_pdb, write_pdb

if TYPE_CHECKING:
    from pathlib import Path


_TINY_PDB = """\
HEADER    TEST                                    01-JAN-26   XXXX
ATOM      1  N   ALA A   1      11.104  13.207  10.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      11.804  14.207  10.500  1.00  0.00           C
ATOM      3  C   ALA A   1      13.104  14.207  10.000  1.00  0.00           C
ATOM      4  O   ALA A   1      13.804  15.207  10.500  1.00  0.00           O
ATOM      5  CB  ALA A   1      11.104  15.207  11.500  1.00  0.00           C
TER       6      ALA A   1
END
"""


class TestParsePdb:
    def test_parses_a_minimal_alanine(self, tmp_path: Path) -> None:
        path = tmp_path / "tiny.pdb"
        path.write_text(_TINY_PDB)
        struct = parse_pdb(path)
        atoms = list(struct.get_atoms())
        assert len(atoms) == 5
        # Element check on the alpha carbon
        ca = next(a for a in atoms if a.get_name() == "CA")
        assert ca.element == "C"

    def test_raises_on_empty_input(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.pdb"
        path.write_text("")
        with pytest.raises(PdbParseError):
            parse_pdb(path)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, PdbParseError)):
            parse_pdb(tmp_path / "does_not_exist.pdb")

    def test_parses_from_string(self) -> None:
        struct = parse_pdb(_TINY_PDB)
        atoms = list(struct.get_atoms())
        assert len(atoms) == 5


class TestCountHeavyAtoms:
    def test_alanine_has_five_heavy_atoms(self, tmp_path: Path) -> None:
        path = tmp_path / "tiny.pdb"
        path.write_text(_TINY_PDB)
        assert count_heavy_atoms(parse_pdb(path)) == 5


class TestRoundTrip:
    def test_xyz_preserved_to_3dp(self, tmp_path: Path) -> None:
        path = tmp_path / "tiny.pdb"
        path.write_text(_TINY_PDB)
        struct = parse_pdb(path)

        out = tmp_path / "out.pdb"
        write_pdb(struct, out)

        struct2 = parse_pdb(out)
        atoms1 = sorted(struct.get_atoms(), key=lambda a: a.serial_number)
        atoms2 = sorted(struct2.get_atoms(), key=lambda a: a.serial_number)

        assert len(atoms1) == len(atoms2)
        for a, b in zip(atoms1, atoms2, strict=True):
            assert a.get_name() == b.get_name()
            assert a.element == b.element
            for c1, c2 in zip(a.coord, b.coord, strict=True):
                assert round(float(c1), 3) == round(float(c2), 3)

    def test_chain_and_residue_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "tiny.pdb"
        path.write_text(_TINY_PDB)
        struct = parse_pdb(path)
        chains_before = {c.id for c in struct.get_chains()}

        out = tmp_path / "out.pdb"
        write_pdb(struct, out)
        struct2 = parse_pdb(out)
        chains_after = {c.id for c in struct2.get_chains()}
        assert chains_before == chains_after

        resnames_before = {r.resname for r in struct.get_residues()}
        resnames_after = {r.resname for r in struct2.get_residues()}
        assert resnames_before == resnames_after


# Property tests cover small random coordinate perturbations to catch
# round-off drift in the writer's column-width formatting.
@settings(max_examples=20, deadline=2000)
@given(
    coords=st.lists(
        st.tuples(
            st.floats(min_value=-99.0, max_value=99.0, allow_nan=False, allow_infinity=False),
            st.floats(min_value=-99.0, max_value=99.0, allow_nan=False, allow_infinity=False),
            st.floats(min_value=-99.0, max_value=99.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=1,
        max_size=4,
    ),
)
def test_round_trip_property_random_coords(
    coords: list[tuple[float, float, float]], tmp_path: Path
) -> None:
    """For random heavy atoms, round-trip preserves xyz to 3 decimal places."""
    atom_lines = []
    for i, (x, y, z) in enumerate(coords, start=1):
        # PDB columns: 1-6 record, 7-11 serial, 13-16 name, 18-20 res, 22 chain,
        # 23-26 seqnum, 31-38 x, 39-46 y, 47-54 z, 55-60 occ, 61-66 temp,
        # 77-78 element. Keep names valid by sticking to "CA" and "ALA".
        atom_lines.append(
            f"ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
            "  1.00  0.00           C"
        )
    pdb = "HEADER    PROP                                    01-JAN-26   XXXX\n"
    pdb += "\n".join(atom_lines) + "\nEND\n"

    src = tmp_path / "src.pdb"
    src.write_text(pdb)
    struct = parse_pdb(src)

    out = tmp_path / "out.pdb"
    write_pdb(struct, out)
    struct2 = parse_pdb(out)

    atoms1 = list(struct.get_atoms())
    atoms2 = list(struct2.get_atoms())
    assert len(atoms1) == len(atoms2) == len(coords)
    for a, b in zip(atoms1, atoms2, strict=True):
        for c1, c2 in zip(a.coord, b.coord, strict=True):
            assert round(float(c1), 3) == round(float(c2), 3)
