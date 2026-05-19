# PInSilico

> Single-binary desktop app for end-to-end in-silico drug discovery: structure → pocket detection → docking → stochastic kinetic simulation, with both an abstract arena view and an atomistic Mol* view.

[![CI](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml/badge.svg)](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Status

**Phase 0 — Bootstrap.** This is the foundational scaffold. See [BUILD_PROMPT.md](BUILD_PROMPT.md) for the full 14-phase build plan.

What works today:

- Tauri 2.x desktop shell opens a window labeled "PInSilico v0.0.1"
- Python FastAPI sidecar exposes `GET /health` on `127.0.0.1`
- `make dev` runs both concurrently
- CI matrix (Ubuntu / macOS 14 / Windows) covers lint + tests on every push

## Quickstart (developers)

```bash
# Prereqs (one-time, host-level)
#  - Node 20+ with pnpm 9 (`corepack enable && corepack prepare pnpm@9 --activate`)
#  - Python 3.11.x (pyenv recommended)
#  - Rust stable + cargo-tauri (`cargo install tauri-cli --version "^2.0"`)
#  - pre-commit (`pipx install pre-commit`)

make install   # installs sidecar + frontend deps, sets up pre-commit hooks
make dev       # runs sidecar (127.0.0.1) + tauri shell concurrently
make test      # runs python + frontend + rust test suites
make lint      # ruff + mypy + eslint + prettier + clippy + rustfmt, zero warnings
```

## Architecture

PInSilico is a Tauri 2.x desktop shell (Rust) hosting a React 18 + TypeScript frontend, talking to a PyInstaller-packed Python 3.11 sidecar over local HTTP with a per-launch auth token. The sidecar wraps RDKit, Biopython, fpocket, Smina, AutoDock Vina, and (optionally) DiffDock + Boltz-2. See [docs/architecture.md](docs/architecture.md).

## License

MIT — see [LICENSE](LICENSE).
