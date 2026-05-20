//! PInSilico Tauri shell — library entry point.
//!
//! Splitting the entry into a library lets later phases re-use the same boot
//! sequence (Phase 6 sidecar wiring, future mobile builds) without
//! duplicating the Tauri setup, and lets us unit-test the pure helpers that
//! anchor the cross-stack version sync without spawning a real window.

pub mod sidecar;

/// Single-source app version on the Rust side.
///
/// Pulled from `CARGO_PKG_VERSION` at compile time so it can never drift from
/// the `[package].version` field in `Cargo.toml`. Must agree with:
///
/// * `app/package.json` `version`
/// * `app/src-tauri/tauri.conf.json` `version`
/// * `app/src/lib/version.ts` `APP_VERSION`
/// * `sidecar/pyproject.toml` `[project].version`
/// * `sidecar/pinsilico/__init__.py` `__version__`
///
/// Phase 12 packaging adds a CI step asserting all six agree.
#[must_use]
pub fn app_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Window title shown by the Tauri shell.
///
/// Mirrors the static `windows[0].title` field in `tauri.conf.json`. Kept as
/// a function rather than a `const` so a future phase can append build
/// metadata (e.g. `"PInSilico v0.0.1 (canary)"`) without breaking callers.
#[must_use]
pub fn window_title() -> String {
    format!("PInSilico v{}", app_version())
}

/// Boot the Tauri application. Returns to the caller only when the window
/// is closed. The window title and identifier are configured in
/// `tauri.conf.json`. Panics on a Tauri config error (developer bug — no
/// recovery path exists).
///
/// Wires in two plugins required for the auto-updater:
/// * `tauri_plugin_updater` — checks the `endpoints` listed in
///   `tauri.conf.json`'s `plugins.updater` block, verifies the signed
///   manifest against the embedded public key, and downloads + applies
///   the new bundle.
/// * `tauri_plugin_process` — exposes `relaunch()` to the webview so the
///   frontend can restart the app after a successful install.
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|_app| Ok(()))
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}
