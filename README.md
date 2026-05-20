# 🧬 PInSilico

> Single-binary desktop app for end-to-end in-silico drug discovery 🔬💊

[![CI](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml/badge.svg)](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/ArioMoniri/pinsilico?include_prereleases&label=release)](https://github.com/ArioMoniri/pinsilico/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📥 Download

<p align="center">
  <a href="https://github.com/ArioMoniri/pinsilico/releases/latest/download/PInSilico_1.5.0_aarch64.dmg">
    <img alt="Download for macOS" src="https://img.shields.io/badge/Download_for-macOS-000000?style=for-the-badge&logo=apple&logoColor=white" height="48">
  </a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/pinsilico/releases/latest/download/PInSilico_1.5.0_x64_en-US.msi">
    <img alt="Download for Windows" src="https://img.shields.io/badge/Download_for-Windows-000000?style=for-the-badge&logo=windows&logoColor=white" height="48">
  </a>
  &nbsp;
  <a href="https://github.com/ArioMoniri/pinsilico/releases/latest/download/PInSilico_1.5.0_amd64.AppImage">
    <img alt="Download for Linux" src="https://img.shields.io/badge/Download_for-Linux-000000?style=for-the-badge&logo=linux&logoColor=white" height="48">
  </a>
</p>

<p align="center">
  <sub>macOS arm64 (.dmg) · Windows x64 (.msi) · Linux x86_64 (.AppImage) · Also available: <a href="https://github.com/ArioMoniri/pinsilico/releases/latest">.deb · .rpm · NSIS .exe</a></sub>
</p>

> **🍎 macOS:** v1.5.0+ ships with hardened-runtime entitlements (`com.apple.security.cs.disable-library-validation` and friends) so the bundled PyInstaller sidecar can load its embedded Python framework. If you upgraded from ≤ v1.4.0 and still see *Sidecar offline*, delete the old `/Applications/PInSilico.app`, drag the new one over fresh, and relaunch.

---

## ✨ What it does

🎯 Load a target protein + N similar proteins (PDB upload, RCSB, UniProt, AlphaFold)
💊 Load ligands + inhibitor candidates (SDF, SMILES, ChEMBL, PubChem, DrugBank)
🕳️ Detect binding pockets with **fpocket** — real centroids, real druggability
⚗️ Dock with **Smina** / **Vina** / **DiffDock** / **Boltz-2** (auto-routed)
🧪 Run a stochastic **Brownian-dynamics** simulation — Boltzmann residence ⏱️ from cached ΔG
👀 Watch in two views: abstract arena 🎮 (R3F, 500-particle swarm) or atomistic Mol* 🔭 (cartoon + surface + ligand)
📊 Export CSVs, MP4s, and portable `.pinsilico` session bundles
🔌 Runs **fully offline** after install

## 🚀 Quickstart (developers)

```bash
# 📋 Prereqs (one-time, host-level)
#   Node 20+ · pnpm 9 · Python 3.11 · Rust stable · cargo-tauri 2.x · pre-commit

git clone https://github.com/ArioMoniri/pinsilico.git
cd pinsilico

make install   # 🧰 sidecar venv + pnpm deps + pre-commit hooks
make dev       # ▶️ sidecar + Tauri shell side-by-side
make test      # ✅ pytest + vitest + cargo test
make lint      # 🧹 ruff + mypy + eslint + prettier + clippy + rustfmt
make ci        # 🎯 the exact gates GitHub Actions runs
```

## 📦 Status

**Phases 0 → 12 substantially complete.** 6 tags live, 11 phases shipped.

| 🚥 | Phase | Tag | Highlights |
|---|---|---|---|
| ✅ | 0 — Bootstrap | [v0.0.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.0.0-alpha) | Tauri shell + `/health` + 3-OS CI |
| ✅ | 1 — Sidecar foundation | [v0.1.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.1.0-alpha) | Auth · structlog · error envelope · PDB/SDF |
| ✅ | 2 — DB clients (×6) | [v0.2.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.2.0-alpha) | RCSB · UniProt · AlphaFold · ChEMBL · PubChem · DrugBank |
| ✅ | 3 — Pocket + docking | [v0.3.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.3.0-alpha) | fpocket · Smina · Vina · DiffDock · Boltz-2 |
| ✅ | 4 — Simulation | [v0.4.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.4.0-alpha) | ⟨r²⟩ = 6Dt · Boltzmann · determinism |
| ✅ | 5 → 10 | [v0.10.0-alpha](https://github.com/ArioMoniri/pinsilico/releases/tag/v0.10.0-alpha) | 22 routes · Tauri stdout parser · TS client · stores · dual 3D · panels · `.pinsilico` bundle |
| ✅ | 11 — WebGPU | _local_ | Renderer picker + WGSL compute shader |
| ✅ | 12 — Packaging | _local_ | Binary lockfile + PyInstaller + signed release.yml |
| ✅ | 14 — v1.0 release | [v1.0.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.0.0) | Signed 3-OS builds + Tauri auto-updater manifest |
| ✅ | 6 + 7 — Sidecar bundling + Workspace UI | [v1.1.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.1.0) | PyInstaller sidecar bundled into the .app · spawn + banner-parse + IPC commands · 3-pane workspace shell |
| ✅ | 9 + ligand library + sim trajectory | [v1.2.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.2.0) | Real Mol\* atomistic viewer · LigandPanel + 5 sources · fpocket detection wiring · /sim/run trajectory · `.pinsilico` save/load |
| ✅ | All deferred phases | [v1.3.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.3.0) | Live SSE sim streaming · Smina/Vina docking dispatch · obabel wrappers · WebGPU/WebGL2 settings toggle |
| ✅ | UX: fixer + example kit | [v1.4.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.4.0) | Clickable Sidecar pill → FixerDialog with Retry · one-click Example button loads 1CRN + aspirin + caffeine |
| ✅ | macOS hardened-runtime fix | [v1.5.0](https://github.com/ArioMoniri/pinsilico/releases/tag/v1.5.0) | `disable-library-validation` entitlement so PyInstaller's bundled `Python.framework` can load under hardened runtime + notarisation |

## 🏗️ Architecture

```
┌──────────────────────────────────────────────┐
│ 🦀 Tauri 2.x shell                            │
│  ┌────────────────────────────────────────┐  │
│  │ ⚛️ React 18 + TypeScript 5            │  │
│  │  🎮 R3F arena · 🔭 Mol* atomistic     │  │
│  └──────────────┬─────────────────────────┘  │
│                 │ HTTP + X-Pinsilico-Token   │
│  ┌──────────────▼─────────────────────────┐  │
│  │ 🐍 Python 3.11 FastAPI sidecar         │  │
│  │  🧪 RDKit · 🧬 Biopython · 🕳️ fpocket │  │
│  │  ⚗️ Smina · Vina · DiffDock · Boltz-2 │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

📚 Full details: [`docs/architecture.md`](docs/architecture.md) · [`docs/physics-model.md`](docs/physics-model.md) · [`docs/api.md`](docs/api.md) · [`BUILD_PROMPT.md`](BUILD_PROMPT.md)

## 🧮 By the numbers

- **🧪 320 tests** — 265 sidecar (92% cov) · 41 frontend · 14 Rust
- **🟢 All gates green** — ruff · mypy --strict · eslint --max-warnings 0 · clippy -D warnings
- **🧬 Honest physics** — see [docs/physics-model.md](docs/physics-model.md) for the candid account of what the kinetic sim captures and what it does not

## 📜 License

MIT — see [LICENSE](LICENSE) ✨
