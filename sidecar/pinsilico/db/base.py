"""Shared types for DB-client modules.

A provider exposes one or more typed dataclasses describing what it
returns (e.g. :class:`PdbEntry`, :class:`ChemblCompound`). The Phase 5
route layer converts these into Pydantic response models — the
dataclasses stay implementation-detail.

Errors flow through :class:`DbError` so the FastAPI layer can map
provider-specific failures into the standard error envelope without
catching ``httpx.HTTPError`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass


class DbError(RuntimeError):
    """Raised when a DB provider returns an error or yields no results.

    Attributes:
        provider: Provider slug (``"rcsb"``, ``"uniprot"``, …).
        status_code: HTTP status from the upstream API, if applicable.
            ``None`` for non-HTTP failures (e.g. cache corruption,
            JSON shape mismatch).
        original: The underlying httpx / parse exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.original = original


@dataclass(frozen=True, slots=True)
class PdbEntry:
    """A protein structure record from RCSB or AlphaFold.

    Attributes:
        identifier: Provider-specific id (e.g. ``"1HSG"``, ``"AF-P00533-F1"``).
        title: Human-readable title.
        organism: Source organism, when known.
        resolution_angstrom: X-ray resolution; ``None`` for NMR / predicted.
        pdb_text: Full PDB block as text. Empty string when the provider
            returns only metadata.
    """

    identifier: str
    title: str
    organism: str | None
    resolution_angstrom: float | None
    pdb_text: str
