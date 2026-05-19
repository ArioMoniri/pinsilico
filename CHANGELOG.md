# Changelog

All notable changes to PInSilico are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Nothing yet — Phase 1 lands next.)

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

[Unreleased]: https://github.com/ArioMoniri/pinsilico/compare/v0.0.0-alpha...HEAD
[0.0.0-alpha]: https://github.com/ArioMoniri/pinsilico/releases/tag/v0.0.0-alpha
