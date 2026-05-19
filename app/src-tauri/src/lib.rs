//! PInSilico Tauri shell — library entry point.
//!
//! The `run` function is invoked from `main.rs` on every platform. Splitting
//! the entry into a library lets later phases re-use the same boot sequence
//! (e.g. Phase 6 sidecar wiring, future mobile builds) without duplicating
//! the Tauri setup.

/// Boot the Tauri application. Returns to the caller only when the window
/// is closed. The window title and identifier are configured in
/// `tauri.conf.json`. Panics on a Tauri config error (developer bug — no
/// recovery path exists).
pub fn run() {
    tauri::Builder::default()
        .setup(|_app| Ok(()))
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}
