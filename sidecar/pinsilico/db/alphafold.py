"""AlphaFold DB client.

Fetches predicted protein structures by UniProt accession. AlphaFold
files follow the URL pattern::

    https://alphafold.ebi.ac.uk/files/AF-<ACC>-F1-model_v4.pdb

The ``-F1`` segment is the fragment number; single-domain proteins are
always F1. The ``v4`` is AlphaFold's database version (current as of
this build).
"""

from __future__ import annotations

import httpx

from pinsilico.db.base import DbError, PdbEntry

ALPHAFOLD_FILES_BASE = "https://alphafold.ebi.ac.uk/files"
_PROVIDER = "alphafold"
_DEFAULT_TIMEOUT_S = 30.0
_MODEL_VERSION = "v4"


def _http() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT_S, follow_redirects=True)


def fetch_alphafold_pdb(uniprot_accession: str) -> PdbEntry:
    """Fetch an AlphaFold-predicted structure by UniProt accession.

    Args:
        uniprot_accession: Case-insensitive UniProt id (e.g. ``"P12345"``).

    Returns:
        :class:`PdbEntry` with ``identifier`` set to the AlphaFold model
        id (e.g. ``"AF-P12345-F1"``), ``resolution_angstrom`` left None
        (predicted structures have no measured resolution), and
        ``pdb_text`` set to the raw PDB block.

    Raises:
        DbError: on any non-200 response, network failure, or empty body.
    """
    acc = uniprot_accession.upper()
    model_id = f"AF-{acc}-F1"
    url = f"{ALPHAFOLD_FILES_BASE}/{model_id}-model_{_MODEL_VERSION}.pdb"

    try:
        with _http() as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise DbError(
            f"AlphaFold request failed: {exc}",
            provider=_PROVIDER,
            original=exc,
        ) from exc

    if response.status_code != httpx.codes.OK:
        raise DbError(
            f"AlphaFold returned {response.status_code} for {model_id}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    text = response.text
    if not text.strip():
        raise DbError(
            f"AlphaFold returned an empty body for {model_id}",
            provider=_PROVIDER,
            status_code=response.status_code,
        )

    return PdbEntry(
        identifier=model_id,
        title=f"AlphaFold prediction for UniProt {acc}",
        organism=None,
        resolution_angstrom=None,
        pdb_text=text,
    )
