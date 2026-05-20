"""Tests for the ffmpeg locator.

Cross-platform ffmpeg ships via the imageio-ffmpeg PyPI wheel
(Phase 12 design choice — see docs/releasing.md). The wheel embeds
a pre-built ffmpeg for every OS Tauri targets, replacing the
per-OS download-and-checksum path that timed out on macOS arm64.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pinsilico.io import media
from pinsilico.io.media import FfmpegUnavailableError, ffmpeg_exe, ffmpeg_version


class TestFfmpegExe:
    def test_returns_an_existing_path(self) -> None:
        """The bundled binary should exist after `pip install` runs."""
        ffmpeg_exe.cache_clear()
        path = ffmpeg_exe()
        assert isinstance(path, Path)
        assert path.exists()
        assert "imageio_ffmpeg" in str(path)

    def test_cached_after_first_call(self) -> None:
        ffmpeg_exe.cache_clear()
        a = ffmpeg_exe()
        b = ffmpeg_exe()
        assert a is b

    def test_raises_when_imageio_ffmpeg_uninstalled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ffmpeg_exe.cache_clear()
        monkeypatch.setattr(media, "_get_ffmpeg_exe", None)
        with pytest.raises(FfmpegUnavailableError, match="imageio-ffmpeg"):
            ffmpeg_exe()

    def test_raises_when_returned_path_is_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ffmpeg_exe.cache_clear()
        bogus = tmp_path / "no-such-ffmpeg"
        monkeypatch.setattr(media, "_get_ffmpeg_exe", lambda: str(bogus))
        with pytest.raises(FfmpegUnavailableError, match="missing"):
            ffmpeg_exe()


class TestFfmpegVersion:
    def test_returns_a_version_string(self) -> None:
        version = ffmpeg_version()
        assert isinstance(version, str)
        assert version
        assert version != "0.0.0"
