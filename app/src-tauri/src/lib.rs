//! PInSilico Tauri shell — library entry point.
//!
//! Splitting the entry into a library lets later phases re-use the same boot
//! sequence (Phase 6 sidecar wiring, future mobile builds) without
//! duplicating the Tauri setup, and lets us unit-test the pure helpers that
//! anchor the cross-stack version sync without spawning a real window.

pub mod sidecar;

use std::sync::{Arc, OnceLock};

use tauri::{Manager, State};
use tauri_plugin_shell::{process::CommandEvent, ShellExt};

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

/// Tauri-managed state for the parsed sidecar handle.
///
/// The shell spawns the sidecar from `setup()` and reads its four-line
/// banner asynchronously. Until the banner is fully parsed, IPC commands
/// return an error so the webview can show a "connecting" state.
#[derive(Default)]
pub struct SidecarState {
    pub handle: OnceLock<sidecar::SidecarHandle>,
}

#[tauri::command]
fn get_api_base(state: State<'_, Arc<SidecarState>>) -> Result<String, String> {
    state
        .handle
        .get()
        .map(sidecar::SidecarHandle::api_base)
        .ok_or_else(|| "sidecar not ready: banner not yet parsed".to_string())
}

#[tauri::command]
fn get_token(state: State<'_, Arc<SidecarState>>) -> Result<String, String> {
    state
        .handle
        .get()
        .map(|h| h.token.clone())
        .ok_or_else(|| "sidecar not ready: banner not yet parsed".to_string())
}

#[tauri::command]
fn get_sidecar_version(state: State<'_, Arc<SidecarState>>) -> Result<String, String> {
    state
        .handle
        .get()
        .map(|h| h.version.clone())
        .ok_or_else(|| "sidecar not ready: banner not yet parsed".to_string())
}

/// Boot the Tauri application. Returns to the caller only when the window
/// is closed.
///
/// Wired plugins:
/// * `tauri_plugin_updater` — auto-updater (signed manifest at
///   `endpoints` in tauri.conf.json verified against the embedded
///   `pubkey`).
/// * `tauri_plugin_process` — exposes `relaunch()` to JS so the
///   frontend can restart after a successful install.
/// * `tauri_plugin_shell` — used here to spawn the bundled
///   `pinsilico-sidecar` external binary (Phase 6 wiring).
///
/// On boot, `setup()` spawns the sidecar and parses the four-line
/// stdout banner (`PINSILICO_HOST=…` / `PORT=…` / `VERSION=…` /
/// `TOKEN=…`). The resulting [`sidecar::SidecarHandle`] is stored in
/// Tauri state; the webview reads it via the three IPC commands above.
/// If the sidecar binary isn't bundled (typical for `pnpm tauri dev`
/// before someone has run `python scripts/build_sidecar.py` once),
/// `setup()` logs the error but the window still opens so the React
/// shell can show a "sidecar not connected" status to the user.
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(Arc::new(SidecarState::default()))
        .invoke_handler(tauri::generate_handler![
            get_api_base,
            get_token,
            get_sidecar_version,
        ])
        .setup(|app| {
            let state: Arc<SidecarState> = app.state::<Arc<SidecarState>>().inner().clone();

            // `pinsilico-sidecar` is the externalBin stem listed in
            // tauri.conf.json. Tauri resolves it to the per-platform
            // suffixed binary that scripts/build_sidecar.py drops into
            // `app/src-tauri/binaries/`. Spawn failures (binary missing
            // in dev before PyInstaller has run, OS denied execution,
            // etc.) are logged but don't abort the window — the
            // frontend surfaces the disconnected state.
            match app.shell().sidecar("pinsilico-sidecar") {
                Ok(cmd) => match cmd.spawn() {
                    Ok((mut rx, _child)) => {
                        tauri::async_runtime::spawn(async move {
                            let mut banner: Vec<String> = Vec::new();
                            let mut banner_done = false;

                            while let Some(event) = rx.recv().await {
                                match event {
                                    CommandEvent::Stdout(bytes) => {
                                        let line = String::from_utf8_lossy(&bytes).to_string();
                                        println!("[sidecar] {line}");
                                        if !banner_done {
                                            banner.push(line.trim().to_string());
                                            if banner.len() >= 4 {
                                                let refs: Vec<&str> =
                                                    banner.iter().map(String::as_str).collect();
                                                if let Ok(handle) =
                                                    sidecar::SidecarHandle::from_banner(&refs)
                                                {
                                                    println!(
                                                        "[sidecar] banner parsed: {} v{}",
                                                        handle.api_base(),
                                                        handle.version,
                                                    );
                                                    let _ = state.handle.set(handle);
                                                    banner_done = true;
                                                }
                                            }
                                        }
                                    }
                                    CommandEvent::Stderr(bytes) => {
                                        let line = String::from_utf8_lossy(&bytes);
                                        eprintln!("[sidecar:stderr] {line}");
                                    }
                                    CommandEvent::Terminated(payload) => {
                                        eprintln!(
                                            "[sidecar] terminated: code={:?} signal={:?}",
                                            payload.code, payload.signal,
                                        );
                                    }
                                    _ => {}
                                }
                            }
                        });
                    }
                    Err(e) => {
                        eprintln!(
                            "[sidecar] spawn failed: {e}. The app will run but the \
                             workspace will show a disconnected status. Run \
                             `python scripts/build_sidecar.py` to populate \
                             app/src-tauri/binaries/ for local dev.",
                        );
                    }
                },
                Err(e) => {
                    eprintln!(
                        "[sidecar] could not locate externalBin 'pinsilico-sidecar': {e}",
                    );
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}
