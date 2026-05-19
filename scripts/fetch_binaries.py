#!/usr/bin/env python3
"""Fetch every native binary the installer ships and verify SHA256.

Usage:
    # Default — fetch every binary into sidecar/resources/binaries/ for
    # the current platform, refusing to proceed on a checksum mismatch.
    python scripts/fetch_binaries.py

    # Update the lockfile by computing checksums of upstream URLs.
    # Run after upstream releases bump versions; commit the diff.
    python scripts/fetch_binaries.py --update

    # Verify-only — fail if any binary is missing or its checksum is wrong.
    python scripts/fetch_binaries.py --verify

BUILD_PROMPT.md §12 calls this script "checksum-pinned" and requires it
to abort on a mismatch. The lock file (`scripts/binaries.lock.json`)
is the authoritative source; CI's release.yml verifies it on every
tag push.

This file is platform-aware: it picks the right URL for the current
host (linux-x86_64, macos-arm64, windows-x86_64). Cross-platform
builds run this script three times in their respective matrix jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "scripts" / "binaries.lock.json"
DEST_DIR = ROOT / "sidecar" / "resources" / "binaries"

# 64 zero hex chars marks the "release not yet populated" sentinel in
# the lockfile. fetch_binaries.py never trusts these — it errors loud.
_UNPOPULATED_SHA = "0" * 64


@dataclass(frozen=True, slots=True)
class BinarySpec:
    name: str
    version: str
    url: str
    sha256: str


def detect_platform() -> str:
    """Map (platform.system(), platform.machine()) to our lock keys."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x86_64"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        # macOS Intel currently uses the arm64 build via Rosetta until we
        # add an explicit x86_64 lock entry.
        return "macos-arm64"
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x86_64"
    msg = f"unsupported platform: {system}/{machine}"
    raise SystemExit(msg)


def load_lock() -> dict[str, Any]:
    if not LOCK_PATH.exists():
        msg = f"lock file missing: {LOCK_PATH}"
        raise SystemExit(msg)
    return json.loads(LOCK_PATH.read_text("utf-8"))


def specs_for(platform_key: str, lock: dict[str, Any]) -> list[BinarySpec]:
    out: list[BinarySpec] = []
    for name, entry in lock["binaries"].items():
        plats = entry.get("platforms", {})
        info = plats.get(platform_key)
        if info is None:
            continue
        out.append(
            BinarySpec(
                name=name,
                version=entry["version"],
                url=info["url"],
                sha256=info["sha256"].lower(),
            ),
        )
    return out


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # nosec B310: URLs come from the version-controlled lockfile only.
    with urllib.request.urlopen(url) as src:  # noqa: S310
        dest.write_bytes(src.read())


def fetch(spec: BinarySpec, *, dest_dir: Path) -> Path:
    """Download `spec` into `dest_dir/<name>` and verify SHA256."""
    if spec.sha256 == _UNPOPULATED_SHA:
        msg = (
            f"{spec.name} ({spec.version}) has an unpopulated SHA256 in the lock file. "
            "Run `python scripts/fetch_binaries.py --update` to populate it against the real "
            "release, then commit the diff."
        )
        raise SystemExit(msg)
    target = dest_dir / spec.name
    if target.exists():
        existing = _sha256_of_file(target)
        if existing == spec.sha256:
            return target
        target.unlink()
    _download(spec.url, target)
    got = _sha256_of_file(target)
    if got != spec.sha256:
        target.unlink(missing_ok=True)
        msg = (
            f"checksum mismatch for {spec.name} ({spec.version}):\n"
            f"  expected: {spec.sha256}\n"
            f"  got:      {got}\n"
            f"  url:      {spec.url}"
        )
        raise SystemExit(msg)
    return target


def update_lock(platform_key: str) -> None:
    """Compute fresh SHA256s for every URL and rewrite the lock file."""
    lock = load_lock()
    for name, entry in lock["binaries"].items():
        plats = entry.get("platforms", {})
        info = plats.get(platform_key)
        if info is None:
            continue
        url = info["url"]
        sys.stderr.write(f"updating {name} on {platform_key} from {url}\n")
        tmp = DEST_DIR / f".update.{name}"
        try:
            _download(url, tmp)
            info["sha256"] = _sha256_of_file(tmp)
            info.pop("_pending", None)
        finally:
            tmp.unlink(missing_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_only(platform_key: str) -> int:
    """Walk the lock for the current platform; fail on any missing/wrong file."""
    lock = load_lock()
    specs = specs_for(platform_key, lock)
    missing: list[str] = []
    mismatched: list[str] = []
    for spec in specs:
        target = DEST_DIR / spec.name
        if spec.sha256 == _UNPOPULATED_SHA:
            missing.append(f"{spec.name}: SHA256 not yet populated in lockfile")
            continue
        if not target.exists():
            missing.append(f"{spec.name}: file not present at {target}")
            continue
        got = _sha256_of_file(target)
        if got != spec.sha256:
            mismatched.append(f"{spec.name}: expected {spec.sha256}, got {got}")
    if missing or mismatched:
        for line in missing + mismatched:
            sys.stderr.write(f"  FAIL  {line}\n")
        return 1
    sys.stdout.write(f"ok — all {len(specs)} binaries verified for {platform_key}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Update the lock file SHA256s")
    parser.add_argument("--verify", action="store_true", help="Verify only; don't fetch")
    parser.add_argument(
        "--platform",
        default=None,
        help="Override platform detection (linux-x86_64 / macos-arm64 / windows-x86_64)",
    )
    args = parser.parse_args(argv)

    platform_key = args.platform or detect_platform()
    if args.update:
        update_lock(platform_key)
        return 0
    if args.verify:
        return verify_only(platform_key)

    lock = load_lock()
    specs = specs_for(platform_key, lock)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        path = fetch(spec, dest_dir=DEST_DIR)
        sys.stdout.write(f"fetched {spec.name} ({spec.version}) -> {path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
