"""Biopython-backed PDB parser/writer.

Phase 1 surface is intentionally narrow: parse from path or string, write
back to path, count heavy atoms. Phase 2 (DB clients) feeds PDB blobs
straight to :func:`parse_pdb` from RCSB / AlphaFold. Phase 3 (pocket +
docking) consumes the resulting :class:`Bio.PDB.Structure.Structure`.

Biopython's :class:`PDBParser` is permissive by default (``PERMISSIVE=1``),
which we keep — most real PDB files contain enough quirks to make strict
parsing impractical. We do, however, convert "no atoms parsed" and "input
is empty" into a typed :class:`PdbParseError` so callers can ``except``
against one class.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from Bio.PDB import PDBIO, PDBParser

if TYPE_CHECKING:
    from Bio.PDB.Structure import Structure


class PdbParseError(ValueError):
    """Raised when PDB input is empty, missing, or contains no atoms."""


PdbSource = Path | str


def _read_source(source: PdbSource) -> str:
    """Return the raw PDB text, treating short non-path strings as inline data.

    A ``Path`` is always read from disk. A ``str`` is interpreted as a path
    only if (a) it points to an existing file or (b) it doesn't contain
    newlines and looks like a filename. Otherwise it's treated as inline
    PDB content. This keeps the API ergonomic in tests (pass a literal)
    without surprising users who pass a relative path.
    """
    if isinstance(source, Path):
        if not source.exists():
            msg = f"PDB file not found: {source}"
            raise FileNotFoundError(msg)
        text = source.read_text("utf-8")
    elif "\n" in source or source.lstrip().startswith(("HEADER", "ATOM", "HETATM", "MODEL")):
        text = source
    else:
        path = Path(source)
        if not path.exists():
            msg = f"PDB file not found: {source}"
            raise FileNotFoundError(msg)
        text = path.read_text("utf-8")
    if not text.strip():
        msg = "PDB input is empty"
        raise PdbParseError(msg)
    return text


def parse_pdb(source: PdbSource, *, structure_id: str = "pinsilico") -> Structure:
    """Parse a PDB file or literal block into a Biopython :class:`Structure`.

    Args:
        source: Either a :class:`Path`, a string path, or a literal PDB
            block (detected by newlines / leading record keyword).
        structure_id: Identifier attached to the parsed structure.

    Raises:
        PdbParseError: if the input is empty, contains no atoms, or
            Biopython raises a parse-internal exception.
        FileNotFoundError: if the source points to a path that doesn't
            exist.
    """
    text = _read_source(source)
    parser = PDBParser(QUIET=True)
    try:
        struct = parser.get_structure(structure_id, StringIO(text))
    except Exception as exc:
        msg = f"Biopython failed to parse the PDB input: {exc}"
        raise PdbParseError(msg) from exc
    if not list(struct.get_atoms()):
        msg = "PDB input contained no atoms"
        raise PdbParseError(msg)
    return struct


def write_pdb(structure: Structure, destination: Path) -> None:
    """Write ``structure`` to ``destination`` in PDB format.

    The destination's parent directory is created if needed so callers
    can write into a fresh ``tmp_path`` directory without an explicit
    ``mkdir``.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(destination))


def count_heavy_atoms(structure: Structure) -> int:
    """Return the number of non-hydrogen atoms in ``structure``.

    fpocket and the docking layer only care about heavy atoms; this
    helper avoids repeatedly filtering ``get_atoms()`` at call sites.
    """
    return sum(1 for atom in structure.get_atoms() if atom.element != "H")
