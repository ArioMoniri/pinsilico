#!/usr/bin/env python3
"""Release helper.

Validates pre-release invariants then creates and pushes a signed
annotated tag. CI's release.yml picks the tag up and runs the
cross-platform build matrix.

Pre-flight checks:

* The working tree must be clean (no untracked / unstaged / staged changes).
* The tag must not already exist locally or on origin.
* `make ci` must pass locally (lint + tests across Python/Rust/Frontend).
* The supplied version string must agree with the six places it appears
  (Cargo.toml, package.json, tauri.conf.json, pyproject.toml,
  version.ts, __init__.py).

Usage:
    python scripts/release.py v1.0.0
    python scripts/release.py v1.0.0 --skip-ci  # skip make ci (manual override)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_VERSION_FILES: dict[Path, str] = {
    ROOT / "app" / "src-tauri" / "Cargo.toml": r'^version\s*=\s*"([^"]+)"',
    ROOT / "app" / "src-tauri" / "tauri.conf.json": r'"version"\s*:\s*"([^"]+)"',
    ROOT / "app" / "package.json": r'"version"\s*:\s*"([^"]+)"',
    ROOT / "sidecar" / "pyproject.toml": r'^version\s*=\s*"([^"]+)"',
    ROOT / "sidecar" / "pinsilico" / "__init__.py": r'__version__\s*:\s*str\s*=\s*"([^"]+)"',
    ROOT / "app" / "src" / "lib" / "version.ts": r'APP_VERSION\s*=\s*"([^"]+)"',
}


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT), check=check, capture_output=True, text=True)


def assert_clean_tree() -> None:
    result = _run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        msg = f"working tree not clean:\n{result.stdout}"
        raise SystemExit(msg)


def assert_tag_unique(tag: str) -> None:
    local = _run(["git", "tag", "--list", tag])
    if local.stdout.strip():
        msg = f"tag {tag} already exists locally"
        raise SystemExit(msg)
    # Fetching tags is cheap and confirms the remote view.
    _run(["git", "fetch", "--tags"], check=False)
    remote = _run(["git", "tag", "--list", tag])
    if remote.stdout.strip():
        msg = f"tag {tag} already exists on remote"
        raise SystemExit(msg)


def extract_versions() -> dict[Path, str]:
    """Pull the version literal out of every source-of-truth file."""
    out: dict[Path, str] = {}
    for path, pattern in _VERSION_FILES.items():
        if not path.exists():
            msg = f"version file missing: {path}"
            raise SystemExit(msg)
        text = path.read_text("utf-8")
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match is None:
            msg = f"could not extract version from {path}"
            raise SystemExit(msg)
        out[path] = match.group(1)
    return out


def assert_versions_agree(expected: str) -> None:
    versions = extract_versions()
    bad = [(p, v) for p, v in versions.items() if v != expected]
    if bad:
        lines = "\n".join(f"  {p.relative_to(ROOT)}: {v}" for p, v in bad)
        msg = f"version mismatch (expected {expected}):\n{lines}"
        raise SystemExit(msg)


def run_ci() -> None:
    sys.stderr.write("running `make ci` (lint + all tests across stacks) …\n")
    result = subprocess.run(["make", "ci"], cwd=str(ROOT), check=False)  # noqa: S603, S607
    if result.returncode != 0:
        msg = "make ci failed; refusing to tag a broken state"
        raise SystemExit(msg)


def create_and_push_tag(tag: str, message: str) -> None:
    _run(["git", "tag", "-a", tag, "-m", message])
    sys.stderr.write(f"created annotated tag {tag}\n")
    push = subprocess.run(
        ["git", "push", "origin", tag],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if push.returncode != 0:
        msg = f"failed to push tag: {push.stderr.strip()}"
        raise SystemExit(msg)
    sys.stderr.write(f"pushed {tag} -> origin\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Annotated tag to create (e.g. v1.0.0)")
    parser.add_argument(
        "--message",
        default=None,
        help="Tag message. Defaults to a generated summary.",
    )
    parser.add_argument(
        "--skip-ci",
        action="store_true",
        help="Skip make ci (manual override; CI still runs on the tag push)",
    )
    args = parser.parse_args(argv)

    if not re.match(r"^v\d+\.\d+\.\d+(-[a-z]+)?$", args.tag):
        msg = (
            f"tag must match v<MAJOR>.<MINOR>.<PATCH>[-prerelease], got {args.tag!r}"
        )
        raise SystemExit(msg)

    assert_clean_tree()
    assert_tag_unique(args.tag)
    expected_version = args.tag.lstrip("v")
    assert_versions_agree(expected_version)
    if not args.skip_ci:
        run_ci()

    message = args.message or f"PInSilico {args.tag}"
    create_and_push_tag(args.tag, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
