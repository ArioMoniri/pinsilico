#!/usr/bin/env bash
# Build AutoDock Vina from source.
#
# NOTE FOR v1.0.0: release.yml does NOT call this on macOS — the macOS
# arm64 build is marked _unavailable in scripts/binaries.lock.json because
# Vina v1.2.5 source requires Boost <= 1.84 (Homebrew only ships 1.85+,
# which removed boost/filesystem/convenience.hpp). macOS users get
# docking via smina (a Vina fork with the same scoring function);
# SminaVinaAdapter speaks both engines.
#
# This script is kept for:
#   - Manual local builds on platforms where developers can install
#     Boost 1.84 from source / older Homebrew bottle / conda.
#   - Linux source builds where the apt-installed Boost is still <= 1.84.
#
# Outputs sidecar/resources/binaries/vina, matching the layout
# fetch_binaries.py would produce on platforms that do ship binaries.
#
# Build prereqs (Linux):
#   - g++, make, libboost-dev, libboost-system-dev, libboost-thread-dev,
#     libboost-serialization-dev, libboost-filesystem-dev,
#     libboost-program-options-dev, swig

set -euo pipefail

VINA_VERSION="${VINA_VERSION:-1.2.5}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="$ROOT/sidecar/resources/binaries"
WORK_DIR="$(mktemp -d -t pinsilico-vina-build-XXXXXX)"
SRC_URL="https://github.com/ccsb-scripps/AutoDock-Vina/archive/refs/tags/v${VINA_VERSION}.tar.gz"

# Pinned SHA256 of the source tarball. Verified once; bump alongside
# VINA_VERSION.
SRC_SHA256_v1_2_5="38aec306bff0e47522ca8f581095ace9303ae98f6a64031495a9ff1e4b2ff712"

cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

echo "==> downloading Vina ${VINA_VERSION} source"
cd "$WORK_DIR"
curl -fsSL -o "vina-${VINA_VERSION}.tar.gz" "$SRC_URL"

# Verify the source-tarball checksum.
GOT_SHA="$(shasum -a 256 "vina-${VINA_VERSION}.tar.gz" | awk '{print $1}')"
EXPECTED_VAR="SRC_SHA256_v$(echo "$VINA_VERSION" | tr . _)"
EXPECTED="${!EXPECTED_VAR:-}"
if [ -z "$EXPECTED" ]; then
    echo "WARNING: no SHA256 pinned for Vina ${VINA_VERSION}." >&2
    echo "  downloaded SHA: $GOT_SHA" >&2
    echo "  Add this to scripts/build_vina_from_source.sh and commit it." >&2
elif [ "$GOT_SHA" != "$EXPECTED" ]; then
    echo "ERROR: Vina source-tarball SHA mismatch" >&2
    echo "  expected: $EXPECTED" >&2
    echo "  got:      $GOT_SHA" >&2
    exit 1
fi

echo "==> extracting"
tar xf "vina-${VINA_VERSION}.tar.gz"

# Pick the right build directory. The Vina v1.2.5 source tree has
# Makefiles at build/<os>/release/Makefile (verified locally against
# the v1.2.5 tarball; do NOT use build/<os>/Makefile — that path
# doesn't exist).
case "$(uname -s)" in
    Darwin)
        BUILD_DIR="AutoDock-Vina-${VINA_VERSION}/build/mac/release"
        ;;
    Linux)
        BUILD_DIR="AutoDock-Vina-${VINA_VERSION}/build/linux/release"
        ;;
    *)
        echo "ERROR: unsupported platform for source build: $(uname -s)" >&2
        exit 1
        ;;
esac

if [ ! -d "$BUILD_DIR" ]; then
    echo "ERROR: expected build directory not found: $BUILD_DIR" >&2
    echo "       Vina source layout may have changed; update this script." >&2
    exit 1
fi
cd "$BUILD_DIR"

if [ ! -f Makefile ]; then
    echo "ERROR: no Makefile in $BUILD_DIR — Vina source layout may have changed." >&2
    exit 1
fi

echo "==> building in $BUILD_DIR (~30 s on Apple Silicon / Linux)"
# Vina's bundled Makefile pins `BASE=/usr/local` with `=` (not `?=`), so
# `BASE=` must be passed on the make command line to override (env var is
# ignored). On Apple Silicon, Homebrew lives under /opt/homebrew.
MAKE_BASE=""
if [ "$(uname -s)" = "Darwin" ] && [ -d "/opt/homebrew/include/boost" ]; then
    MAKE_BASE="BASE=/opt/homebrew"
elif [ "$(uname -s)" = "Darwin" ] && [ -d "/usr/local/include/boost" ]; then
    MAKE_BASE="BASE=/usr/local"
fi
make $MAKE_BASE -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu || echo 2)"

echo "==> installing into $DEST_DIR"
mkdir -p "$DEST_DIR"
cp -f vina "$DEST_DIR/vina"
chmod +x "$DEST_DIR/vina"
echo "==> done. Built binary: $DEST_DIR/vina"
"$DEST_DIR/vina" --version || true
