"""``/db/{provider}/...`` routes.

Thin wrappers over the Phase 2 DB clients. Each provider is one or two
GET endpoints. Error mapping is uniform: a `DbError` from any provider
becomes a 502 Bad Gateway with the standard envelope and the provider's
status code surfaced under ``details``.

Routes:

* ``GET /db/rcsb/structures/{pdb_id}`` — RCSB PDB file fetch
* ``GET /db/rcsb/search?q=...&limit=...`` — RCSB keyword search
* ``GET /db/uniprot/proteins/{accession}`` — UniProt FASTA fetch
* ``GET /db/uniprot/search?q=...&limit=...`` — UniProt search
* ``GET /db/alphafold/structures/{accession}`` — AlphaFold predicted PDB
* ``GET /db/chembl/targets?q=...&limit=...`` — ChEMBL target search
* ``GET /db/chembl/activities?target=...&pchembl_threshold=...`` — bioactivities
* ``GET /db/chembl/compounds/{molecule_id}`` — compound lookup
* ``GET /db/pubchem/by_smiles?smiles=...`` — SMILES → CID
* ``GET /db/pubchem/compounds/{cid}/sdf`` — CID → SDF
* ``GET /db/drugbank/drugs/{id}?csv_path=...`` — local DrugBank lookup
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from pinsilico.db import alphafold, chembl, drugbank, pubchem, rcsb_pdb, uniprot
from pinsilico.db.base import DbError, PdbEntry

router = APIRouter(prefix="/db", tags=["db"])


def _db_error_to_http(exc: DbError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "code": "DB_ERROR",
            "message": str(exc),
            "provider": exc.provider,
            "upstream_status": exc.status_code,
        },
    )


# --------------------------------------------------------------- response models


class PdbEntryResponse(BaseModel):
    identifier: str
    title: str
    organism: str | None
    resolution_angstrom: float | None
    pdb_text: str

    @classmethod
    def from_dataclass(cls, p: PdbEntry) -> PdbEntryResponse:
        return cls(
            identifier=p.identifier,
            title=p.title,
            organism=p.organism,
            resolution_angstrom=p.resolution_angstrom,
            pdb_text=p.pdb_text,
        )


class IdentifierList(BaseModel):
    identifiers: list[str]


# ----------------------------------------------------------------- RCSB


@router.get("/rcsb/structures/{pdb_id}", response_model=PdbEntryResponse)
def rcsb_fetch(pdb_id: str) -> PdbEntryResponse:
    try:
        return PdbEntryResponse.from_dataclass(rcsb_pdb.fetch_pdb_by_id(pdb_id))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc


@router.get("/rcsb/search", response_model=IdentifierList)
def rcsb_search(
    q: Annotated[str, Query(min_length=1, description="Free-text query")],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> IdentifierList:
    try:
        return IdentifierList(identifiers=rcsb_pdb.search_pdb_by_keyword(q, limit=limit))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc


# --------------------------------------------------------------- UniProt


class UniProtResponse(BaseModel):
    accession: str
    description: str
    sequence: str


@router.get("/uniprot/proteins/{accession}", response_model=UniProtResponse)
def uniprot_fetch(accession: str) -> UniProtResponse:
    try:
        e = uniprot.fetch_uniprot(accession)
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return UniProtResponse(accession=e.accession, description=e.description, sequence=e.sequence)


@router.get("/uniprot/search", response_model=IdentifierList)
def uniprot_search_route(
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> IdentifierList:
    try:
        return IdentifierList(identifiers=uniprot.search_uniprot(q, limit=limit))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc


# --------------------------------------------------------------- AlphaFold


@router.get("/alphafold/structures/{accession}", response_model=PdbEntryResponse)
def alphafold_fetch(accession: str) -> PdbEntryResponse:
    try:
        return PdbEntryResponse.from_dataclass(alphafold.fetch_alphafold_pdb(accession))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc


# --------------------------------------------------------------- ChEMBL


class ChemblTargetResponse(BaseModel):
    target_chembl_id: str
    pref_name: str
    organism: str | None


class ChemblActivityResponse(BaseModel):
    molecule_chembl_id: str
    pchembl_value: float
    standard_type: str
    standard_value: float | None
    standard_units: str | None


class ChemblCompoundResponse(BaseModel):
    molecule_chembl_id: str
    pref_name: str | None
    canonical_smiles: str
    max_phase: int | None


@router.get("/chembl/targets", response_model=list[ChemblTargetResponse])
def chembl_targets(
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> list[ChemblTargetResponse]:
    try:
        targets = chembl.search_targets(q, limit=limit)
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return [
        ChemblTargetResponse(
            target_chembl_id=t.target_chembl_id,
            pref_name=t.pref_name,
            organism=t.organism,
        )
        for t in targets
    ]


@router.get("/chembl/activities", response_model=list[ChemblActivityResponse])
def chembl_activities(
    target: Annotated[str, Query(min_length=1)],
    pchembl_threshold: Annotated[float, Query(ge=0.0, le=15.0)] = 6.0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ChemblActivityResponse]:
    try:
        acts = chembl.fetch_activities(
            target,
            pchembl_threshold=pchembl_threshold,
            limit=limit,
        )
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return [
        ChemblActivityResponse(
            molecule_chembl_id=a.molecule_chembl_id,
            pchembl_value=a.pchembl_value,
            standard_type=a.standard_type,
            standard_value=a.standard_value,
            standard_units=a.standard_units,
        )
        for a in acts
    ]


@router.get("/chembl/compounds/{molecule_id}", response_model=ChemblCompoundResponse)
def chembl_compound(molecule_id: str) -> ChemblCompoundResponse:
    try:
        c = chembl.fetch_compound(molecule_id)
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return ChemblCompoundResponse(
        molecule_chembl_id=c.molecule_chembl_id,
        pref_name=c.pref_name,
        canonical_smiles=c.canonical_smiles,
        max_phase=c.max_phase,
    )


# --------------------------------------------------------------- PubChem


class PubChemSmilesResponse(BaseModel):
    smiles: str
    cid: int


class PubChemSdfResponse(BaseModel):
    cid: int
    sdf_text: str


@router.get("/pubchem/by_smiles", response_model=PubChemSmilesResponse)
def pubchem_smiles_to_cid(smiles: Annotated[str, Query(min_length=1)]) -> PubChemSmilesResponse:
    try:
        return PubChemSmilesResponse(smiles=smiles, cid=pubchem.smiles_to_cid(smiles))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc


@router.get("/pubchem/compounds/{cid}/sdf", response_model=PubChemSdfResponse)
def pubchem_sdf(cid: int) -> PubChemSdfResponse:
    try:
        c = pubchem.fetch_sdf_by_cid(cid)
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return PubChemSdfResponse(cid=c.cid, sdf_text=c.sdf_text)


# --------------------------------------------------------------- DrugBank


class DrugBankResponse(BaseModel):
    drugbank_id: str
    name: str
    smiles: str
    molecular_formula: str
    groups: tuple[str, ...] = Field(default_factory=tuple)


def _drugbank_csv_path(csv_path: str | None) -> Path:
    """Resolve the DrugBank CSV path. Defaults to the bundled location."""
    if csv_path:
        return Path(csv_path)
    return Path(__file__).resolve().parents[2] / "resources" / "drugbank.csv"


@router.get("/drugbank/drugs/{drugbank_id}", response_model=DrugBankResponse)
def drugbank_lookup(
    drugbank_id: str,
    csv_path: Annotated[str | None, Query(description="Override CSV path (tests)")] = None,
) -> DrugBankResponse:
    try:
        rec = drugbank.find_drug_by_id(drugbank_id, csv_path=_drugbank_csv_path(csv_path))
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return DrugBankResponse(
        drugbank_id=rec.drugbank_id,
        name=rec.name,
        smiles=rec.smiles,
        molecular_formula=rec.molecular_formula,
        groups=rec.groups,
    )


@router.get("/drugbank/search", response_model=list[DrugBankResponse])
def drugbank_search(
    q: Annotated[str, Query(description="Keyword; empty returns first `limit` rows")] = "",
    limit: Annotated[int, Query(ge=1, le=500)] = 25,
    csv_path: Annotated[str | None, Query(description="Override CSV path (tests)")] = None,
) -> list[DrugBankResponse]:
    try:
        rows = drugbank.search_drugs(q, csv_path=_drugbank_csv_path(csv_path), limit=limit)
    except DbError as exc:
        raise _db_error_to_http(exc) from exc
    return [
        DrugBankResponse(
            drugbank_id=r.drugbank_id,
            name=r.name,
            smiles=r.smiles,
            molecular_formula=r.molecular_formula,
            groups=r.groups,
        )
        for r in rows
    ]


__all__: list[str] = ["router"]
