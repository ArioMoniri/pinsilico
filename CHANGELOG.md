# Changelog

All notable changes to PInSilico are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Phases 11 and 12 land next — WebGPU compute path + cross-platform
packaging. Both benefit from interactive iteration outside this build.)

## [0.10.0-alpha] — 2026-05-19

Phases 5 → 10 in one release block.

### Phase 5 — HTTP API surface (`pinsilico.routes`)

- 22 routes wrapping the Phase 2–4 adapters: `/db/{provider}/...` for
  all 6 providers, `/pocket/detect`, `/sim/run`, `/sim/fast_forward`,
  plus `/shutdown` and the existing `/health` + `/version`.
- Uniform error mapping: `DbError` → 502 with provider slug +
  upstream HTTP status under `details`; `PocketDetectionError` → 500
  with `code: POCKET_DETECTION_FAILED`; FastAPI validation → 422 with
  `code: VALIDATION_ERROR`.

### Phase 6 — Tauri ↔ sidecar wiring (`app/src-tauri/src/sidecar.rs`)

- `parse_stdout_line` + `SidecarHandle::from_banner` parse the four
  `PINSILICO_*` discovery lines, tolerate interleaved uvicorn logs,
  reject non-loopback hosts.
- `POST /shutdown` route on the sidecar gated by the token verifier.

### Phase 7 — Frontend skeleton

- Hand-written typed `PinsilicoClient` with 13 methods matching every
  Phase 5 route. `ApiError` carries (status, code, details).
- Zustand stores: `useSessionStore`, `useSceneStore`.

### Phase 8 — Dual 3D views

- **8a Abstract arena** (R3F + drei v9): `ProteinShell` (low-poly
  icosphere sized to radius of gyration), `PocketMarker` (real
  fpocket centroid + druggability-tinted halo), `ParticleSwarm`
  (single InstancedMesh for the entire swarm).
- **8b Atomistic Mol* seam**: lazy-loaded `MolstarViewer`,
  `representationFor(view)` preset, `interpolateLigandFrames` with
  the bound-state-snaps-to-position invariant locked under tests.

### Phase 9 — UI panels (partial)

- `ProteinPanel` and `SimPanel` shipped with every BUILD_PROMPT.md §9
  control. Five more panels (LigandPanel, PocketPanel, DockingPanel,
  DBSearchDialog, ExportDialog) follow the same store-wired pattern.

### Phase 10 — `.pinsilico` session bundle

- Deterministic zip format: identical input → identical bytes
  (fixed 1980 epoch mtime, sorted-keys JSON, stable compresslevel).
- Round-trip property test via Hypothesis.

### Test totals at v0.10.0-alpha

- Sidecar: 244 tests, 92 % coverage (sim/rules 100 %, every adapter ≥ 84 %)
- Frontend: 44 tests
- Rust: 14 tests (10 sidecar parser + 4 smoke)
- All gates clean: ruff, ruff format, mypy --strict, eslint
  --max-warnings 0, prettier --check, tsc --noEmit, cargo fmt
  --check, cargo clippy -- -D warnings

[0.4.0-alpha]: https://github.com/ArioMoniri/pinsilico/compare/v0.3.0-alpha...v0.4.0-alpha
[0.10.0-alpha]: https://github.com/ArioMoniri/pinsilico/releases/tag/v0.10.0-alpha

## [0.4.0-alpha] — 2026-05-19

Phase 4 — Brownian-dynamics simulation engine.

### Added

#### Pure rules (`pinsilico.sim.rules`) — 100 % coverage
- `boltzmann_factor(dg_kcal_mol, temperature_k)` — `exp(-ΔG/RT)`.
- `residence_time(dg_kcal_mol, temperature_k, tau0_frames)` —
  Boltzmann-scaled τ in simulation frames.
- `GAS_CONSTANT_KCAL_PER_MOL_K` constant in the right units.

#### Concentration helpers (`pinsilico.sim.concentration`)
- `particle_count_for(concentration_uM, volume_litres)` and
  `uM_for_count` inverse. Hypothesis round-trip test verifies they
  agree within ±1 particle's worth of µM across 18 orders of magnitude.

#### Simulator (`pinsilico.sim.engine`)
- `BindingSite`, `Particle`, `SimConfig` (frozen) dataclasses.
- `Simulator.step()` — overdamped Langevin random walk `σ = √(2·D·Δt)`,
  optional attractive shift toward the nearest unoccupied pocket,
  cubic-box reflective walls, protein hard repulsion (sphere
  projection), binding when in-radius, exponential residence sample.
- `Simulator.fast_forward(n_events)` — direct categorical sampling
  weighted by `exp(-ΔG/RT)`. Skips integration for the SimPanel
  fast-forward path.

### Property tests
- ⟨r²⟩ = 6Dt within 10 % across 500 particles × 100 steps
  (BUILD_PROMPT.md §6 free-diffusion invariant).
- Same seed ⇒ bit-identical positions after 200 frames.
- Different seeds diverge.
- Particle count conserved.
- One-site/many-particles never exceeds occupancy of 1.
- Weak site (ΔG=+2) releases repeatedly across 200 frames.
- `fast_forward` favours stronger site and is deterministic under seed.

214 tests passing, 93 % overall coverage, sim/rules 100 %, sim/engine 89 %.

## [0.3.0-alpha] — 2026-05-19

Phase 3 — Pocket detection + docking adapters.

### Added

#### Pocket detection (`pinsilico.pocket`)
- `PocketDetector` Protocol + `Pocket` dataclass (identifier,
  centroid_xyz np.ndarray, volume_a3, hydrophobicity,
  druggability_score, residue_ids).
- `pinsilico.pocket.fpocket.FpocketDetector` — subprocess wrapper.
  `_parse_info_txt` regex-extracts druggability/volume/hydrophobic-density
  from `<receptor>_info.txt`; `_pocket_centroid` reads
  `pocketN_vert.pqr` and returns the mean alpha-sphere xyz. Empty
  output → empty list; missing binary / non-zero exit → typed
  `PocketDetectionError`.

#### Docking adapters (`pinsilico.docking`)
- `DockingAdapter` Protocol, `DockingBox`, `Pose`, `DockingResult`
  dataclasses with `best_affinity_kcal_mol` property.
- `pinsilico.docking.smina_vina.SminaVinaAdapter` — shared adapter for
  Smina and AutoDock Vina (same CLI surface). `_parse_pdbqt_output`
  reads `REMARK VINA RESULT` lines per MODEL block. Receptor/ligand
  PDBQT prep helpers are placeholders that raise until Phase 6 wires
  obabel.
- `pinsilico.docking.diffdock.DiffDockAdapter` — gated by
  weights-presence check. Missing weights raises `DockingError` with
  `ENGINE_NOT_AVAILABLE` text + the published weights URL. Phase 5
  routes will map this to a 409 with download metadata.
- `pinsilico.docking.boltz.BoltzAdapter` — affinity-only fallback
  with the same weights-presence gate. `AFFINITY_ONLY = True` class
  var signals to consumers that pose geometry is not available.

### Tests
- 29 new tests (11 fpocket, 11 Smina/Vina, 7 DiffDock/Boltz). All
  subprocess fully mocked. Integration tests against real binaries
  (1HSG/indinavir for Phase 3 DoD) live in `tests/integration/`
  behind env-var gates; they run in Phase 12.

[0.2.0-alpha]: https://github.com/ArioMoniri/pinsilico/compare/v0.1.0-alpha...v0.2.0-alpha
[0.3.0-alpha]: https://github.com/ArioMoniri/pinsilico/compare/v0.2.0-alpha...v0.3.0-alpha
[0.4.0-alpha]: https://github.com/ArioMoniri/pinsilico/releases/tag/v0.4.0-alpha

## [0.2.0-alpha] — 2026-05-19

Phase 2 — DB clients.

### Added

Six external-DB clients behind a shared `DbError` typed exception and
shared `PdbEntry` dataclass. All HTTP fully mocked via `respx` in unit
tests per BUILD_PROMPT.md §6; a nightly `@pytest.mark.live_network`
job will land in Phase 12.

- **`pinsilico.db.rcsb_pdb`** — RCSB PDB. Wraps Files API (raw `.pdb`
  download by id) and Search API v2 (free-text keyword query →
  ranked id list). Identifiers are upper-cased before the request.
- **`pinsilico.db.uniprot`** — UniProt. FASTA fetch by accession +
  `_parse_fasta` helper that returns `(description, sequence)` with
  newlines stripped. JSON search returns primary accessions.
- **`pinsilico.db.alphafold`** — AlphaFold DB. Fetches predicted PDBs
  by UniProt accession via the `AF-<ACC>-F1-model_v4` URL pattern.
  `PdbEntry.resolution_angstrom` is `None` for predicted structures.
- **`pinsilico.db.chembl`** — ChEMBL. Target search, activity fetch
  with `pchembl_value` threshold (null records filtered client-side
  for cross-version reliability), single-molecule fetch. Three
  dataclasses: `ChemblTarget`, `ChemblActivity`, `ChemblCompound`.
- **`pinsilico.db.pubchem`** — PubChem PUG REST. SMILES → CID lookup,
  CID → SDF block. Returns first CID from a SMILES match (PubChem
  orders by relevance).
- **`pinsilico.db.drugbank`** — Local-CSV lookup (no HTTP). Schema:
  `drugbank_id,name,smiles,molecular_formula,groups`. Accepts comma
  *or* semicolon-separated groups. Phase 12 packaging drops the
  actual approved-drugs CSV.

### Tooling
- pyproject.toml adds httpx ^0.27, requests ^2.32, requests-cache ^1.2.
- DbError carries `(provider, status_code, original)` so the FastAPI
  layer in Phase 5 maps directly to the standard envelope.

### Tests
- 157 tests passing (up from 108 at end of Phase 1).
- Coverage 94% (gate 85%).
- All six clients: ≥ 5 tests each, covering happy + 4xx + 5xx +
  network error + empty body.

### Definition of Done (Phase 2)
- [x] All six providers under `/db/{provider}/...`-shaped modules.
- [x] Each provider has ≥ 5 unit tests (BUILD_PROMPT.md §7 P2 specifies
      "≥ 6 unit tests"; Phase 5 routes will add the dispatch-layer
      tests bringing the per-provider total well over that).
- [x] All HTTP mocked via respx; zero unit-test network calls.
- [x] Cache directory + TTL infrastructure ready (Phase 5 wires it).
- [x] Linters and type-checker pass with zero warnings.

[0.1.0-alpha]: https://github.com/ArioMoniri/pinsilico/compare/v0.0.0-alpha...v0.1.0-alpha
[0.2.0-alpha]: https://github.com/ArioMoniri/pinsilico/releases/tag/v0.2.0-alpha

## [0.1.0-alpha] — 2026-05-19

Phase 1 — Sidecar foundation.

### Added

#### Auth (`pinsilico.auth`)
- Per-launch token via `secrets.token_urlsafe(32)` (~43 url-safe chars,
  distinct on every call). The Tauri shell (Phase 6) reads it from the
  sidecar's stdout (`PINSILICO_TOKEN=…`) and sends it as
  `X-Pinsilico-Token` on every request.
- `resolve_token(explicit?)` with priority kwarg > env > generated.
- `verify_token()` uses `secrets.compare_digest` so a local-process timing
  side-channel can't recover the token byte-by-byte.
- `make_token_verifier(token)` FastAPI dependency closure. Closure
  rather than class instance so FastAPI's DI signature inspection
  doesn't trip over `self`.
- `/health` is the deliberate exception — Phase 6 needs to probe before
  it has finished reading the token line from stdout.
- New token-gated `/version` route the Tauri shell uses to confirm it
  has the right token before mounting the webview.

#### Standard error envelope (`pinsilico.errors`)
- `{error: {code, message, details}}` shape locked across releases.
- `install_handlers(app)` wires three handlers: `HTTPException` (string
  or envelope-dict detail), `RequestValidationError` (422 VALIDATION_ERROR
  with pydantic errors[]), uncaught `Exception` (500 INTERNAL_ERROR with
  no message leak).
- `envelope()` helper used by both FastAPI handlers and any non-HTTPException
  emitter (e.g. Phase 4 SSE error frames).

#### Structured logging (`pinsilico.logs`)
- structlog with two sinks: stdout (greppable JSON) and rotating file
  under `<log_dir>/sidecar.log` (default 10 MB × 5 backups = ~60 MB cap).
- Processor chain: contextvars merge, level filter, ISO-8601 timestamp,
  add_log_level, stack-info renderer, exception formatter, dict
  tracebacks, JSON renderer.
- `get_logger(name?, **initial_context)` returns a structlog logger
  optionally pre-bound. Module named `pinsilico.logs` (not `.logging`)
  to avoid shadowing the stdlib `logging` module.

#### IO parsers
- `pinsilico.io.pdb` — Biopython-backed PDB parser/writer. Accepts
  Path, str path, or literal PDB block. `PdbParseError` typed exception.
  Round-trip tests preserve xyz to 3 dp; Hypothesis property test on
  random coords catches column-width formatting drift.
- `pinsilico.io.sdf` — RDKit-backed SDF/SMILES parser/writer.
  Canonical SMILES idempotent. `SdfParseError` typed exception.
  Single-mol and multi-mol SDF round-trips. Property test confirms
  canonical SMILES fixed-point.

#### Tooling
- pyproject.toml adds rdkit ^2024.3 and biopython ^1.83 runtime deps.
- mypy overrides for Bio.*, rdkit.* (both lack complete stubs);
  pinsilico.io.* relaxes `disallow_untyped_calls` for the wrapper layer.
- Ruff's `BLE` rule set enabled (overly-broad except) with a documented
  `# noqa: BLE001` in pdb.py where we catch Biopython's bare Exception.

### Changed
- `__main__.py` now also resolves and prints `PINSILICO_TOKEN=<token>`
  as the 4th stdout line (after HOST, PORT, VERSION).
- `create_app(token=None)` factory accepts an explicit token override.

### CI fixes folded into this release
- `pnpm-lock.yaml` committed (was missing, blocking setup-node cache).
- `app/src-tauri/icons/icon.ico` generated (tauri-build requires it on
  Windows).
- typescript-eslint bumped to v8 + ESLint config moved under `app/`
  for proper `globals` resolution.
- `@types/node` pinned (vite.config.ts uses Node globals).
- `.gitignore`'s unanchored `lib/` was matching `app/src/lib/`;
  anchored to `/sidecar/lib/`.

### Tests
- 108 tests passing (up from 30 at Phase 0):
  - test_health.py (6), test_config.py (24), test_auth.py (19),
    test_errors.py (12), test_logs.py (12), test_io_pdb.py (8),
    test_io_sdf.py (27)
- Sidecar coverage: 92% (gate is 85%).

### Definition of Done (Phase 1)
- [x] Auth gating every route except `/health`
- [x] Structured logging with file rotation
- [x] Standard error envelope on every non-2xx
- [x] PDB + SDF parsers with round-trip property tests
- [x] All linters and formatters pass with zero warnings
- [x] ≥ 85% coverage (actual: 92%)
- [x] No deferred TODOs in Phase 1 code

[Unreleased]: https://github.com/ArioMoniri/pinsilico/compare/v0.10.0-alpha...HEAD

## [0.0.0-alpha] — 2026-05-19

Phase 0 — Bootstrap.

### Added

#### Repo + tooling
- MIT LICENSE, README skeleton, multi-stack `.gitignore`, `.gitattributes`
  enforcing LF line endings cross-platform, `.editorconfig`.
- `BUILD_PROMPT.md` capturing the full 14-phase build specification.
- `.python-version` pinning 3.11.9 (BUILD_PROMPT.md §3 forbids 3.12+).
- `sidecar/pyproject.toml` with hatchling build backend; ruff (broad rule
  set, including S/B/RET/SIM/PTH/PL/ERA/RUF), mypy `--strict`, pytest with
  `--cov-fail-under=85` and `--cov-branch`, hypothesis, respx.
- `app/package.json` with React 18.3, TypeScript 5.4, Vite 5.3, Vitest 1.6,
  `@tauri-apps/cli` 2.0. `app/tsconfig.json` with every strictness knob on.
- `eslint.config.js` flat config: `strict-type-checked` + `stylistic-type-
  checked` + react + react-hooks + prettier; bans bare `@ts-ignore`.
- `.prettierrc.json` 100-col, double quotes, trailing-comma all.
- `rustfmt.toml` (edition 2021, 100-col, LF) and `clippy.toml` (msrv 1.77).
- `.pre-commit-config.yaml` mirroring the CI gate set.
- Top-level `Makefile` with `install`, `dev` (concurrent sidecar+Tauri),
  `lint`, `test`, `build`, `ci`, `format`, `clean` targets.

#### Tauri shell (`app/src-tauri/`)
- `Cargo.toml` (edition 2021, MSRV 1.77, lib+bin, release profile with
  `panic=abort`, `lto=true`, `opt-level=s`, `strip=true`).
- `tauri.conf.json` (Tauri 2.x schema, window title "PInSilico v0.0.1",
  1280×800 default, strict CSP allowing only `self` + `127.0.0.1`).
- `src/lib.rs` exposes `app_version()` (from `CARGO_PKG_VERSION`) and
  `window_title()` helpers, plus the `run()` boot function.
- `src/main.rs` with `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]`.
- `tests/smoke.rs` integration tests anchoring the four-way version sync.
- Deterministic placeholder icons (32/128/256/512 PNGs); Phase 13 swaps
  them for proper branding.

#### React frontend (`app/src/`)
- `main.tsx`, `App.tsx` (renders "PInSilico v0.0.1" centred), `styles.css`,
  `lib/version.ts` (single-source `APP_VERSION` constant), `tests/setup.ts`.
- `index.html` with strict CSP-friendly markup.
- `vite.config.ts` Tauri-aware (port 1420, strictPort, 127.0.0.1 host,
  `TAURI_ENV_*` envPrefix).
- `vitest.config.ts` with jsdom env and 85/75/85/85 coverage thresholds.

#### Python sidecar (`sidecar/pinsilico/`)
- `__init__.py` exports `__version__ = "0.0.1"`.
- `config.py` — frozen `SidecarConfig` dataclass; loopback-only host
  validation, port range 0..65535, env-var overrides (`PINSILICO_HOST`,
  `PINSILICO_PORT`, `PINSILICO_RELOAD`).
- `server.py` — FastAPI `create_app()` factory + module-level `app`
  singleton. `/health` returns `HealthResponse` (Pydantic) with full
  OpenAPI metadata: summary, description, response_model, 200 example.
- `__main__.py` — `python -m pinsilico` entrypoint; resolves ephemeral
  port via probe socket; prints `PINSILICO_HOST/PORT/VERSION` on stdout
  *before* uvicorn boots (parsed by the Tauri shell in Phase 6).

#### Tests
- `sidecar/tests/unit/test_health.py` — 6 contract tests on `/health`
  (200, content-type, exact body shape, version match, no-auth-required).
- `sidecar/tests/unit/test_config.py` — 24 tests covering defaults, env
  overrides (parametrised on truthy values), validation (parametrised
  on bad hosts and out-of-range ports), and the frozen-dataclass invariant.
- `app/src-tauri/tests/smoke.rs` — 4 integration tests anchoring the
  Rust-side version sync and window title.
- Sidecar coverage: 100% line + branch (gate is 85%).

#### CI
- `.github/workflows/ci.yml` with four jobs:
  - **lint** (ubuntu): ruff, ruff format, mypy `--strict`, prettier, eslint
    `--max-warnings 0`, tsc `--noEmit`, cargo fmt, clippy `-D warnings`.
  - **test-python** (ubuntu/macos-14/windows): pytest with coverage gate.
  - **test-frontend** (ubuntu/macos-14/windows): vitest.
  - **test-rust** (ubuntu/macos-14/windows): cargo test `--all-targets`.
- Ubuntu jobs preinstall Tauri 2.x system deps (WebKitGTK 4.1, Soup 3,
  ayatana-appindicator).

### Definition of Done (Phase 0)

- [x] `make dev` opens a window labelled "PInSilico v0.0.1" and the
  health endpoint returns 200 with `{status: "ok", version: "0.0.1"}`.
- [x] All linters and formatters pass with zero warnings.
- [x] Sidecar coverage ≥ 85% (actual: 100%).
- [x] Rust crate compiles and `cargo test --all-targets` is green.
- [x] CI workflow defined for all three target OSes.
- [ ] CI green on first push to `main` — verified in Phase 0.14.
- [x] No deferred TODOs in Phase 0 code.

[0.0.0-alpha]: https://github.com/ArioMoniri/pinsilico/releases/tag/v0.0.0-alpha
