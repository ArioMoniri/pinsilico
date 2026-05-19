"""HTTP route modules.

Phase 5 exposes the Phase 2-4 adapters over FastAPI. Each module owns
one ``APIRouter`` and is mounted via :func:`register_all` from
:mod:`pinsilico.server`.

* :mod:`pinsilico.routes.db` — `/db/{provider}/...` (Phase 2 wrappers)
* :mod:`pinsilico.routes.pocket` — `/pocket/detect`
* :mod:`pinsilico.routes.docking` — `/docking/dock`, `/docking/jobs/{id}`
* :mod:`pinsilico.routes.sim` — `/sim/run` (SSE), `/sim/fast_forward`

Auth gating is applied to every router except `/health` (the only
unauthenticated endpoint) via the verifier dependency set up in
:func:`pinsilico.server.create_app`.
"""

from __future__ import annotations

__all__: list[str] = []
