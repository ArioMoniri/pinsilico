#!/usr/bin/env python3
"""Generate the Tauri auto-updater ``latest.json`` manifest.

Reads the project version from a single source of truth
(``sidecar/pyproject.toml``) so the manifest version always matches
whatever ``release.py`` just tagged — no risk of the embedded version
in the Tauri build drifting from the manifest the updater fetches.

Scans a directory of artefacts (downloaded by ``release.yml`` from
all matrix jobs) for the Tauri-emitted updater bundles
(``.app.tar.gz``, ``.AppImage.tar.gz``, ``.msi.zip``) and their
sibling ``.sig`` files, then writes a single ``latest.json`` that
lists each platform's signed bundle URL.

Usage::

    python scripts/generate_latest_json.py \\
        --artefacts dist-artefacts/ \\
        --tag v1.0.0 \\
        --out latest.json

Format (Tauri 2.x updater spec):

.. code-block:: json

    {
      "version": "1.0.0",
      "notes": "See the GitHub Release for the full changelog.",
      "pub_date": "2026-05-20T12:00:00Z",
      "platforms": {
        "darwin-aarch64": {
          "signature": "<contents of the .app.tar.gz.sig file>",
          "url": "https://github.com/.../v1.0.0/PInSilico_1.0.0_aarch64.app.tar.gz"
        },
        ...
      }
    }

The ``platforms`` keys are exactly what the Tauri updater expects:

* ``darwin-aarch64`` — macOS Apple Silicon
* ``darwin-x86_64`` — macOS Intel
* ``linux-x86_64`` — Linux glibc
* ``windows-x86_64`` — Windows 64-bit
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "sidecar" / "pyproject.toml"

_REPO = "ArioMoniri/pinsilico"

# Map Tauri 2.x per-OS bundle filename suffixes to the platform key the
# updater plugin uses. Note: Tauri 2.x signs the installers directly —
# there is no .AppImage.tar.gz or .msi.zip wrapper anymore (those were
# Tauri 1.x). The macOS bundle keeps .app.tar.gz, and on a single-arch
# build the tauri-bundler omits the arch suffix (so "PInSilico.app.tar.gz"
# rather than "PInSilico_1.0.0_aarch64.app.tar.gz").
_PLATFORM_SUFFIXES: Final[dict[str, str]] = {
    ".app.tar.gz": "darwin-aarch64",
    "_amd64.AppImage": "linux-x86_64",
    "_x86_64.AppImage": "linux-x86_64",
    # MSI is the canonical Windows updater target; the NSIS _x64-setup.exe
    # is shipped as a separate download installer but not in latest.json
    # (Tauri's updater needs exactly one URL per platform).
    "_x64_en-US.msi": "windows-x86_64",
}


def read_version_from_pyproject() -> str:
    """Single source of truth — sidecar/pyproject.toml's ``version``.

    release.py already enforces six-way version sync before tagging,
    so any of the six would do; we pick pyproject because it has the
    simplest grammar to parse without an extra dep.
    """
    text = PYPROJECT.read_text("utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if match is None:
        msg = f"could not extract version from {PYPROJECT}"
        raise SystemExit(msg)
    return match.group(1)


def github_download_url(tag: str, filename: str) -> str:
    """The public URL the Tauri updater fetches each bundle from."""
    return f"https://github.com/{_REPO}/releases/download/{tag}/{filename}"


def discover_platforms(artefacts_dir: Path) -> dict[str, dict[str, str]]:
    """Walk the artefacts directory and build the platforms map.

    Each bundle must have a sibling ``.sig`` file (produced by
    tauri-build when ``TAURI_SIGNING_PRIVATE_KEY`` is set). Missing
    ``.sig`` files cause a warning + skip — better than a half-signed
    manifest the updater would reject silently.
    """
    platforms: dict[str, dict[str, str]] = {}
    for path in artefacts_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        # Pick the longest matching suffix so "_x64.app.tar.gz" wins
        # over a hypothetical shorter ".tar.gz" match.
        match = next(
            (
                (suffix, platform_key)
                for suffix, platform_key in sorted(
                    _PLATFORM_SUFFIXES.items(), key=lambda kv: -len(kv[0])
                )
                if name.endswith(suffix)
            ),
            None,
        )
        if match is None:
            continue
        _suffix, platform_key = match
        sig_path = path.with_suffix(path.suffix + ".sig")
        # Try the conventional ``<bundle>.sig`` first; some setups use
        # ``<bundle>.sig`` (no second extension) for tar.gz too.
        if not sig_path.exists():
            sig_path = path.parent / f"{path.name}.sig"
        if not sig_path.exists():
            sys.stderr.write(
                f"WARNING: skipping {name}: missing signature file at {sig_path}\n",
            )
            continue
        signature = sig_path.read_text("utf-8").strip()
        if platform_key in platforms:
            sys.stderr.write(
                f"WARNING: duplicate platform key {platform_key!r} "
                f"(was {platforms[platform_key]['url']}, now {name})\n",
            )
        platforms[platform_key] = {"signature": signature, "url": ""}  # url set below
        platforms[platform_key]["url"] = name  # fill in once tag known
    return platforms


def build_manifest(
    *,
    version: str,
    tag: str,
    notes: str,
    platforms: dict[str, dict[str, str]],
) -> dict[str, object]:
    """Assemble the final manifest dict ready for json.dump."""
    # Rewrite each url from a bare filename to the GitHub Release URL
    # the updater will fetch from.
    resolved: dict[str, dict[str, str]] = {}
    for key, entry in platforms.items():
        resolved[key] = {
            "signature": entry["signature"],
            "url": github_download_url(tag, entry["url"]),
        }
    return {
        "version": version,
        "notes": notes,
        "pub_date": _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": resolved,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artefacts",
        type=Path,
        required=True,
        help="Directory containing the downloaded matrix artefacts",
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Git tag for this release (e.g. v1.0.0). Used in download URLs.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "latest.json",
        help="Output path for the manifest (default: ./latest.json)",
    )
    parser.add_argument(
        "--notes",
        default="See the GitHub Release page for the full changelog.",
        help="Release notes blurb to embed in the manifest",
    )
    args = parser.parse_args(argv)

    version = read_version_from_pyproject()
    expected_tag = f"v{version}"
    if args.tag != expected_tag:
        sys.stderr.write(
            f"WARNING: tag {args.tag!r} doesn't match pyproject version "
            f"({expected_tag!r}). Continuing, but the updater compares manifest "
            "version against the running app's version — confirm release.py's "
            "pre-flight check passed before tagging.\n",
        )

    if not args.artefacts.exists():
        msg = f"artefacts directory not found: {args.artefacts}"
        raise SystemExit(msg)

    platforms = discover_platforms(args.artefacts)
    if not platforms:
        msg = (
            f"no Tauri updater artefacts found under {args.artefacts}. "
            "Confirm release.yml's matrix jobs ran with createUpdaterArtifacts=true "
            "and uploaded the resulting .app.tar.gz (mac) / .AppImage (linux) / "
            ".msi or _setup.exe (windows) + their .sig signatures."
        )
        raise SystemExit(msg)

    manifest = build_manifest(
        version=version,
        tag=args.tag,
        notes=args.notes,
        platforms=platforms,
    )
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"wrote {args.out} for {len(platforms)} platform(s): "
        f"{', '.join(sorted(platforms))}\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
