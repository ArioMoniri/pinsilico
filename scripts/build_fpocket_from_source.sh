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

case "$(uname -s)" in
    Darwin)
        echo "==> installing fpocket via Homebrew"
        # `brew install fpocket` exits 0 cleanly even if already
        # installed, so re-runs on a warm cache are free.
        brew install fpocket
        brew_prefix="$(brew --prefix fpocket)"
        if [ ! -f "$brew_prefix/bin/fpocket" ]; then
            echo "ERROR: fpocket installed but binary not at $brew_prefix/bin/fpocket" >&2
            exit 1
        fi
        cp -f "$brew_prefix/bin/fpocket" "$DEST_DIR/fpocket"
        chmod +x "$DEST_DIR/fpocket"
        if [ -f "$brew_prefix/bin/dpocket" ]; then
            cp -f "$brew_prefix/bin/dpocket" "$DEST_DIR/dpocket"
            chmod +x "$DEST_DIR/dpocket"
        fi
        ;;

    Linux)
        echo "==> ensuring qhull + netcdf headers are present"
        if ! dpkg -s libqhull-dev >/dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq libqhull-dev libnetcdf-dev
        fi

        WORK_DIR="$(mktemp -d -t pinsilico-fpocket-build-XXXXXX)"
        # shellcheck disable=SC2064
        trap "rm -rf '$WORK_DIR'" EXIT

        echo "==> downloading fpocket ${FPOCKET_VERSION} source"
        SRC_URL="https://github.com/Discngine/fpocket/archive/refs/tags/${FPOCKET_VERSION}.tar.gz"
        SRC_SHA="5908eb271eae48d34e2d70fd04339c4c670568b7efd0e61c1d479dd1bf4ebecc"
        cd "$WORK_DIR"
        curl -fsSL -o src.tar.gz "$SRC_URL"
        GOT="$(sha256sum src.tar.gz | awk '{print $1}')"
        if [ "$GOT" != "$SRC_SHA" ]; then
            echo "ERROR: fpocket source SHA mismatch ($GOT vs $SRC_SHA)" >&2
            exit 1
        fi
        tar xf src.tar.gz
        cd "fpocket-${FPOCKET_VERSION}"

        # Repoint the Makefile's qhull include + link at the system
        # package so the broken bundled qhull tree never gets built.
        # The Makefile uses `-Isrc/qhull/src` and `-Lsrc/qhull/lib`;
        # rewrite both to `-I/usr/include/libqhull` and `-lqhull`.
        sed -i.bak \
            -e 's|-Isrc/qhull/src|-I/usr/include/libqhull|g' \
            -e 's|-Lsrc/qhull/lib|-L/usr/lib/x86_64-linux-gnu|g' \
            makefile

        # Skip the bundled qhull build target entirely so make doesn't
        # try to compile it. Each Makefile rule that depends on the
        # qhull subdir gets its dependency stripped.
        sed -i.bak -E 's|(\$\(QHULL_OBJ\)|\1\\n#disabled-qhull|g' makefile || true

        echo "==> building fpocket (skipping bundled qhull)"
        make -j "$(nproc)" bin/fpocket LFLAGS="-lqhull -lm -lnetcdf -lpthread" || {
            # Fallback: try the default target if the bin/fpocket-only
            # invocation can't find the right deps.
            make -j "$(nproc)" LFLAGS="-lqhull -lm -lnetcdf -lpthread"
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
        ;;

    *)
        echo "ERROR: unsupported platform for fpocket: $(uname -s)" >&2
        exit 1
        ;;
esac

echo "==> done. Installed: $DEST_DIR/fpocket"
"$DEST_DIR/fpocket" --version || true
