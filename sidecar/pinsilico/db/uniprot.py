"""UniProt client.

Two endpoints used:

* ``https://rest.uniprot.org/uniprotkb/<accession>.fasta`` for the
  sequence of a known accession.
* ``https://rest.uniprot.org/uniprotkb/search?query=…`` for free-text
  search returning a JSON page of result records.

All HTTP via :class:`httpx.Client` so respx mocks intercept cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from pinsilico.db.base import DbError

UNIPROT_REST_BASE = "https://rest.uniprot.org"
_PROVIDER = "uniprot"
_DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True, slots=True)
class UniProtEntry:
    """A UniProt FASTA record reduced to the fields downstream code uses.

    Attributes:
        accession: Primary accession (e.g. ``"P12345"``).
        description: FASTA description line minus the leading ``>``.
        sequence: Raw amino-acid sequence with newlines removed.
    """

    accession: str
    description: str
    sequence: str


def _http() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT_S, follow_redirects=True)


def _parse_fasta(fasta_text: str) -> tuple[str, str]:
    """Split a single-record FASTA into ``(description, sequence)``.

    Multi-record FASTAs are not in scope here — the UniProt single-entry
    endpoint always returns one record.
    """
    lines = [line for line in fasta_text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(">"):
        msg = "input is not a FASTA record"
        raise DbError(msg, provider=_PROVIDER)
    description = lines[0].lstrip(">").strip()
    sequence = "".join(lines[1:]).replace(" ", "").strip()
    return description, sequence


def fetch_uniprot(accession: str) -> UniProtEntry:
    """Fetch the FASTA record for a UniProt accession."""
    acc = accession.upper()
    url = f"{UNIPROT_REST_BASE}/uniprotkb/{acc}.fasta"
    try:
        with _http() as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise DbError(
            f"UniProt request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"UniProt returned {response.status_code} for {acc}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    text = response.text
    if not text.strip():
        raise DbError(
            f"UniProt returned an empty body for {acc}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    description, sequence = _parse_fasta(text)
    return UniProtEntry(accession=acc, description=description, sequence=sequence)


def search_uniprot(query: str, *, limit: int = 25) -> list[str]:
    """Free-text search UniProt; return a list of primary accessions."""
    url = f"{UNIPROT_REST_BASE}/uniprotkb/search"
    try:
        with _http() as client:
            response = client.get(
                url,
                params={
                    "query": query,
                    "format": "json",
                    "size": str(limit),
                    "fields": "accession",
                },
            )
    except httpx.HTTPError as exc:
        raise DbError(
            f"UniProt search request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"UniProt search returned {response.status_code}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    body = response.json()
    results = body.get("results", [])
    return [str(item["primaryAccession"]) for item in results if "primaryAccession" in item]
