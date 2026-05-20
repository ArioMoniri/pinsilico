/**
 * Single source of truth for the app's display version on the TS side.
 *
 * Kept in sync with:
 *  - app/package.json `version`
 *  - app/src-tauri/Cargo.toml `[package].version`
 *  - app/src-tauri/tauri.conf.json `version`
 *  - sidecar/pyproject.toml `version`
 *
 * Phase 12 packaging gates this with a CI check that asserts all four match.
 */
export const APP_VERSION = "1.2.0" as const;
