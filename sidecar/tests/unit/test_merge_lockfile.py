"""Tests for scripts/merge_lockfile_fragments.py."""

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
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "merge_lockfile_fragments.py"
    spec = importlib.util.spec_from_file_location("merge_lockfile_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["merge_lockfile_under_test"] = module
    spec.loader.exec_module(module)
    return module


merge_lockfile = _load_module()


def _base() -> dict[str, object]:
    return {
        "_comment": "base lockfile",
        "_ffmpeg_moved_to_pypi": {"_reason": "see media.py"},
        "binaries": {
            "smina": {
                "version": "2020-12-10",
                "platforms": {
                    "linux-x86_64": {
                        "url": "https://example/smina-linux",
                        "sha256": "0" * 64,
                    },
                    "macos-arm64": {
                        "url": "https://example/smina-mac",
                        "sha256": "abc" + "0" * 61,
                    },
                    "windows-x86_64": {
                        "url": "https://example/smina-win",
                        "sha256": "0" * 64,
                    },
                },
            },
            "vina": {
                "version": "1.2.5",
                "platforms": {
                    "macos-arm64": {"_source_build": True, "_reason": "no upstream binary"},
                },
            },
        },
    }


def _linux_fragment() -> dict[str, object]:
    return {
        "binaries": {
            "smina": {
                "version": "2020-12-10",
                "platforms": {
                    "linux-x86_64": {
                        "url": "https://example/smina-linux",
                        "sha256": "linux-sha" + "0" * 55,
                    },
                },
            },
        },
    }


def _windows_fragment() -> dict[str, object]:
    return {
        "binaries": {
            "smina": {
                "version": "2020-12-10",
                "platforms": {
                    "windows-x86_64": {
                        "url": "https://example/smina-win",
                        "sha256": "win-sha" + "0" * 57,
                    },
                },
            },
        },
    }


class TestParseFragmentArg:
    def test_splits_on_first_equals(self) -> None:
        key, path = merge_lockfile.parse_fragment_arg("linux-x86_64=fragments/lockfile.json")
        assert key == "linux-x86_64"
        assert path == Path("fragments/lockfile.json")

    def test_rejects_missing_equals(self) -> None:
        with pytest.raises(SystemExit, match="--fragment expects"):
            merge_lockfile.parse_fragment_arg("linux-x86_64")


class TestMerge:
    def test_applies_linux_fragment_only_to_linux_platform(self) -> None:
        base = _base()
        out = merge_lockfile.merge(base, {"linux-x86_64": _linux_fragment()})
        assert out["binaries"]["smina"]["platforms"]["linux-x86_64"]["sha256"].startswith(
            "linux-sha"
        )
        # macOS unchanged
        assert out["binaries"]["smina"]["platforms"]["macos-arm64"]["sha256"].startswith("abc")
        # Windows unchanged (still sentinel)
        assert out["binaries"]["smina"]["platforms"]["windows-x86_64"]["sha256"] == "0" * 64

    def test_combines_linux_and_windows_fragments(self) -> None:
        base = _base()
        out = merge_lockfile.merge(
            base,
            {
                "linux-x86_64": _linux_fragment(),
                "windows-x86_64": _windows_fragment(),
            },
        )
        smina = out["binaries"]["smina"]["platforms"]
        assert smina["linux-x86_64"]["sha256"].startswith("linux-sha")
        assert smina["windows-x86_64"]["sha256"].startswith("win-sha")

    def test_preserves_top_level_metadata(self) -> None:
        base = _base()
        out = merge_lockfile.merge(base, {"linux-x86_64": _linux_fragment()})
        assert out["_comment"] == "base lockfile"
        assert "_ffmpeg_moved_to_pypi" in out

    def test_preserves_source_build_entries(self) -> None:
        base = _base()
        out = merge_lockfile.merge(base, {"linux-x86_64": _linux_fragment()})
        vina_mac = out["binaries"]["vina"]["platforms"]["macos-arm64"]
        assert vina_mac.get("_source_build") is True
        # No SHA was assigned to a source-build entry by accident.
        assert "sha256" not in vina_mac

    def test_ignores_metadata_only_top_level_entries(self) -> None:
        """Fragments containing a `_*` top-level entry shouldn't break the merge."""
        base = _base()
        linux_binaries = _linux_fragment()["binaries"]
        assert isinstance(linux_binaries, dict)
        fragment_with_meta = {
            "binaries": {
                "_some_metadata": {"_reason": "irrelevant"},
                "smina": linux_binaries["smina"],
            },
        }
        out = merge_lockfile.merge(base, {"linux-x86_64": fragment_with_meta})
        # The metadata is ignored (didn't crash, didn't get copied).
        assert out["binaries"]["smina"]["platforms"]["linux-x86_64"]["sha256"].startswith(
            "linux-sha"
        )

    def test_no_fragments_returns_base_copy(self) -> None:
        base = _base()
        out = merge_lockfile.merge(base, {})
        assert out == base
        assert out is not base  # deep-copied


class TestMain:
    def test_writes_merged_file(self, tmp_path: Path) -> None:
        base_path = tmp_path / "base.json"
        base_path.write_text(json.dumps(_base()))
        linux_path = tmp_path / "linux.json"
        linux_path.write_text(json.dumps(_linux_fragment()))
        out_path = tmp_path / "out.json"

        rc = merge_lockfile.main(
            [
                "--base",
                str(base_path),
                "--fragment",
                f"linux-x86_64={linux_path}",
                "--out",
                str(out_path),
            ]
        )
        assert rc == 0
        data = json.loads(out_path.read_text())
        assert data["binaries"]["smina"]["platforms"]["linux-x86_64"]["sha256"].startswith(
            "linux-sha"
        )

    def test_aborts_when_base_missing(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="lockfile not found"):
            merge_lockfile.main(
                ["--base", str(tmp_path / "nope.json"), "--out", str(tmp_path / "o.json")]
            )
