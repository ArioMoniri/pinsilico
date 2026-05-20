#!/usr/bin/env bash
# Build fpocket from source.
#
# fpocket has no prebuilt binary release — the GitHub release ships only
# the source tarball. binaries.lock.json's `fpocket` entry pointed at the
# source URL, which fetch_binaries.py would save verbatim (not unpack,
# not compile), so the bundled .app never had a runnable fpocket and
# "Detect pockets" reported `fpocket binary not found at 'fpocket'`.
#
# This script compiles fpocket on Linux + macOS and drops the resulting
# binary at `sidecar/resources/binaries/fpocket` so PyInstaller's
# `--add-data resources:resources` step picks it up. Windows is not
# attempted: upstream fpocket's Makefile is POSIX-only and patching
# it for MSVC is out of scope; Windows users get docking via Smina/Vina
# without an fpocket step.
#
# Build prereqs:
#   - g++ / clang++ (Xcode CLT on macOS, build-essential on Linux)
#   - tar, curl
#
# Runtime: ~30-60s on a modern laptop.

set -euo pipefail

FPOCKET_VERSION="${FPOCKET_VERSION:-4.1.3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="$ROOT/sidecar/resources/binaries"
WORK_DIR="$(mktemp -d -t pinsilico-fpocket-build-XXXXXX)"
SRC_URL="https://github.com/Discngine/fpocket/archive/refs/tags/${FPOCKET_VERSION}.tar.gz"

# Pinned SHA256 of the source tarball — same value the binaries lockfile
# tracked. Bump alongside FPOCKET_VERSION.
SRC_SHA256_v4_1_3="5908eb271eae48d34e2d70fd04339c4c670568b7efd0e61c1d479dd1bf4ebecc"

cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

echo "==> downloading fpocket ${FPOCKET_VERSION} source"
cd "$WORK_DIR"
curl -fsSL -o "fpocket-${FPOCKET_VERSION}.tar.gz" "$SRC_URL"

GOT_SHA="$(shasum -a 256 "fpocket-${FPOCKET_VERSION}.tar.gz" | awk '{print $1}')"
EXPECTED_VAR="SRC_SHA256_v$(echo "$FPOCKET_VERSION" | tr . _)"
EXPECTED="${!EXPECTED_VAR:-}"
if [ -z "$EXPECTED" ]; then
    echo "WARNING: no SHA256 pinned for fpocket ${FPOCKET_VERSION}." >&2
    echo "  downloaded SHA: $GOT_SHA" >&2
elif [ "$GOT_SHA" != "$EXPECTED" ]; then
    echo "ERROR: fpocket source-tarball SHA mismatch" >&2
    echo "  expected: $EXPECTED" >&2
    echo "  got:      $GOT_SHA" >&2
    exit 1
fi

echo "==> extracting"
tar xf "fpocket-${FPOCKET_VERSION}.tar.gz"
cd "fpocket-${FPOCKET_VERSION}"

# fpocket's Makefile defaults to g++; on macOS that's actually clang++.
# The build is tolerant of either as long as we don't pin -static.
echo "==> building (~30-60s)"
case "$(uname -s)" in
    Darwin)
        # Drop the Makefile's `-static` since macOS doesn't ship a
        # static system libc. Use sed to rewrite the LFLAGS line.
        sed -i.bak 's/-static//g' makefile
        ;;
    Linux)
        : # default makefile works
        ;;
    *)
        echo "ERROR: unsupported platform for fpocket source build: $(uname -s)" >&2
        exit 1
        ;;
esac

make -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu || echo 2)"

if [ ! -f bin/fpocket ]; then
    echo "ERROR: fpocket build succeeded but bin/fpocket is missing" >&2
    exit 1
fi

echo "==> installing into $DEST_DIR"
mkdir -p "$DEST_DIR"
cp -f bin/fpocket "$DEST_DIR/fpocket"
chmod +x "$DEST_DIR/fpocket"
# fpocket also ships a `dpocket` companion the docs reference; copy
# it too so future routes can shell out without a separate fetch.
if [ -f bin/dpocket ]; then
    cp -f bin/dpocket "$DEST_DIR/dpocket"
    chmod +x "$DEST_DIR/dpocket"
fi

echo "==> done. Built binary: $DEST_DIR/fpocket"
"$DEST_DIR/fpocket" --version || true
