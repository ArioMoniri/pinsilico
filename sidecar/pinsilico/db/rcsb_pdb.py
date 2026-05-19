"""RCSB PDB client.

Two endpoints used:

* **Files API** — ``https://files.rcsb.org/download/<ID>.pdb``. Returns
  the raw PDB block for a known structure id. Used by
  :func:`fetch_pdb_by_id`.
* **Search API v2** — ``https://search.rcsb.org/rcsbsearch/v2/query``.
  POST a JSON query, get a ranked id list. Used by
  :func:`search_pdb_by_keyword`.

All HTTP is via :class:`httpx.Client` so :func:`respx.mock` can
intercept it cleanly in tests (BUILD_PROMPT.md §6).
"""

from __future__ import annotations

from typing import Any

import httpx

from pinsilico.db.base import DbError, PdbEntry

RCSB_FILES_BASE = "https://files.rcsb.org/download"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

_PROVIDER = "rcsb"
_DEFAULT_TIMEOUT_S = 30.0


def _http() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT_S, follow_redirects=True)


def fetch_pdb_by_id(identifier: str) -> PdbEntry:
    """Fetch a single PDB file from RCSB by identifier.

    Args:
        identifier: 4-char PDB id (case-insensitive; upper-cased before
            the request to match RCSB's URL convention).

    Returns:
        :class:`PdbEntry` with ``pdb_text`` set to the raw PDB block.
        ``title`` and ``organism`` are unset for the bare file endpoint
        — call the Data API (Phase 5 extension) for full metadata.

    Raises:
        DbError: on any non-200 response, network failure, or empty body.
    """
    pdb_id = identifier.upper()
    url = f"{RCSB_FILES_BASE}/{pdb_id}.pdb"
    try:
        with _http() as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise DbError(
            f"RCSB request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"RCSB returned {response.status_code} for {pdb_id}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    text = response.text
    if not text.strip():
        raise DbError(
            f"RCSB returned an empty body for {pdb_id}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    return PdbEntry(
        identifier=pdb_id,
        title="",
        organism=None,
        resolution_angstrom=None,
        pdb_text=text,
    )


def _build_search_payload(keyword: str, limit: int) -> dict[str, Any]:
    """Build a minimal RCSB Search v2 query body.

    The shape follows the documented "full-text" service. We deliberately
    don't expose every Search v2 knob — the chemistry-discovery flow only
    needs keyword + limit. Phase 5 can extend with structured filters
    when the UI grows them.
    """
    return {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": keyword},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": limit},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
            "scoring_strategy": "combined",
        },
    }


def search_pdb_by_keyword(keyword: str, *, limit: int = 25) -> list[str]:
    """Search RCSB for structures matching a free-text keyword.

    Args:
        keyword: Free-text search query (e.g. ``"HIV protease"``).
        limit: Maximum number of identifiers to return.

    Returns:
        Ranked list of PDB identifiers. Empty list when RCSB returns
        204 No Content (i.e. zero matches).

    Raises:
        DbError: on any non-204 / non-200 response or network failure.
    """
    payload = _build_search_payload(keyword, limit)
    try:
        with _http() as client:
            response = client.post(RCSB_SEARCH_URL, json=payload)
    except httpx.HTTPError as exc:
        raise DbError(
            f"RCSB search request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code == httpx.codes.NO_CONTENT:
        return []
    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"RCSB search returned {response.status_code}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    body = response.json()
    result_set = body.get("result_set", [])
    return [str(item["identifier"]) for item in result_set]
