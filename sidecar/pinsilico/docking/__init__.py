"""Docking engines.

Phase 3 ships Smina (default) and AutoDock Vina. DiffDock and Boltz-2 land
behind explicit "download extra engines" gates (BUILD_PROMPT.md §3) — both
weights are too large to bundle. The :mod:`pinsilico.docking.base` Protocol
keeps the dispatch surface uniform so Phase 5 routes can pick an engine by
name.
"""

from __future__ import annotations

__all__: list[str] = []
