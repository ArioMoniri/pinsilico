#!/usr/bin/env bash
# Build the full Tauri bundle for the host platform.
#
# Order:
#   1. fetch_binaries.py — pull bundled binaries (fpocket, smina, vina,
#      obabel, ffmpeg) and verify SHA256s against scripts/binaries.lock.json.
#   2. build_sidecar.py — PyInstaller bundles the Python sidecar into
#      app/src-tauri/binaries/pinsilico-sidecar-<triple>.
#   3. pnpm tauri build — Tauri compiles the Rust shell, runs Vite to
#      bundle the frontend, and produces a platform-native installer.
#
# CI's release.yml runs this on each OS in the matrix and uploads the
# resulting artefacts to the GitHub Release.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> fetching bundled binaries"
python3 scripts/fetch_binaries.py

echo "==> building Python sidecar"
python3 scripts/build_sidecar.py

echo "==> building Tauri bundle"
cd app
pnpm tauri build

echo "==> done"
