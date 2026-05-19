"""Database clients for external chemistry sources.

Six providers, all behind the same :class:`DbClient` Protocol so the
Phase 5 route layer can dispatch by provider name without caring whether
the data comes from RCSB, UniProt, AlphaFold, ChEMBL, PubChem, or the
bundled DrugBank CSV.

Network calls are opt-in: the sidecar only fetches when a user clicks a
search button in the UI. Every fetch is cached with ``requests-cache``
under ``~/.pinsilico/cache/db/`` (7-day default TTL, overridable per
call).
"""

from __future__ import annotations

__all__: list[str] = []
