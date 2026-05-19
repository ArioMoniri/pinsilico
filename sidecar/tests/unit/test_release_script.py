"""Tests for scripts/release.py.

Loads the script as a module so the version-sync extractor and the
tag-format validator are testable without actually creating tags.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("release_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_under_test"] = module
    spec.loader.exec_module(module)
    return module


release = _load_module()


class TestExtractVersions:
    def test_picks_up_every_source_of_truth(self) -> None:
        versions = release.extract_versions()
        # Every file should have been read and a version string extracted.
        assert len(versions) == 6
        # All six should agree at the current HEAD.
        unique = set(versions.values())
        assert len(unique) == 1, f"version mismatch at HEAD: {versions}"


class TestAssertVersionsAgree:
    def test_passes_when_all_match(self) -> None:
        versions = release.extract_versions()
        current = next(iter(versions.values()))
        # Should not raise.
        release.assert_versions_agree(current)

    def test_raises_on_mismatch(self) -> None:
        with pytest.raises(SystemExit, match="version mismatch"):
            release.assert_versions_agree("99.99.99")


class TestTagFormat:
    @pytest.mark.parametrize(
        "tag",
        ["1.0.0", "v1", "v1.0", "vX.Y.Z", "v1.0.0-bad ext"],
    )
    def test_rejects_bad_tags(self, tag: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(release, "assert_clean_tree", lambda: None)
        monkeypatch.setattr(release, "assert_tag_unique", lambda _t: None)
        monkeypatch.setattr(release, "assert_versions_agree", lambda _v: None)
        monkeypatch.setattr(release, "run_ci", lambda: None)
        monkeypatch.setattr(release, "create_and_push_tag", lambda _t, _m: None)
        with pytest.raises(SystemExit, match="tag must match"):
            release.main([tag])

    @pytest.mark.parametrize(
        "tag",
        ["v0.0.0", "v1.0.0", "v0.0.0-alpha", "v123.456.789", "v1.0.0-beta"],
    )
    def test_accepts_valid_tags(self, tag: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(release, "assert_clean_tree", lambda: None)
        monkeypatch.setattr(release, "assert_tag_unique", lambda _t: None)
        monkeypatch.setattr(release, "assert_versions_agree", lambda _v: None)
        monkeypatch.setattr(release, "run_ci", lambda: None)
        called: list[tuple[str, str]] = []
        monkeypatch.setattr(
            release,
            "create_and_push_tag",
            lambda t, m: called.append((t, m)),
        )
        assert release.main([tag, "--skip-ci"]) == 0
        assert called
        assert called[0][0] == tag
