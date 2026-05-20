//! Cross-stack version-sync smoke tests.
//!
//! These integration tests don't open a real Tauri window — they exercise
//! the pure helpers in `pinsilico_app_lib` that anchor the six-way version
//! sync (Cargo.toml, tauri.conf.json, package.json, pyproject.toml,
//! __init__.py, version.ts).

use pinsilico_app_lib::{app_version, window_title};

#[test]
fn app_version_matches_semver_pattern() {
    let v = app_version();
    let parts: Vec<&str> = v.split('.').collect();
    assert!(
        parts.len() >= 3,
        "app_version() must be semver-shaped (N.N.N[-pre]), got {v:?}",
    );
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
fn window_title_format_is_pinsilico_v_then_pkg_version() {
    // tauri.conf.json's window title is set statically; this test pins the
    // Rust-side format so the two don't drift even though we can't read
    // tauri.conf.json at test time without parsing it.
    let expected = format!("PInSilico v{}", env!("CARGO_PKG_VERSION"));
    assert_eq!(window_title(), expected);
}
