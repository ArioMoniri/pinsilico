"""Tests for scripts/generate_latest_json.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "generate_latest_json.py"
    spec = importlib.util.spec_from_file_location("genlatest_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["genlatest_under_test"] = module
    spec.loader.exec_module(module)
    return module


genlatest = _load_module()


class TestReadVersionFromPyproject:
    def test_returns_a_semver_string(self) -> None:
        version = genlatest.read_version_from_pyproject()
        assert isinstance(version, str)
        assert version.count(".") >= 2


class TestGithubDownloadUrl:
    def test_builds_release_url(self) -> None:
        url = genlatest.github_download_url("v1.0.0", "PInSilico_1.0.0_aarch64.app.tar.gz")
        assert "github.com/ArioMoniri/pinsilico" in url
        assert "v1.0.0" in url
        assert "PInSilico_1.0.0_aarch64.app.tar.gz" in url


class TestDiscoverPlatforms:
    def _fake_artefact(self, dir: Path, name: str, sig: str = "fake-signature") -> None:
        artefact = dir / name
        artefact.write_bytes(b"fake bundle")
        (dir / f"{name}.sig").write_text(sig)

    def test_picks_up_macos_arm64(self, tmp_path: Path) -> None:
        self._fake_artefact(tmp_path, "PInSilico_1.0.0_aarch64.app.tar.gz", sig="sig-arm64")
        platforms = genlatest.discover_platforms(tmp_path)
        assert "darwin-aarch64" in platforms
        assert platforms["darwin-aarch64"]["signature"] == "sig-arm64"

    def test_picks_up_linux(self, tmp_path: Path) -> None:
        self._fake_artefact(tmp_path, "pinsilico_1.0.0_amd64.AppImage.tar.gz", sig="sig-linux")
        platforms = genlatest.discover_platforms(tmp_path)
        assert "linux-x86_64" in platforms

    def test_picks_up_windows(self, tmp_path: Path) -> None:
        self._fake_artefact(tmp_path, "PInSilico_1.0.0_x64-setup.nsis.zip", sig="sig-win")
        platforms = genlatest.discover_platforms(tmp_path)
        assert "windows-x86_64" in platforms

    def test_skips_artefacts_without_sig(self, tmp_path: Path) -> None:
        (tmp_path / "PInSilico_1.0.0_aarch64.app.tar.gz").write_bytes(b"x")
        platforms = genlatest.discover_platforms(tmp_path)
        assert platforms == {}

    def test_ignores_non_updater_files(self, tmp_path: Path) -> None:
        (tmp_path / "PInSilico_1.0.0.dmg").write_bytes(b"x")
        (tmp_path / "PInSilico_1.0.0.dmg.sig").write_text("sig")
        platforms = genlatest.discover_platforms(tmp_path)
        assert platforms == {}

    def test_picks_up_multiple_platforms(self, tmp_path: Path) -> None:
        self._fake_artefact(tmp_path, "PInSilico_1.0.0_aarch64.app.tar.gz")
        self._fake_artefact(tmp_path, "pinsilico_1.0.0_amd64.AppImage.tar.gz")
        self._fake_artefact(tmp_path, "PInSilico_1.0.0_x64-setup.nsis.zip")
        platforms = genlatest.discover_platforms(tmp_path)
        assert set(platforms) == {"darwin-aarch64", "linux-x86_64", "windows-x86_64"}


class TestBuildManifest:
    def test_emits_full_shape(self) -> None:
        manifest = genlatest.build_manifest(
            version="1.0.0",
            tag="v1.0.0",
            notes="bugfixes",
            platforms={
                "darwin-aarch64": {
                    "signature": "sig-arm64",
                    "url": "PInSilico_1.0.0_aarch64.app.tar.gz",
                },
            },
        )
        assert manifest["version"] == "1.0.0"
        assert manifest["notes"] == "bugfixes"
        assert "pub_date" in manifest
        assert manifest["platforms"]["darwin-aarch64"]["signature"] == "sig-arm64"
        assert manifest["platforms"]["darwin-aarch64"]["url"].startswith(
            "https://github.com/ArioMoniri/pinsilico/releases/download/v1.0.0/",
        )


class TestMain:
    def test_writes_manifest_to_file(self, tmp_path: Path) -> None:
        artefacts = tmp_path / "art"
        artefacts.mkdir()
        (artefacts / "PInSilico_1.0.0_aarch64.app.tar.gz").write_bytes(b"x")
        (artefacts / "PInSilico_1.0.0_aarch64.app.tar.gz.sig").write_text("sig")
        out = tmp_path / "latest.json"

        # Override the version source so the test is self-contained.
        version = genlatest.read_version_from_pyproject()
        rc = genlatest.main(
            ["--artefacts", str(artefacts), "--tag", f"v{version}", "--out", str(out)]
        )
        assert rc == 0
        data = json.loads(out.read_text())
        assert "darwin-aarch64" in data["platforms"]
        assert data["version"] == version

    def test_aborts_when_no_artefacts(self, tmp_path: Path) -> None:
        artefacts = tmp_path / "art"
        artefacts.mkdir()
        out = tmp_path / "latest.json"
        with pytest.raises(SystemExit, match="no Tauri updater artefacts"):
            genlatest.main(
                ["--artefacts", str(artefacts), "--tag", "v1.0.0", "--out", str(out)]
            )
