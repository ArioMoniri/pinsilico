# Pocket detection — installing fpocket (or skipping it)

PInSilico's "Detect pockets" button shells out to [fpocket](https://github.com/Discngine/fpocket),
a small C/C++ tool that finds candidate binding cavities in a protein
structure. fpocket isn't bundled in any of the shipped `.dmg` /
`.msi` / `.AppImage` because:

- **No prebuilt binary** — upstream releases ship only source, and
  fpocket v4.1.3's bundled qhull tree has broken include paths that
  prevent a clean CI build.
- **No Homebrew formula** on macOS.
- **Not in Ubuntu 24.04 repos** (was in earlier LTS as
  `universe/fpocket`, dropped from noble).
- **POSIX-only Makefile** rules out Windows entirely.

Two paths forward — pick one.

## Option A — use a `.pinsilico` bundle (no fpocket needed)

If you don't have fpocket installed, you don't have to. Pocket data
round-trips through PInSilico's `.pinsilico` session-bundle format,
so you can:

1. Run "Detect pockets" once on a machine that **does** have fpocket
   (e.g., a Linux box with `conda install -c bioconda fpocket`).
2. Click the **Save** button in the toolbar. The sidecar writes a
   deterministic zip containing every protein, every pocket, every
   ligand.
3. Share the `.pinsilico` file. The recipient clicks **Open** in their
   PInSilico toolbar and gets the whole workspace — pockets included —
   without ever running fpocket.

The bundled **Example** kit takes this approach: 1CRN ships with a
pre-detected demo pocket so the Run + Dock flow works end-to-end
without an fpocket install.

This is the **recommended path** for most users.

## Option B — install fpocket manually

If you want to detect pockets on arbitrary structures locally, install
fpocket and tell PInSilico where to find it:

### macOS (Apple Silicon or Intel)

```bash
brew install qhull netcdf
git clone https://github.com/Discngine/fpocket.git
cd fpocket
sed -i.bak \
  -e 's|^QCFLAGS *= \(.*\)|QCFLAGS = \1 -I$(PATH_QHULL)|' \
  -e 's|^CFLAGS *= \(.*\)|CFLAGS = \1 -I$(PATH_QHULL)|' \
  -e 's|-pg||g' \
  -e 's|^ARCH.*= LINUXAMD64|ARCH = MACOSXX86_64|' \
  makefile

# Apple Silicon: fpocket's bundled libmolfile_plugin.a is x86_64-only,
# so cross-compile or build via Rosetta (`arch -x86_64 make ...`).
# Intel macOS users skip the arch step.
make bin/fpocket LFLAGS="-L$(brew --prefix qhull)/lib -lqhull_r -lm -L$(brew --prefix netcdf)/lib -lnetcdf"

# Tell PInSilico where it is. Add to ~/.zshrc or ~/.bash_profile to
# make it persist across sessions:
export FPOCKET_BIN="$PWD/bin/fpocket"
```

Then quit + relaunch PInSilico. The Sidecar pill reads `FPOCKET_BIN`
on boot.

### Linux

Easiest is `conda` (works on any distro):

```bash
# Install miniconda or micromamba if you don't have it, then:
conda install -c bioconda fpocket
export FPOCKET_BIN="$CONDA_PREFIX/bin/fpocket"
```

Or build from source (Ubuntu/Debian):

```bash
sudo apt install libqhull-dev libnetcdf-dev
git clone https://github.com/Discngine/fpocket.git
cd fpocket
sed -i.bak \
  -e 's|^QCFLAGS *= \(.*\)|QCFLAGS = \1 -I$(PATH_QHULL)|' \
  -e 's|^CFLAGS *= \(.*\)|CFLAGS = \1 -I$(PATH_QHULL)|' \
  makefile
make bin/fpocket LFLAGS="-L/usr/lib/x86_64-linux-gnu -lqhull_r -lm -lnetcdf"
export FPOCKET_BIN="$PWD/bin/fpocket"
```

Relaunch PInSilico.

### Windows

fpocket's Makefile is POSIX-only and there's no recommended Windows
build path. Use Option A (load a `.pinsilico` bundle from someone with
fpocket) or run PInSilico under WSL2 with the Linux build above.

## Confirming it worked

After setting `FPOCKET_BIN` and relaunching the app:

1. Click **Example** in the toolbar (loads 1CRN with the bundled demo
   pocket).
2. Click **+ Add protein** → RCSB → enter `1AKE` (adenylate kinase,
   classic two-pocket structure) → Add.
3. On the 1AKE card click **Detect pockets (fpocket)**.

If your `FPOCKET_BIN` resolved correctly the status bar will report
something like `Detected 3 pocket(s) in 1AKE.` If it still shows
`fpocket isn't bundled…` the env var didn't reach the spawned sidecar
— in that case, launch the app from a terminal that has `FPOCKET_BIN`
already exported:

```bash
FPOCKET_BIN=/path/to/fpocket open /Applications/PInSilico.app
```

on macOS, or just run the bundled executable on Linux.

## Why we didn't bundle it

We tried — see [`scripts/build_fpocket_from_source.sh`](../scripts/build_fpocket_from_source.sh)
for the recipes that nearly worked. The blockers:

- fpocket's bundled qhull tree (`src/qhull/src/`) hardcodes a quoted
  `#include "libqhull/libqhull.h"` path that doesn't resolve unless
  the top-level Makefile's `CFLAGS` AND `QCFLAGS` both include
  `-Isrc/qhull/src`. We patch this in the build script.
- On Apple Silicon the `libmolfile_plugin.a` fpocket ships is x86_64
  only; the link fails with undefined `_molfile_*` symbols. Building
  the VMD molfile plugin for arm64 is its own multi-hour project we
  decided wasn't worth blocking shipping.

If you've solved the arm64 molfile plugin problem and want to upstream
a working CI bundle, the build script is a good starting point.
