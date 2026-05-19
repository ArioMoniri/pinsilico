# PInSilico

> Single-binary desktop app for end-to-end in-silico drug discovery: structure → pocket detection → docking → stochastic kinetic simulation, with both an abstract arena view and an atomistic Mol* view.

[![CI](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml/badge.svg)](https://github.com/ArioMoniri/pinsilico/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Status

**Phase 0 — Bootstrap.** This is the foundational scaffold. See [BUILD_PROMPT.md](BUILD_PROMPT.md) for the full 14-phase build plan and the latest entry in [CHANGELOG.md](CHANGELOG.md) for what currently ships.

What works today:

- Tauri 2.x desktop shell opens a window labeled "PInSilico v0.0.1".
- Python FastAPI sidecar exposes `GET /health` on `127.0.0.1` returning `{status: "ok", version: "0.0.1"}`.
- `make dev` runs both concurrently with a SIGINT trap so Ctrl-C kills both.
- CI matrix (Ubuntu / macOS 14 / Windows) gates lint + tests on every push and PR.
- 100 % line + branch coverage on the sidecar so far (gate: 85 %).

## Quickstart (developers)

```bash
# --- Prereqs (one-time, host-level) ---
#  - Node 20+ with pnpm 9   (`corepack enable && corepack prepare pnpm@9 --activate`)
#  - Python 3.11.x          (pyenv recommended — see .python-version)
#  - Rust stable + cargo-tauri 2.x  (`cargo install tauri-cli --version "^2.0"`)
#  - pre-commit             (`pipx install pre-commit`)
#  - Linux only: Tauri WebKitGTK 4.1 / libsoup3 / ayatana-appindicator system deps

git clone https://github.com/ArioMoniri/pinsilico.git
cd pinsilico

make install   # sidecar venv + pnpm deps + pre-commit hooks
make dev       # sidecar (127.0.0.1) + tauri shell concurrently
make test      # python pytest + frontend vitest + rust cargo test
make lint      # ruff + mypy + eslint + prettier + clippy + rustfmt
make ci        # the exact gates GitHub Actions runs
```

## Architecture

PInSilico is a Tauri 2.x desktop shell (Rust) hosting a React 18 + TypeScript frontend, talking to a PyInstaller-packed Python 3.11 sidecar over local HTTP with a per-launch auth token. The sidecar wraps RDKit, Biopython, fpocket, Smina, AutoDock Vina, and (optionally) DiffDock + Boltz-2. See [docs/architecture.md](docs/architecture.md) and [docs/api.md](docs/api.md).

The kinetic-simulation model is deliberately an abstraction, not full MD. The honest accounting of what it captures and does not capture lives in [docs/physics-model.md](docs/physics-model.md).

## Repository layout

```
pinsilico/
├── app/                # Tauri shell + React frontend
│   ├── src/            #   TypeScript app
│   └── src-tauri/      #   Rust Tauri 2.x crate
├── sidecar/            # Python 3.11 FastAPI sidecar (PyInstaller target)
│   ├── pinsilico/      #   package
│   ├── tests/          #   pytest unit/integration/property
│   └── resources/      #   bundled binaries + starter kit (Phase 12)
├── scripts/            # build / release / binary-fetch helpers
├── docs/               # architecture, api, physics-model, visualization
└── .github/workflows/  # CI (Phase 0) + release.yml (Phase 12)
```

## Contributing

Conventional commits with TDD discipline (red test commit precedes its green implementation commit). Every change must satisfy `make ci` locally before pushing. See `BUILD_PROMPT.md` §5 and §6 for the full Definition of Done and TDD rules.

## License

MIT — see [LICENSE](LICENSE).
