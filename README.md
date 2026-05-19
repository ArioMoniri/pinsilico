# 🧬 PInSilico

> Single-binary desktop app for end-to-end in-silico drug discovery 🔬💊

[![CI](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml/badge.svg)](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
| 🔜 | 14 — v1.0 release | — | Awaiting lockfile-populate + signing certs |

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
