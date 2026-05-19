//! Sidecar process lifecycle.
//!
//! The Tauri shell spawns the PyInstaller-packed Python sidecar at
//! launch, parses the four-line stdout banner
//! (`PINSILICO_HOST=…`, `PINSILICO_PORT=…`, `PINSILICO_VERSION=…`,
//! `PINSILICO_TOKEN=…`), and stores the resulting [`SidecarHandle`]
//! in Tauri state.
//!
//! Phase 6 wires the spawn into the real shell. This module surfaces
//! the helpers as pure-Rust functions so they can be unit-tested
//! without a running Python process.

use std::collections::HashMap;

/// One key=value line from the sidecar's stdout banner.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StdoutLine {
    pub key: String,
    pub value: String,
}

/// Parse a single stdout line of the form `KEY=VALUE`.
///
/// Returns `None` for empty lines, lines without `=`, or lines whose
/// key isn't one of the four `PINSILICO_*` discovery keys. Strictly
/// ignoring unknown keys means uvicorn's own log output can interleave
/// with the banner without breaking the parser.
#[must_use]
pub fn parse_stdout_line(line: &str) -> Option<StdoutLine> {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return None;
    }
    let (key, value) = trimmed.split_once('=')?;
    if !key.starts_with("PINSILICO_") {
        return None;
    }
    Some(StdoutLine {
        key: key.to_string(),
        value: value.to_string(),
    })
}

/// Parsed sidecar discovery state.
#[derive(Debug, Clone)]
pub struct SidecarHandle {
    pub host: String,
    pub port: u16,
    pub version: String,
    pub token: String,
}

impl SidecarHandle {
    /// Build a handle from the four expected `PINSILICO_*` lines.
    ///
    /// Returns `Err` if any required key is missing or the port doesn't
    /// parse as `u16`.
    pub fn from_banner(lines: &[&str]) -> Result<Self, String> {
        let mut map: HashMap<String, String> = HashMap::new();
        for raw in lines {
            if let Some(parsed) = parse_stdout_line(raw) {
                map.insert(parsed.key, parsed.value);
            }
        }
        let host = map
            .remove("PINSILICO_HOST")
            .ok_or_else(|| "missing PINSILICO_HOST line".to_string())?;
        let port_raw = map
            .remove("PINSILICO_PORT")
            .ok_or_else(|| "missing PINSILICO_PORT line".to_string())?;
        let port: u16 = port_raw
            .parse()
            .map_err(|e| format!("PINSILICO_PORT not a u16: {port_raw:?} ({e})"))?;
        let version = map
            .remove("PINSILICO_VERSION")
            .ok_or_else(|| "missing PINSILICO_VERSION line".to_string())?;
        let token = map
            .remove("PINSILICO_TOKEN")
            .ok_or_else(|| "missing PINSILICO_TOKEN line".to_string())?;
        if !matches!(host.as_str(), "127.0.0.1" | "localhost" | "::1") {
            return Err(format!(
                "sidecar bound to non-loopback host {host:?}; refusing to connect"
            ));
        }
        Ok(Self {
            host,
            port,
            version,
            token,
        })
    }

    /// Base URL for HTTP requests to this sidecar instance.
    #[must_use]
    pub fn api_base(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_well_formed_line() {
        let p = parse_stdout_line("PINSILICO_HOST=127.0.0.1").unwrap();
        assert_eq!(p.key, "PINSILICO_HOST");
        assert_eq!(p.value, "127.0.0.1");
    }

    #[test]
    fn empty_line_returns_none() {
        assert!(parse_stdout_line("").is_none());
        assert!(parse_stdout_line("   ").is_none());
    }

    #[test]
    fn line_without_equals_returns_none() {
        assert!(parse_stdout_line("uvicorn running on 127.0.0.1:5000").is_none());
    }

    #[test]
    fn non_pinsilico_key_ignored() {
        assert!(parse_stdout_line("SHELL=/bin/zsh").is_none());
        assert!(parse_stdout_line("PATH=/usr/bin").is_none());
    }

    #[test]
    fn handle_from_full_banner() {
        let banner = vec![
            "PINSILICO_HOST=127.0.0.1",
            "PINSILICO_PORT=51234",
            "PINSILICO_VERSION=0.0.1",
            "PINSILICO_TOKEN=abc123xyz",
        ];
        let h = SidecarHandle::from_banner(&banner).unwrap();
        assert_eq!(h.host, "127.0.0.1");
        assert_eq!(h.port, 51234);
        assert_eq!(h.version, "0.0.1");
        assert_eq!(h.token, "abc123xyz");
        assert_eq!(h.api_base(), "http://127.0.0.1:51234");
    }

    #[test]
    fn handle_ignores_interleaved_uvicorn_lines() {
        let banner = vec![
            "INFO:     Started server process [12345]",
            "PINSILICO_HOST=127.0.0.1",
            "INFO:     Waiting for application startup.",
            "PINSILICO_PORT=51234",
            "INFO:     Application startup complete.",
            "PINSILICO_VERSION=0.0.1",
            "PINSILICO_TOKEN=abc123xyz",
        ];
        let h = SidecarHandle::from_banner(&banner).unwrap();
        assert_eq!(h.port, 51234);
    }

    #[test]
    fn missing_key_is_error() {
        let banner = vec![
            "PINSILICO_HOST=127.0.0.1",
            "PINSILICO_PORT=51234",
            // missing VERSION
            "PINSILICO_TOKEN=abc",
        ];
        let err = SidecarHandle::from_banner(&banner).unwrap_err();
        assert!(err.contains("PINSILICO_VERSION"), "got: {err}");
    }

    #[test]
    fn non_loopback_host_rejected() {
        let banner = vec![
            "PINSILICO_HOST=0.0.0.0",
            "PINSILICO_PORT=51234",
            "PINSILICO_VERSION=0.0.1",
            "PINSILICO_TOKEN=abc",
        ];
        let err = SidecarHandle::from_banner(&banner).unwrap_err();
        assert!(err.contains("non-loopback"));
    }

    #[test]
    fn bad_port_is_error() {
        let banner = vec![
            "PINSILICO_HOST=127.0.0.1",
            "PINSILICO_PORT=not-a-number",
            "PINSILICO_VERSION=0.0.1",
            "PINSILICO_TOKEN=abc",
        ];
        let err = SidecarHandle::from_banner(&banner).unwrap_err();
        assert!(err.contains("PINSILICO_PORT"));
    }

    #[test]
    fn api_base_localhost_form() {
        let banner = vec![
            "PINSILICO_HOST=localhost",
            "PINSILICO_PORT=1420",
            "PINSILICO_VERSION=0.0.1",
            "PINSILICO_TOKEN=t",
        ];
        let h = SidecarHandle::from_banner(&banner).unwrap();
        assert_eq!(h.api_base(), "http://localhost:1420");
    }
}
