"""Locator for the bundled ffmpeg binary.

Phase 12 ditched the binary-lockfile path for ffmpeg in favour of the
``imageio-ffmpeg`` PyPI wheel, which ships a pre-built ffmpeg in every
wheel for Linux / macOS-intel / macOS-arm64 / Windows. This means:

* No per-OS lockfile entry to maintain.
* No URL-rot risk (evermeet.cx and gyan.dev timed out during the first
  ``--update`` run on macOS arm64).
* ``pip install -e ".[dev]"`` covers ffmpeg on every developer's machine
  with no extra steps.

The Phase 4 ``sim.exporter`` MP4 path calls :func:`ffmpeg_exe` instead
of hard-coding ``ffmpeg``-on-PATH; the PyInstaller bundle then carries
the wheel-shipped binary into the final installer.
"""

from __future__ import annotations

import importlib.metadata as _importlib_metadata
from functools import lru_cache
from pathlib import Path

try:
    from imageio_ffmpeg import get_ffmpeg_exe as _get_ffmpeg_exe
except ImportError:  # pragma: no cover - covered by patched-out-import test
    _get_ffmpeg_exe = None


class FfmpegUnavailableError(RuntimeError):
    """Raised when imageio-ffmpeg can't locate a usable ffmpeg binary."""


@lru_cache(maxsize=1)
def ffmpeg_exe() -> Path:
    """Return the absolute path to the bundled ffmpeg executable.

    Raises :class:`FfmpegUnavailableError` when imageio-ffmpeg isn't
    installed (which only happens if someone messed with the venv —
    ``imageio-ffmpeg`` is a runtime dep of the sidecar) or its
    discovery function returns no binary.
    """
    if _get_ffmpeg_exe is None:
        msg = (
            "imageio-ffmpeg is required at runtime. Install with "
            "`pip install imageio-ffmpeg` or reinstall the sidecar dev "
            'extras (`pip install -e ".[dev]"`).'
        )
        raise FfmpegUnavailableError(msg)
    path = Path(_get_ffmpeg_exe())
    if not path.exists():
        msg = f"imageio-ffmpeg reports ffmpeg at {path} but the file is missing"
        raise FfmpegUnavailableError(msg)
    return path


def ffmpeg_version() -> str:
    """Return the version of the bundled ffmpeg (best-effort).

    Pulls from imageio-ffmpeg's package version rather than shelling out
    to ``ffmpeg -version`` — that's the version the wheel publishes and
    it's stable across calls.
    """
    try:
        return _importlib_metadata.version("imageio-ffmpeg")
    except _importlib_metadata.PackageNotFoundError:
        return "0.0.0"
