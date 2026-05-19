"""Pocket detection.

Phase 3 ships :mod:`pinsilico.pocket.fpocket` — a thin adapter around
the bundled ``fpocket`` binary (Phase 12 packaging downloads the static
release into ``sidecar/resources/binaries/fpocket``).

The Phase 4 simulation engine places binding sites at the
:class:`Pocket.centroid_xyz` returned by the detector; the Phase 3
docking adapters use the same coords as their docking-box centre.
"""

from __future__ import annotations

__all__: list[str] = []
