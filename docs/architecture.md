# Architecture

> Living document. Updated each phase. As of Phase 0 this is a stub; later phases populate it with sequence diagrams, IPC contracts, and the dual-view rendering pipeline.

## Overview

PInSilico is a three-layer system:

1. **Tauri 2.x shell (Rust)** — owns the OS window, file dialogs, and the sidecar process lifecycle. Talks to the webview over Tauri IPC and to the sidecar over `http://127.0.0.1:<ephemeral-port>` with a per-launch `X-Pinsilico-Token` header.
2. **Webview (React 18 + TypeScript)** — renders the UI and both 3D views (abstract arena via R3F/Three.js, atomistic via Mol*). State lives in Zustand stores; server calls go through TanStack Query against a typed client generated from the sidecar's OpenAPI 3.1 schema.
3. **Python 3.11 sidecar (PyInstaller)** — wraps the chemistry stack (RDKit, Biopython, biotite, Open Babel), the docking engines (Smina, Vina, optional DiffDock and Boltz-2), fpocket, and the simulation engine.

## Process model

- Shell spawns sidecar at startup. Sidecar prints `PINSILICO_TOKEN=…` and `PINSILICO_PORT=…` on stdout (Phase 1 introduces the token; Phase 6 wires the spawn into the Tauri shell).
- Shell health-checks `/health` until ready, then mounts the webview.
- Webview reads the API base + token from Tauri IPC commands (`get_api_base()`, `get_token()`).
- On window close: shell sends `POST /shutdown` to the sidecar, then kills the process after a 1 s grace period.

## What's in this scaffold today (Phase 0)

- Tauri shell that opens an empty window labeled "PInSilico v0.0.1".
- FastAPI sidecar exposing only `GET /health` returning `{"status":"ok","version":"0.0.1"}`.
- Two processes started in parallel by `make dev`. (The Phase 6 "shell spawns sidecar" wiring lands later.)

## What's intentionally not here yet

- Auth token plumbing (Phase 1)
- Real chemistry routes (Phases 2 → 5)
- Frontend stores / 3D scenes (Phases 7 → 11)
- Cross-platform packaging (Phase 12)

See [BUILD_PROMPT.md](../BUILD_PROMPT.md) §7 for the full phase plan.
