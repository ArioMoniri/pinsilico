/**
 * Thin wrapper around Tauri's `@tauri-apps/api` invoke channel for the
 * three sidecar-discovery IPC commands exposed by the Rust shell.
 *
 * Each command returns the same value once the shell's setup hook has
 * parsed the sidecar's four-line stdout banner. While the banner is
 * still being read (or if the sidecar binary was missing on boot —
 * common in `pnpm tauri dev` before `python scripts/build_sidecar.py`
 * has run once) the Rust side returns a "sidecar not ready" error
 * which we surface to the UI as a connection-pending status.
 */

import { invoke } from "@tauri-apps/api/core";

export interface SidecarDiscovery {
  apiBase: string;
  token: string;
  version: string;
}

/**
 * Read all three discovery values in parallel. Throws if any are not
 * yet available. Callers should wrap this in a polling loop with a
 * short delay for the first few seconds of app startup.
 */
export async function fetchSidecarDiscovery(): Promise<SidecarDiscovery> {
  const [apiBase, token, version] = await Promise.all([
    invoke<string>("get_api_base"),
    invoke<string>("get_token"),
    invoke<string>("get_sidecar_version"),
  ]);
  return { apiBase, token, version };
}

/**
 * Poll the IPC layer until the sidecar banner has been parsed, with a
 * cap so the UI doesn't hang forever if the sidecar never came up.
 * Returns `null` on timeout so the caller can show an error state.
 */
export async function awaitSidecarReady(
  timeoutMs = 30_000,
  pollMs = 250,
): Promise<SidecarDiscovery | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      return await fetchSidecarDiscovery();
    } catch {
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
  }
  return null;
}
