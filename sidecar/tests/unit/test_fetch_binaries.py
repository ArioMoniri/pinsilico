"""Tests for scripts/fetch_binaries.py.

Loads the script as a module via importlib so the tests run without
modifying sys.path globally.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType


def _load_module() -> ModuleType:
    """Load scripts/fetch_binaries.py as a module."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "fetch_binaries.py"
    spec = importlib.util.spec_from_file_location("fetch_binaries_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fetch_binaries_under_test"] = module
    spec.loader.exec_module(module)
    return module


fetch_binaries = _load_module()


class TestDetectPlatform:
    def test_returns_known_key(self) -> None:
        key = fetch_binaries.detect_platform()
        assert key in {"linux-x86_64", "macos-arm64", "windows-x86_64"}


class TestSpecsFor:
    def test_filters_by_platform(self) -> None:
        lock = {
            "binaries": {
                "smina": {
                    "version": "1.0",
                    "platforms": {
                        "linux-x86_64": {"url": "u1", "sha256": "a" * 64},
                        "macos-arm64": {"url": "u2", "sha256": "b" * 64},
                    },
                },
            },
        }
        specs = fetch_binaries.specs_for("macos-arm64", lock)
        assert len(specs) == 1
        assert specs[0].sha256 == "b" * 64

    def test_skips_unknown_platform(self) -> None:
        lock = {
            "binaries": {
                "smina": {
                    "version": "1.0",
                    "platforms": {"linux-x86_64": {"url": "u1", "sha256": "a" * 64}},
                },
            },
        }
        specs = fetch_binaries.specs_for("macos-arm64", lock)
        assert specs == []


class TestFetch:
    def test_aborts_on_unpopulated_sha(self, tmp_path: Path) -> None:
        spec = fetch_binaries.BinarySpec(
            name="dummy",
            version="0.0.0",
            url="https://example.invalid/x",
            sha256="0" * 64,
        )
        with pytest.raises(SystemExit, match="unpopulated SHA256"):
            fetch_binaries.fetch(spec, dest_dir=tmp_path)

    def test_skips_redownload_when_existing_hash_matches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        existing = tmp_path / "dummy"
        existing.write_bytes(b"hello-world")
        expected = hashlib.sha256(b"hello-world").hexdigest()
        spec = fetch_binaries.BinarySpec(
            name="dummy",
            version="0.0.0",
            url="https://example.invalid/x",
            sha256=expected,
        )

        def fail_download(*_args: object, **_kw: object) -> None:
            raise AssertionError("should not download when checksum already matches")

        monkeypatch.setattr(fetch_binaries, "_download", fail_download)
        out = fetch_binaries.fetch(spec, dest_dir=tmp_path)
        assert out == existing

    def test_aborts_on_checksum_mismatch_and_removes_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "dummy"

        def fake_download(url: str, dest: Path) -> None:
            assert url == "https://example.invalid/x"
            dest.write_bytes(b"wrong-content")

        monkeypatch.setattr(fetch_binaries, "_download", fake_download)
        spec = fetch_binaries.BinarySpec(
            name="dummy",
            version="0.0.0",
            url="https://example.invalid/x",
            sha256=hashlib.sha256(b"expected-content").hexdigest(),
        )
        with pytest.raises(SystemExit, match="checksum mismatch"):
            fetch_binaries.fetch(spec, dest_dir=tmp_path)
        assert not target.exists()


class TestVerifyOnly:
    def test_returns_1_on_unpopulated_sha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lock = {
            "binaries": {
                "dummy": {
                    "version": "0.0.0",
                    "platforms": {
                        "linux-x86_64": {
                            "url": "https://example.invalid/x",
                            "sha256": "0" * 64,
                        },
                    },
                },
            },
        }
        lock_path = tmp_path / "lock.json"
        lock_path.write_text(json.dumps(lock))
        monkeypatch.setattr(fetch_binaries, "LOCK_PATH", lock_path)
        monkeypatch.setattr(fetch_binaries, "DEST_DIR", tmp_path / "binaries")
        rc = fetch_binaries.verify_only("linux-x86_64")
        assert rc == 1

    def test_returns_0_when_all_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        content = b"binary-bytes"
        bin_dir = tmp_path / "binaries"
        bin_dir.mkdir()
        (bin_dir / "dummy").write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        lock = {
            "binaries": {
                "dummy": {
                    "version": "0.0.0",
                    "platforms": {
                        "linux-x86_64": {
                            "url": "https://example.invalid/x",
                            "sha256": digest,
                        },
                    },
                },
            },
        }
        lock_path = tmp_path / "lock.json"
        lock_path.write_text(json.dumps(lock))
        monkeypatch.setattr(fetch_binaries, "LOCK_PATH", lock_path)
        monkeypatch.setattr(fetch_binaries, "DEST_DIR", bin_dir)
        rc = fetch_binaries.verify_only("linux-x86_64")
        assert rc == 0
