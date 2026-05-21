#!/usr/bin/env bash
# Provision an fpocket binary into sidecar/resources/binaries/.
#
# fpocket has no usable prebuilt binary release. Status per platform:
#
#   * **Linux**  — install via apt (Ubuntu 20.04+ ships an `fpocket`
#     package in `universe`). One line; reliable.
#
#   * **macOS**  — source build needs three things: (1) qhull + netcdf
#     (brew install qhull netcdf), (2) a sed patch to the Makefile so
#     QCFLAGS includes `-I$(PATH_QHULL)` (the bundled qhull's
#     qvoronoi.c uses a quoted include that needs that path to
#     resolve), and (3) a prebuilt `libmolfile_plugin.a` for arm64
#     (fpocket ships the .a only for x86_64 + Intel macOS). The third
#     requirement isn't in this script yet — macOS users install
#     fpocket manually from a checkout. See README "macOS fpocket"
#     section.
#
#   * **Windows** — fpocket's Makefile is POSIX-only.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR="$ROOT/sidecar/resources/binaries"
mkdir -p "$DEST_DIR"

case "$(uname -s)" in
    Linux)
        echo "==> installing fpocket via apt"
        if ! command -v fpocket >/dev/null 2>&1; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq fpocket
        fi
        SYS_BIN="$(command -v fpocket)"
        if [ -z "$SYS_BIN" ]; then
            echo "ERROR: apt installed fpocket but it isn't on PATH" >&2
            exit 1
        fi
        cp -f "$SYS_BIN" "$DEST_DIR/fpocket"
        chmod +x "$DEST_DIR/fpocket"
        if command -v dpocket >/dev/null 2>&1; then
            cp -f "$(command -v dpocket)" "$DEST_DIR/dpocket"
            chmod +x "$DEST_DIR/dpocket"
        fi
        ;;

    Darwin)
        echo "==> macOS source build for fpocket isn't wired into CI yet."
        echo "==> Manual install path:"
        echo "      brew install qhull netcdf"
        echo "      git clone https://github.com/Discngine/fpocket"
        echo "      cd fpocket && sed -i.bak \\"
        echo "        -e 's|^QCFLAGS *= \\(.*\\)|QCFLAGS = \\1 -I\$(PATH_QHULL)|' \\"
        echo "        -e 's|^CFLAGS *= \\(.*\\)|CFLAGS = \\1 -I\$(PATH_QHULL)|' \\"
        echo "        -e 's|-pg||g' \\"
        echo "        -e 's|^ARCH.*= LINUXAMD64|ARCH = MACOSXX86_64|' makefile"
        echo "      make bin/fpocket LFLAGS=\"-lqhull_r -lm -lnetcdf\""
        echo "      # On Apple Silicon you'll need MACOSXARM64 plugins built"
        echo "      # separately or use arch -x86_64 for x86_64 cross-compile."
        echo "==> Skipping fpocket bundling. Set FPOCKET_BIN env to use it."
        ;;

    *)
        echo "ERROR: unsupported platform for fpocket: $(uname -s)" >&2
        exit 1
        ;;
esac

if [ -f "$DEST_DIR/fpocket" ]; then
    echo "==> done. Installed: $DEST_DIR/fpocket"
    "$DEST_DIR/fpocket" --version 2>/dev/null || true
fi
