#!/usr/bin/env bash
# Provision an fpocket binary into sidecar/resources/binaries/.
#
# fpocket has no prebuilt binary release. The fpocket v4.1.3 Makefile
# ships a bundled qhull tree but its include paths regressed (the
# qvoronoi compilation step looks for `libqhull/libqhull.h` in places
# that don't exist), so a plain `make` fails on stock Linux + macOS
# CI runners. We sidestep that two ways:
#
#   * **macOS** — use Homebrew. The `fpocket` formula is maintained,
#     installs in seconds, and produces a working `/opt/homebrew/bin/fpocket`
#     we copy directly.
#   * **Linux** — install system libqhull-dev + libnetcdf-dev, then
#     compile fpocket from source but skip its bundled qhull subdir by
#     pointing the Makefile's qhull include + link flags at the system
#     package. ~30 s.
#
# Both paths end with `sidecar/resources/binaries/fpocket` populated,
# which is the path PyInstaller's `--add-data resources:resources` and
# the route-layer resolver look up at runtime.

set -euo pipefail

FPOCKET_VERSION="${FPOCKET_VERSION:-4.1.3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="$ROOT/sidecar/resources/binaries"
mkdir -p "$DEST_DIR"

install_deps_macos() {
    echo "==> ensuring qhull + netcdf via Homebrew"
    # Both formulae exist in homebrew-core; `brew install` is a no-op
    # if already present. We need qhull's libqhull_r (the reentrant
    # API) to link fpocket on macOS arm64.
    brew install qhull netcdf
}

install_deps_linux() {
    echo "==> ensuring qhull + netcdf headers via apt"
    if ! dpkg -s libqhull-dev >/dev/null 2>&1; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq libqhull-dev libnetcdf-dev
    fi
}

build_fpocket_from_source() {
    local include_flag="$1"   # -I path
    local link_flag="$2"      # -L path

    WORK_DIR="$(mktemp -d -t pinsilico-fpocket-build-XXXXXX)"
    # shellcheck disable=SC2064
    trap "rm -rf '$WORK_DIR'" EXIT

    echo "==> downloading fpocket ${FPOCKET_VERSION} source"
    local src_url="https://github.com/Discngine/fpocket/archive/refs/tags/${FPOCKET_VERSION}.tar.gz"
    local src_sha="5908eb271eae48d34e2d70fd04339c4c670568b7efd0e61c1d479dd1bf4ebecc"
    cd "$WORK_DIR"
    curl -fsSL -o src.tar.gz "$src_url"
    local got
    got="$(shasum -a 256 src.tar.gz | awk '{print $1}')"
    if [ "$got" != "$src_sha" ]; then
        echo "ERROR: fpocket source SHA mismatch ($got vs $src_sha)" >&2
        exit 1
    fi
    tar xf src.tar.gz
    cd "fpocket-${FPOCKET_VERSION}"

    # The Makefile baked in v4.1.3 has broken include paths for its
    # own bundled qhull tree (qvoronoi.c includes libqhull/libqhull.h
    # which doesn't resolve). Repoint the include and link flags at
    # the system qhull installed above so the bundled qhull never
    # compiles. macOS clang doesn't accept -pg (gprof), strip it.
    sed -i.bak \
        -e "s|-Isrc/qhull/src|$include_flag|g" \
        -e "s|-Lsrc/qhull/lib|$link_flag|g" \
        -e 's|-pg||g' \
        makefile

    # Skip recursing into src/qhull entirely — both submake invocations
    # in the top-level Makefile reference the qhull subdir; comment
    # those lines out so make never enters the broken tree.
    sed -i.bak -E '/cd src\/qhull/s|^|# disabled-qhull: |' makefile

    echo "==> building fpocket (system qhull)"
    make -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu || echo 2)" \
        LFLAGS="-lqhull_r -lm -lnetcdf -lpthread" 2>&1 | tail -50 || {
        # Some qhull installations (older Ubuntu) only ship plain
        # libqhull, no _r variant. Retry without the suffix.
        make clean || true
        make -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu || echo 2)" \
            LFLAGS="-lqhull -lm -lnetcdf -lpthread" 2>&1 | tail -50
    }

    if [ ! -f bin/fpocket ]; then
        echo "ERROR: fpocket build produced no bin/fpocket" >&2
        exit 1
    fi

    cp -f bin/fpocket "$DEST_DIR/fpocket"
    chmod +x "$DEST_DIR/fpocket"
    if [ -f bin/dpocket ]; then
        cp -f bin/dpocket "$DEST_DIR/dpocket"
        chmod +x "$DEST_DIR/dpocket"
    fi
}

case "$(uname -s)" in
    Darwin)
        install_deps_macos
        # Homebrew on Apple Silicon puts headers under /opt/homebrew;
        # the qhull formula installs as `libqhull_r` (reentrant API).
        QHULL_PREFIX="$(brew --prefix qhull)"
        NETCDF_PREFIX="$(brew --prefix netcdf)"
        build_fpocket_from_source \
            "-I${QHULL_PREFIX}/include/libqhull_r -I${NETCDF_PREFIX}/include" \
            "-L${QHULL_PREFIX}/lib -L${NETCDF_PREFIX}/lib"
        ;;
    Linux)
        install_deps_linux
        build_fpocket_from_source \
            "-I/usr/include/libqhull -I/usr/include" \
            "-L/usr/lib/x86_64-linux-gnu"
        ;;
    *)
        echo "ERROR: unsupported platform for fpocket: $(uname -s)" >&2
        exit 1
        ;;
esac

echo "==> done. Installed: $DEST_DIR/fpocket"
"$DEST_DIR/fpocket" --version || true
