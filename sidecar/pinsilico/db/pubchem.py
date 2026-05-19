"""PubChem PUG REST client.

Two endpoints used:

* ``/rest/pug/compound/smiles/<smiles>/cids/JSON`` — SMILES → CID list
* ``/rest/pug/compound/cid/<cid>/SDF`` — CID → SDF block

We return the *first* CID from a SMILES query because PubChem orders
matches by descending relevance.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from pinsilico.db.base import DbError

PUBCHEM_REST_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROVIDER = "pubchem"
_DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True, slots=True)
class PubChemCompound:
    """A small-molecule record from PubChem.

    Attributes:
        cid: PubChem Compound ID (e.g. 702 for ethanol).
        sdf_text: Raw SDF block. Empty string when only metadata was
            requested.
    """

    cid: int
    sdf_text: str


def _http() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT_S, follow_redirects=True)


def smiles_to_cid(smiles: str) -> int:
    """Return the first CID matching the given SMILES.

    Raises:
        DbError: if PubChem returns non-200 or zero matches.
    """
    url = f"{PUBCHEM_REST_BASE}/compound/smiles/{smiles}/cids/JSON"
    try:
        with _http() as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise DbError(
            f"PubChem SMILES request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"PubChem returned {response.status_code} for SMILES {smiles!r}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    body = response.json()
    cids = body.get("IdentifierList", {}).get("CID", [])
    if not cids:
        raise DbError(
            f"PubChem matched no compounds for SMILES {smiles!r}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )
    return int(cids[0])


def fetch_sdf_by_cid(cid: int) -> PubChemCompound:
    """Fetch the SDF block for a PubChem CID."""
    url = f"{PUBCHEM_REST_BASE}/compound/cid/{cid}/SDF"
    try:
        with _http() as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise DbError(
            f"PubChem SDF request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"PubChem returned {response.status_code} for CID {cid}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    text = response.text
    if not text.strip():
        raise DbError(
            f"PubChem returned an empty SDF for CID {cid}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    return PubChemCompound(cid=cid, sdf_text=text)
