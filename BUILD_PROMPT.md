# PInSilico — Master Build Prompt for Claude Code

> **How to use this file.** Save as `BUILD_PROMPT.md` at the repo root. Open Claude Code in the local directory and paste the full contents of this file as the first message. Claude Code must read the *entire* document before writing any code, then execute Phase 0 → Phase 14 sequentially without deferring tasks. If a phase is blocked, fix the blocker before moving on. Commit and push after every completed task.

---

## 0. Project Context (Authoritative)

* **Local working directory**: `/Users/ario/Downloads/pinsilico/`
* **Remote**: `https://github.com/ArioMoniri/pinsilico.git`
* **Default branch**: `main` (protected — feature work happens on `feat/*`, merged via fast-forward after CI passes)
* **License**: MIT
* **Maintainer username**: ArioMoniri
* **OS targets**: macOS 12+ (Apple Silicon + Intel), Windows 10/11 x64, Linux x86_64 (glibc ≥ 2.31)
* **Fully offline after install**: the installer ships Smina, AutoDock Vina, fpocket, Open Babel, ffmpeg, RDKit, Biopython, a Mol* build, and a curated starter dataset. DiffDock and Boltz-2 weights are optional, gated behind an explicit "Download extra engines" action. Protein–protein docking (HADDOCK3, pyDock) is **out of scope for v1**; the hooks exist in the engine registry but the UI flags them as "not available — peptide/protein inhibitors are post-v1".

---

## 1. Mission

PInSilico is a single-binary desktop app that lets a researcher:

1. Load a **protein of interest** plus N **similar proteins** (homologs, off-targets) from local PDB files or by querying RCSB PDB, UniProt, or AlphaFold DB.
2. Load **ligands** (natural substrates) and/or **small-molecule inhibitor candidates** from local SDF/MOL2/SMILES, or by querying ChEMBL, PubChem, or DrugBank.
3. **Detect binding pockets** automatically with fpocket for every loaded protein. Pocket centroid, volume, hydrophobicity, and druggability score are surfaced in the UI and used both as docking box hints and as the binding-site positions in the simulation.
4. Configure a **docking engine** per run (Smina, AutoDock Vina, optional DiffDock, optional Boltz-2 affinity-only) with engine-specific parameters, cofactors, pH, temperature, ionic strength, exhaustiveness, and box dimensions (auto-derived from the chosen pocket or set manually).
5. **Dock** each (ligand or inhibitor, protein, pocket) triple, cache the resulting ΔG and 3D pose, and visualize the docked complex in atomistic detail with Mol*.
6. Run a **stochastic 3D physics simulation** in which inhibitor and/or ligand particles undergo **Brownian dynamics** through a bounded volume containing the loaded proteins at their actual radii, with binding sites placed at the real fpocket-detected pocket centroids. Residence times in each pocket are Boltzmann-scaled from the cached docking ΔG: `τ ∝ exp(-ΔG/RT)`.
7. Toggle **modes**: inhibitor-only, ligand-only, or competition (both species compete for the same finite set of pocket sites; first-come-first-served, no displacement).
8. Toggle **views**: **abstract arena** (Three.js, simplified protein shells with visible pockets, 60 fps with hundreds of particles, optimised for watching many trials at once) and **atomistic molecular view** (Mol* with cartoon/surface/ball-and-stick representations, real PDB atoms, real docked ligand poses, frame-by-frame trajectory playback of a single binding event).
9. Run **N iterations** (1 → 100 000) and observe selectivity distributions in real time, with the option to fast-forward statistically.
10. **Export** everything: docking scores (CSV/JSON), simulation trajectories (binary + replay JSONL), per-protein occupancy plots (PNG/SVG), animation clips (MP4/WebM) from either view, and a portable `.pinsilico` session bundle.
11. Run **fully offline** after install, except when the user explicitly requests a DB query or an optional-engine download.

---

## 2. Architecture (Final — Do Not Renegotiate)

```
┌──────────────────────────────────────────────────────────────┐
│  Tauri 2.x desktop shell (Rust)                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  React 18 + TypeScript 5 + Vite 5                      │  │
│  │  ┌──────────────────────┐ ┌─────────────────────────┐  │  │
│  │  │ Abstract arena view  │ │ Atomistic view (Mol*)   │  │  │
│  │  │ R3F + Three.js       │ │ molstar npm package     │  │  │
│  │  │ - simplified protein │ │ - cartoon + surface     │  │  │
│  │  │   shells with real   │ │ - real PDB structures   │  │  │
│  │  │   pocket markers     │ │ - docked ligand poses   │  │  │
│  │  │ - instanced particles│ │ - frame-by-frame replay │  │  │
│  │  │ - WebGPU or WebGL2   │ │   of one binding event  │  │  │
│  │  └──────────────────────┘ └─────────────────────────┘  │  │
│  │  - shadcn/ui + Tailwind CSS 3                          │  │
│  │  - Zustand 4 + TanStack Query 5                        │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │ Tauri IPC + localhost HTTP           │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │  Python 3.11 sidecar (PyInstaller --onefile)           │  │
│  │  - FastAPI on 127.0.0.1:<ephemeral port>, token auth   │  │
│  │  - pinsilico.docking  (Vina, Smina, DiffDock, Boltz)   │  │
│  │  - pinsilico.pocket   (fpocket adapter + Pocket model) │  │
│  │  - pinsilico.db       (PDB, UniProt, AlphaFold,        │  │
│  │                        ChEMBL, PubChem, DrugBank)      │  │
│  │  - pinsilico.sim      (Brownian dynamics + rules)      │  │
│  │  - pinsilico.io       (file parsers, exports)          │  │
│  │  - pinsilico.session  (save/load bundles)              │  │
│  │  - bundled binaries: smina, vina, fpocket, obabel,     │  │
│  │    ffmpeg, mk_prepare                                  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

The Tauri shell spawns the PyInstaller-packed sidecar at startup, reads the chosen port + auth token from stdout, then talks to it over `http://127.0.0.1:<port>` with the header `X-Pinsilico-Token: <token>`. Sidecar dies when the shell exits.

---

## 3. Tech Stack — Pin These Versions

| Layer            | Choice                                                |
|------------------|-------------------------------------------------------|
| Shell            | Tauri `^2.0`, Rust stable, `tauri-plugin-shell` for sidecar |
| Frontend build   | Vite `^5`, pnpm `^9`, Node `20 LTS`                   |
| UI               | React `^18.3`, TypeScript `^5.4` (strict), shadcn/ui  |
| Abstract 3D view | three `^0.160`, @react-three/fiber `^8`, drei `^9`, @react-three/postprocessing |
| Atomistic view   | molstar `^4.4` (npm package, used headlessly with the `PluginContext` API — not the bundled UI) |
| State            | Zustand `^4`, TanStack Query `^5`                     |
| Charts           | recharts `^2`                                          |
| Python           | 3.11.x (do NOT use 3.12 — RDKit + Open Babel wheel availability) |
| Sidecar server   | FastAPI `^0.110`, uvicorn `^0.29`                      |
| Chem             | rdkit-pypi `^2024.3`, openbabel-wheel, biopython `^1.83`, biotite `^0.41` (surface meshes), prody `^2.4` |
| Docking (bundled, default) | Smina (latest static binary), AutoDock Vina `^1.2.5`, meeko `^0.6` for ligand prep |
| Docking (optional, on-demand download) | DiffDock-L (~3 GB weights), Boltz-2 (~1.5 GB weights, affinity-only) |
| Pocket detection | fpocket `^4.1` (bundled static binary)                |
| HTTP             | requests `^2.32`, requests-cache `^1.2`, httpx `^0.27` (async) |
| Testing (Py)     | pytest `^8`, pytest-cov, pytest-asyncio, hypothesis `^6`, respx (mocking httpx) |
| Testing (TS)     | vitest `^1`, @testing-library/react, msw `^2`, playwright `^1.44` |
| Packaging        | PyInstaller `^6.6`, Tauri bundler                      |
| Lint/format      | ruff, mypy strict, eslint flat config, prettier, rustfmt, clippy `-D warnings` |
| Pre-commit       | pre-commit `^3.7`                                      |

If a pinned version is unavailable on a target platform, fail loudly — do **not** silently bump majors.

**Why these engines, and no others, for v1.** Smina (Vina-family with better scoring options and faster ligand prep) and AutoDock Vina are the bedrock of academic small-molecule docking and run in seconds on a laptop without a GPU. DiffDock is the strongest open AI docker today but its weights are too large to bundle by default. Boltz-2 gives a fast affinity-only fallback when the user doesn't care about poses. HADDOCK3 / pyDock / ZDOCK / FTDock are protein–protein tools — out of scope for v1, which targets small-molecule inhibitors only. The engine registry leaves slots for them so a v2 can plug them in without restructuring.

---

## 4. Repository Layout

See the §4 section of the source build prompt; the on-disk layout under `app/`, `sidecar/`, `scripts/`, and `docs/` is materialised commit-by-commit through Phase 0.

---

## 5. Universal Definition of Done (applies to every task)

A task is **done** only when **all** of the following are true:

1. Code compiles / type-checks on all three target OSes (locally on macOS; CI on Linux + Windows).
2. All new code is covered by tests to ≥ 85 % line coverage, ≥ 75 % branch coverage. Pure functions in `pinsilico.sim.rules`, `pinsilico.sim.concentration`, `pinsilico.sim.potentials`, `pinsilico.docking.*`, and `pinsilico.pocket.*` must be ≥ 95 %.
3. No deferred TODOs in changed files. If a thing can't be built now, the phase is blocked — surface the blocker and stop.
4. Linters and formatters pass with zero warnings: `ruff check`, `ruff format --check`, `mypy --strict sidecar`, `eslint --max-warnings 0`, `prettier --check`, `cargo clippy -- -D warnings`, `cargo fmt --check`.
5. Public API is documented with docstrings (Google style, Python) or TSDoc (TypeScript). Every FastAPI route has a `summary`, `description`, response model, and example.
6. `docs/api.md` is regenerated from the FastAPI OpenAPI schema.
7. Changelog entry added under `## Unreleased` in `CHANGELOG.md`.
8. One commit per logical change, conventional commits format. No `wip`, no `stuff`.
9. Push to remote after every task. If you can't push, treat it as a blocker.
10. CI is green before declaring the phase done.

---

## 6. Test-Driven Development Rules (binding)

* Write the failing test first; commit it as `test(scope): …`. Then make it pass with `feat(scope): …`. The red → green transition must be visible in `git log`.
* Test pyramid targets: 70 % unit, 20 % integration, 10 % end-to-end.
* Property-based tests with Hypothesis for: residence time monotonicity in ΔG; Boltzmann ratio correctness within 1 %; MSD scaling `<r²> ≈ 6Dt`; particle conservation; competition fairness; pocket-detection idempotency; CSV/session bundle round-trip stability.
* External HTTP is always mocked with `respx` (Python) and `msw` (TS) in unit/integration tests. One nightly CI job hits real APIs (`@pytest.mark.live_network`) and is allowed to fail without blocking releases.
* Performance budgets are asserted in CI on the Linux runner — see source build prompt §6 for the full table.
* TDD also applies to bug fixes: every reported bug ships with a regression test that fails on `main` before the fix is committed.

---

## 7. Phase Plan

Phases 0 → 14, each ending with CI green, a tag (`v0.<phase>.0-alpha`), and a `CHANGELOG.md` block. Full details in the source build prompt; this file is the in-repo authoritative reference. Phases summary:

- **Phase 0** — Bootstrap (this commit + the rest of Phase 0)
- **Phase 1** — Sidecar foundation (auth, logging, IO)
- **Phase 2** — DB clients (RCSB, UniProt, AlphaFold, ChEMBL, PubChem, DrugBank)
- **Phase 3** — Pocket detection (fpocket) + docking adapters (Smina, Vina, DiffDock, Boltz)
- **Phase 4** — Simulation engine (Brownian + Boltzmann residence + competition)
- **Phase 5** — Sidecar HTTP API + OpenAPI → TS client generation
- **Phase 6** — Tauri ↔ sidecar wiring (token + ephemeral port + health-check)
- **Phase 7** — Frontend skeleton (routes, stores, typed API client)
- **Phase 8** — Dual 3D views (abstract arena R3F + atomistic Mol*)
- **Phase 9** — UI panels & dialogs
- **Phase 10** — Session bundle + multi-format export
- **Phase 11** — WebGPU compute path + settings
- **Phase 12** — Cross-platform packaging (PyInstaller + Tauri bundler + signing)
- **Phase 13** — Docs, demo, accessibility polish
- **Phase 14** — v1.0 release (signed installers)

---

## 8. Critical Implementation Notes

1. **Two views, one truth.** Abstract arena and Mol* atomistic view are two renderings of the same simulation state. Zustand sim store is the single source of truth.
2. **Pockets are real, not invented.** Binding sites come from fpocket centroids on the actual loaded PDB. If fpocket finds zero druggable pockets, the UI says so and offers manual box specification — do not fabricate a site.
3. **Movement is Brownian.** Overdamped Langevin integrator with a proper diffusion coefficient. MSD scales as `6Dt` for free particles — property-tested.
4. **The encounter potential is honestly labelled.** The optional attractive potential near unoccupied pockets is a kinetic accelerator. It is not real electrostatics. `docs/physics-model.md` says this plainly; the SimPanel tooltip says it; the toggle is one click away from OFF.
5. **The simulation is a kinetic abstraction, not full MD.** Atomistic view replays the docked pose under harmonic restraint plus thermal noise — it shows what binding *looks* like; it does not run MD on the bound complex.
6. **Cofactors are first-class.** Common cofactors (Mg²⁺, Zn²⁺, ATP, NADH, heme) are bundled with 3D coordinates.
7. **pH and protonation.** Open Babel runs at the chosen pH; the pH is recorded in the run record and shown in the atomistic view metadata badge.
8. **Determinism.** Same seed + same inputs ⇒ bit-identical event log AND identical trajectory geometry. Property-tested.
9. **No silent fallbacks.** Missing DiffDock weights → loud error with download offer. Missing fpocket binary → loud error with manual-box fallback.
10. **No telemetry.** Ever. Logs are local. No "share data" toggle exists in Settings — its absence is the feature.
11. **Bundled binaries are checksum-verified at build and at first launch.**
12. **DB queries are opt-in.** Nothing hits the network unless the user clicks a search button or accepts an extra-engine download prompt.
13. **Performance is part of correctness.** Tests at 10 particles also exist at 500.
14. **Mol* is loaded lazily.** Dynamic `import()` on first switch to atomistic view.
15. **Protein–protein docking is v2.** Don't half-implement HADDOCK3 / pyDock in v1.

---

## 9. First-Run Bootstrap Sequence

```bash
cd /Users/ario/Downloads/pinsilico/
git init -b main
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/ArioMoniri/pinsilico.git
```

From this point on, every action follows the Phase plan in §7, the DoD in §5, and the TDD rules in §6.

---

## 10. When You're Stuck

```
BLOCKER (phase N, task X):
- What I tried: …
- Why it failed: …
- What I need: …
```

Do not invent workarounds that violate the DoD.
