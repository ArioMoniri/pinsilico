"""The ``.pinsilico`` session bundle format.

A session bundle is a zip archive containing:

* ``manifest.json`` — schema version, seed, protein + ligand records
* ``proteins/<id>.pdb`` — raw PDB blocks
* ``pockets/<protein_id>.json`` — per-protein fpocket results
* ``ligands.json`` — ligand metadata

The bundle is **deterministic**: identical input always produces
identical bytes. We zero the zip-entry mtime fields and use the
``ZIP_DEFLATED`` compression at level 6 so reproducible-build pipelines
(BUILD_PROMPT.md §8.8) can checksum sessions across platforms.

BUILD_PROMPT.md §10 calls for a Hypothesis-driven round-trip test;
the property test lives in :mod:`tests.unit.test_session_bundle`.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

_MANIFEST_NAME = "manifest.json"
_LIGANDS_NAME = "ligands.json"
_PROTEINS_DIR = "proteins"
_POCKETS_DIR = "pockets"

# Fixed mtime: 1980-01-01 (zip's epoch). Same value on every save → identical
# bytes across platforms.
_EPOCH_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class SessionPocket:
    identifier: str
    centroid_xyz: tuple[float, float, float]
    volume_a3: float
    hydrophobicity: float
    druggability_score: float
    residue_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionProtein:
    identifier: str
    source: str
    role: str
    pdb_text: str
    pockets: list[SessionPocket] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SessionLigand:
    identifier: str
    source: str
    smiles: str
    is_inhibitor: bool
    is_natural_ligand: bool


@dataclass(frozen=True, slots=True)
class SessionBundle:
    version: str
    seed: int
    proteins: list[SessionProtein] = field(default_factory=list)
    ligands: list[SessionLigand] = field(default_factory=list)


def _to_manifest(bundle: SessionBundle) -> dict[str, object]:
    """Return the manifest.json shape. PDB text + ligands live in their own files."""
    return {
        "version": bundle.version,
        "seed": bundle.seed,
        "proteins": [
            {
                "identifier": p.identifier,
                "source": p.source,
                "role": p.role,
                # pdb_text lives in proteins/<id>.pdb
            }
            for p in bundle.proteins
        ],
    }


def save_bundle(bundle: SessionBundle, destination: Path) -> None:
    """Write ``bundle`` to ``destination``.

    Uses a deterministic zip layout so saves are byte-reproducible.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        _write_entry(zf, _MANIFEST_NAME, json.dumps(_to_manifest(bundle), sort_keys=True, indent=2))
        for p in bundle.proteins:
            _write_entry(zf, f"{_PROTEINS_DIR}/{p.identifier}.pdb", p.pdb_text)
            _write_entry(
                zf,
                f"{_POCKETS_DIR}/{p.identifier}.json",
                json.dumps(
                    [asdict(pocket) for pocket in p.pockets],
                    sort_keys=True,
                    indent=2,
                ),
            )
        _write_entry(
            zf,
            _LIGANDS_NAME,
            json.dumps([asdict(lig) for lig in bundle.ligands], sort_keys=True, indent=2),
        )
    destination.write_bytes(buf.getvalue())


def _write_entry(zf: zipfile.ZipFile, name: str, content: str) -> None:
    """Write one entry with a fixed mtime so bytes stay reproducible."""
    info = zipfile.ZipInfo(filename=name, date_time=_EPOCH_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, content)


def load_bundle(source: Path) -> SessionBundle:
    """Read a session bundle from ``source``.

    Raises:
        FileNotFoundError: when ``source`` doesn't exist.
        ValueError: when the file isn't a valid bundle (missing manifest,
            corrupt zip, JSON parse error).
    """
    if not source.exists():
        msg = f"Session bundle not found: {source}"
        raise FileNotFoundError(msg)
    try:
        with zipfile.ZipFile(source) as zf:
            try:
                manifest = json.loads(zf.read(_MANIFEST_NAME).decode("utf-8"))
            except KeyError as exc:
                msg = "bundle missing manifest.json"
                raise ValueError(msg) from exc

            proteins: list[SessionProtein] = []
            for entry in manifest.get("proteins", []):
                pid = entry["identifier"]
                pdb_text = zf.read(f"{_PROTEINS_DIR}/{pid}.pdb").decode("utf-8")
                try:
                    raw_pockets = json.loads(
                        zf.read(f"{_POCKETS_DIR}/{pid}.json").decode("utf-8"),
                    )
                except KeyError:
                    raw_pockets = []
                pockets = [
                    SessionPocket(
                        identifier=p["identifier"],
                        centroid_xyz=tuple(p["centroid_xyz"]),
                        volume_a3=p["volume_a3"],
                        hydrophobicity=p["hydrophobicity"],
                        druggability_score=p["druggability_score"],
                        residue_ids=tuple(p["residue_ids"]),
                    )
                    for p in raw_pockets
                ]
                proteins.append(
                    SessionProtein(
                        identifier=pid,
                        source=entry["source"],
                        role=entry["role"],
                        pdb_text=pdb_text,
                        pockets=pockets,
                    ),
                )

            try:
                raw_ligands = json.loads(zf.read(_LIGANDS_NAME).decode("utf-8"))
            except KeyError:
                raw_ligands = []
            ligands = [
                SessionLigand(
                    identifier=lig["identifier"],
                    source=lig["source"],
                    smiles=lig["smiles"],
                    is_inhibitor=lig["is_inhibitor"],
                    is_natural_ligand=lig["is_natural_ligand"],
                )
                for lig in raw_ligands
            ]
    except zipfile.BadZipFile as exc:
        msg = f"corrupt session bundle: {exc}"
        raise ValueError(msg) from exc

    return SessionBundle(
        version=manifest["version"],
        seed=int(manifest["seed"]),
        proteins=proteins,
        ligands=ligands,
    )
