#!/usr/bin/env python3
"""Merge per-OS ``binaries.lock.json`` fragments into a single canonical lockfile.

The ``update-binaries-lock`` workflow runs ``fetch_binaries.py --update``
on each OS matrix job, then uploads that runner's modified lockfile as
an artefact. This helper combines them into one definitive copy that
the PR job commits back.

Merge rule: for every binary, each platform key is taken from the
matching OS fragment. Entries with no fragment (e.g. obabel only has
``linux-x86_64`` in the lock) are preserved from the source-of-truth
fragment passed via ``--base``. Top-level metadata keys (``_comment``,
``_ffmpeg_moved_to_pypi``, etc.) come from ``--base``.

Usage::

    python scripts/merge_lockfile_fragments.py \\
        --base scripts/binaries.lock.json \\
        --fragment linux-x86_64=artefacts/linux/binaries.lock.json \\
        --fragment windows-x86_64=artefacts/windows/binaries.lock.json \\
        --out scripts/binaries.lock.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_fragment_arg(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        msg = f"--fragment expects PLATFORM_KEY=PATH, got {raw!r}"
        raise SystemExit(msg)
    platform_key, path_str = raw.split("=", 1)
    return platform_key.strip(), Path(path_str.strip())


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        msg = f"lockfile not found: {path}"
        raise SystemExit(msg)
    return json.loads(path.read_text("utf-8"))


def merge(base: dict[str, Any], fragments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return a new lockfile with each fragment's platform applied on top of base.

    Only the platform key matching the fragment's OS is taken; everything
    else (other platforms, ``version``, top-level metadata) is preserved
    from ``base``. This means a workflow can run independently per-OS
    without overwriting any other OS's entries.
    """
    result = json.loads(json.dumps(base))  # deep-copy via JSON round-trip
    for platform_key, fragment in fragments.items():
        for name, entry in fragment.get("binaries", {}).items():
            if name.startswith("_"):
                continue
            plats = entry.get("platforms", {})
            new_info = plats.get(platform_key)
            if new_info is None:
                continue
            target_entry = result["binaries"].setdefault(name, dict(entry))
            target_platforms = target_entry.setdefault("platforms", {})
            target_platforms[platform_key] = new_info
            # Preserve version if the fragment carries a different one
            # (e.g. an upstream release bump).
            if "version" in entry and entry["version"] != target_entry.get("version"):
                sys.stderr.write(
                    f"NOTE: {name} version on {platform_key} is {entry['version']!r} "
                    f"vs base {target_entry.get('version')!r}. "
                    "Taking the fragment's value.\n",
                )
                target_entry["version"] = entry["version"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="Canonical lockfile path")
    parser.add_argument(
        "--fragment",
        action="append",
        default=[],
        help="PLATFORM_KEY=PATH (repeatable)",
    )
    parser.add_argument("--out", type=Path, required=True, help="Where to write merged lockfile")
    args = parser.parse_args(argv)

    base = load(args.base)
    fragments: dict[str, dict[str, Any]] = {}
    for raw in args.fragment:
        platform_key, path = parse_fragment_arg(raw)
        fragments[platform_key] = load(path)

    merged = merge(base, fragments)
    args.out.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"wrote merged lockfile to {args.out} "
        f"(fragments: {', '.join(sorted(fragments)) or 'none'})\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
