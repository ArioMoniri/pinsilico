//! Phase 0 smoke tests.
//!
//! These integration tests don't open a real Tauri window — they exercise
//! the pure helpers in `pinsilico_app_lib` that anchor the four-way version
//! sync (Cargo.toml, package.json, tauri.conf.json, pyproject.toml).
//!
//! Phase 6 adds proper end-to-end window tests under a `tauri-driver` runner.

use pinsilico_app_lib::{app_version, window_title};

#[test]
fn app_version_is_phase_zero_release() {
    // BUILD_PROMPT.md §7 Phase 0: window labelled "PInSilico v0.0.1".
    // The Tauri config carries the literal title; this helper backs the
    // CI version-sync check that ties Cargo.toml, package.json,
    // tauri.conf.json, and pyproject.toml together.
    assert_eq!(app_version(), "0.0.1");
}

#[test]
fn app_version_matches_cargo_pkg_version() {
    // env! is resolved at compile time from CARGO_PKG_VERSION, which Cargo
    // sets from the [package].version field in Cargo.toml. Keeping the
    // helper in lockstep means a stale hard-coded literal can never drift.
    assert_eq!(app_version(), env!("CARGO_PKG_VERSION"));
}

#[test]
fn window_title_includes_product_and_version() {
    let title = window_title();
    assert!(
        title.starts_with("PInSilico v"),
        "window title must start with 'PInSilico v', got {title:?}",
    );
    assert!(
        title.contains(app_version()),
        "window title must include the current app_version(), got {title:?}",
    );
}

#[test]
fn window_title_matches_tauri_conf_json() {
    // tauri.conf.json hard-codes the title (Tauri 2.x has no programmatic
    // window-title override in the static config path). This test locks
    // window_title() to the same string so the two don't drift apart.
    assert_eq!(window_title(), "PInSilico v0.0.1");
}
