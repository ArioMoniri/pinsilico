#!/usr/bin/env python3
"""PyInstaller invocation for the Python sidecar.

Phase 12 packaging step: bundle the sidecar into a single-file binary
named ``pinsilico-sidecar-<target-triple>`` under
``app/src-tauri/binaries/``. Tauri picks that name up via the
``externalBin`` field in tauri.conf.json.

The target triple convention matches Rust's host triple so it slots
cleanly into Tauri's lookup:
    aarch64-apple-darwin
    x86_64-apple-darwin
    x86_64-unknown-linux-gnu
    x86_64-pc-windows-msvc
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDECAR_DIR = ROOT / "sidecar"
DEST_DIR = ROOT / "app" / "src-tauri" / "binaries"


def host_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return "aarch64-apple-darwin" if machine in {"arm64", "aarch64"} else "x86_64-apple-darwin"
    if system == "linux":
        return "x86_64-unknown-linux-gnu"
    if system == "windows":
        return "x86_64-pc-windows-msvc"
    msg = f"unsupported host platform: {system}/{machine}"
    raise SystemExit(msg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-triple",
        default=None,
        help="Override the detected host triple (cross-platform CI uses this)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove dist/ and build/ before running",
    )
    args = parser.parse_args(argv)

    triple = args.target_triple or host_triple()
    out_name = f"pinsilico-sidecar-{triple}"
    if platform.system().lower() == "windows" and "windows" in triple:
        out_name += ".exe"

    work = SIDECAR_DIR
    if args.clean:
        for d in (work / "dist", work / "build"):
            if d.exists():
                shutil.rmtree(d)

    # Locate PyInstaller in the active venv; fall back to the on-PATH
    # `pyinstaller` so dev machines without the sidecar venv still work.
    pyinstaller = shutil.which("pyinstaller") or str(work / ".venv" / "bin" / "pyinstaller")
    if not Path(pyinstaller).exists() and not shutil.which("pyinstaller"):
        msg = (
            "PyInstaller not found. Install dev deps first: "
            "cd sidecar && .venv/bin/pip install pyinstaller"
        )
        raise SystemExit(msg)

    cmd = [
        pyinstaller,
        "--onefile",
        "--name", out_name,
        "--specpath", str(work / "build"),
        "--distpath", str(work / "dist"),
        "--workpath", str(work / "build"),
        "--noconfirm",
        "--clean",
        # PyInstaller's static analysis misses dynamically-imported
        # framework modules. `--collect-all` walks each package and
        # bundles every submodule + datafile so uvicorn / starlette
        # / fastapi / pydantic / our own routes all end up in the
        # onefile binary. Without these, the bundle starts but fails
        # at first import with ModuleNotFoundError.
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--collect-all", "pydantic",
        "--collect-all", "pinsilico",
        # Bundle the chemistry resources directory so the runtime can find
        # the DrugBank CSV and any starter-kit PDBs.
        "--add-data",
        f"{work / 'resources'}{os.pathsep}resources",
        str(work / "pinsilico" / "__main__.py"),
    ]
    sys.stderr.write(f"running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(work), check=False)  # noqa: S603
    if result.returncode != 0:
        return result.returncode

    built = work / "dist" / out_name
    if not built.exists():
        msg = f"PyInstaller succeeded but artefact missing: {built}"
        raise SystemExit(msg)

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    target = DEST_DIR / out_name
    if target.exists():
        target.unlink()
    shutil.copy2(built, target)
    sys.stdout.write(f"copied sidecar -> {target}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
