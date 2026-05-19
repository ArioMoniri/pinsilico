"""File-format I/O for chemistry inputs.

* :mod:`pinsilico.io.pdb` — Biopython-backed PDB parsing/writing.
* :mod:`pinsilico.io.sdf` — RDKit-backed SDF/SMILES parsing/writing.

Each module surfaces a typed adapter and a single ``*ParseError`` so
upstream code can ``except`` against one error class rather than catching
Biopython / RDKit internals.
"""

from __future__ import annotations

__all__: list[str] = []
