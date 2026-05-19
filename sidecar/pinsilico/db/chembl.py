"""ChEMBL client.

Three endpoints used:

* ``/target/search`` — keyword search for biological targets
* ``/activity`` — fetch bioactivities for a target, filtered by pChEMBL
* ``/molecule/<chembl_id>`` — fetch a single small-molecule record

ChEMBL's response shape is JSON-stable across the v33+ era; we tolerate
missing optional fields (``pchembl_value`` is often ``null`` for non-
binding-affinity activities) by filtering them out client-side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from pinsilico.db.base import DbError

CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_PROVIDER = "chembl"
_DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True, slots=True)
class ChemblTarget:
    """A ChEMBL biological target record."""

    target_chembl_id: str
    pref_name: str
    organism: str | None


@dataclass(frozen=True, slots=True)
class ChemblActivity:
    """A ChEMBL bioactivity record."""

    molecule_chembl_id: str
    pchembl_value: float
    standard_type: str
    standard_value: float | None
    standard_units: str | None


@dataclass(frozen=True, slots=True)
class ChemblCompound:
    """A ChEMBL small-molecule record."""

    molecule_chembl_id: str
    pref_name: str | None
    canonical_smiles: str
    max_phase: int | None


def _http() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT_S, follow_redirects=True)


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """Shared JSON GET with envelope-friendly error mapping."""
    try:
        with _http() as client:
            response = client.get(url, params=params, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise DbError(
            f"ChEMBL request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc
    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"ChEMBL returned {response.status_code} for {url}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )
    return response.json()


def search_targets(query: str, *, limit: int = 25) -> list[ChemblTarget]:
    """Free-text search ChEMBL targets."""
    body = _get_json(
        f"{CHEMBL_API_BASE}/target/search",
        params={"q": query, "format": "json", "limit": limit},
    )
    return [
        ChemblTarget(
            target_chembl_id=str(item["target_chembl_id"]),
            pref_name=str(item.get("pref_name", "")),
            organism=item.get("organism"),
        )
        for item in body.get("targets", [])
    ]


def fetch_activities(
    target_chembl_id: str,
    *,
    pchembl_threshold: float,
    limit: int = 100,
) -> list[ChemblActivity]:
    """Fetch bioactivities for a target.

    Filters records whose ``pchembl_value`` is null on the client because
    the upstream ``pchembl_value__isnull=false`` query parameter is
    inconsistent across ChEMBL versions; doing it locally is reliable.
    """
    body = _get_json(
        f"{CHEMBL_API_BASE}/activity",
        params={
            "target_chembl_id": target_chembl_id,
            "pchembl_value__gte": pchembl_threshold,
            "format": "json",
            "limit": limit,
        },
    )
    activities: list[ChemblActivity] = []
    for item in body.get("activities", []):
        raw_pchembl = item.get("pchembl_value")
        if raw_pchembl is None:
            continue
        try:
            pchembl = float(raw_pchembl)
        except (TypeError, ValueError):
            continue
        std_val = item.get("standard_value")
        activities.append(
            ChemblActivity(
                molecule_chembl_id=str(item["molecule_chembl_id"]),
                pchembl_value=pchembl,
                standard_type=str(item.get("standard_type", "")),
                standard_value=float(std_val) if std_val is not None else None,
                standard_units=item.get("standard_units"),
            )
        )
    return activities


def fetch_compound(molecule_chembl_id: str) -> ChemblCompound:
    """Fetch a single small-molecule record from ChEMBL."""
    body = _get_json(f"{CHEMBL_API_BASE}/molecule/{molecule_chembl_id}")
    structures = body.get("molecule_structures") or {}
    return ChemblCompound(
        molecule_chembl_id=str(body["molecule_chembl_id"]),
        pref_name=body.get("pref_name"),
        canonical_smiles=str(structures.get("canonical_smiles", "")),
        max_phase=body.get("max_phase"),
    )
