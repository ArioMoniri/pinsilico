"""RDKit-backed SDF / SMILES parser/writer.

Phase 1 wraps a small subset of RDKit so downstream Phase 3 docking
adapters and Phase 2 DB clients (PubChem returns SDF) talk to a typed
interface rather than RDKit's globally-mutable :class:`Mol`.

Only the calls we actually need are exposed:

* :func:`mol_from_smiles` — SMILES → :class:`Mol`
* :func:`canonical_smiles` — SMILES or :class:`Mol` → canonical SMILES
* :func:`read_sdf` / :func:`write_sdf` — round-trippable file IO
* :func:`count_heavy_atoms` — for the docking layer's box sizing
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rdkit import Chem, RDLogger

if TYPE_CHECKING:
    from rdkit.Chem.rdchem import Mol

# RDKit prints noisy warnings to stderr by default; silence them — anything
# user-facing flows through our exceptions or structlog. RDLogger.DisableLog
# is missing from the bundled stubs, hence the targeted type: ignore.
RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]


class SdfParseError(ValueError):
    """Raised when SDF/SMILES input is empty, malformed, or yields no molecules."""


def mol_from_smiles(smiles: str) -> Mol:
    """Parse a SMILES string into an RDKit :class:`Mol`.

    Raises :class:`SdfParseError` on empty input or any parse failure.
    """
    if not smiles or not smiles.strip():
        msg = "SMILES input is empty"
        raise SdfParseError(msg)
    # RDKit's bundled stubs declare MolFromSmiles -> Mol (not Optional),
    # but the runtime returns None on parse failure. Branch on truthiness.
    mol: Mol | None = Chem.MolFromSmiles(smiles)
    if not mol:
        msg = f"RDKit could not parse SMILES: {smiles!r}"
        raise SdfParseError(msg)
    return mol


def canonical_smiles(smiles_or_mol: str | Mol) -> str:
    """Return the canonical SMILES form.

    Accepts either a SMILES string (parsed first) or an existing :class:`Mol`.
    Always returns the same string for chemically-equivalent inputs.
    """
    mol = mol_from_smiles(smiles_or_mol) if isinstance(smiles_or_mol, str) else smiles_or_mol
    return Chem.MolToSmiles(mol, canonical=True)


def count_heavy_atoms(mol: Mol) -> int:
    """Return the number of heavy (non-hydrogen) atoms in ``mol``."""
    return int(mol.GetNumHeavyAtoms())


def read_sdf(path: Path) -> list[Mol]:
    """Parse an SDF file into a list of :class:`Mol` objects.

    Raises:
        FileNotFoundError: if ``path`` doesn't exist.
        SdfParseError: if the file exists but contains no parseable mols.
    """
    if not path.exists():
        msg = f"SDF file not found: {path}"
        raise FileNotFoundError(msg)
    supplier = Chem.SDMolSupplier(str(path), sanitize=True, removeHs=False)
    mols: list[Mol] = [m for m in supplier if m is not None]
    if not mols:
        msg = f"SDF file contained no parseable molecules: {path}"
        raise SdfParseError(msg)
    return mols


def write_sdf(mols: list[Mol], destination: Path) -> None:
    """Write the given mols to ``destination`` in SDF format.

    The destination's parent directory is created if needed so callers
    can write into a fresh ``tmp_path`` without an explicit ``mkdir``.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = Chem.SDWriter(str(destination))
    try:
        for m in mols:
            writer.write(m)
    finally:
        writer.close()
