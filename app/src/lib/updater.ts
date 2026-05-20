/**
 * Auto-updater wrapper.
 *
 * Hides the `@tauri-apps/plugin-updater` API behind a small typed
 * surface so:
 *   - Components don't have to know the plugin's exception shape.
 *   - Tests stub the underlying plugin via vi.mock("@tauri-apps/plugin-updater").
 *
 * The plugin queries `tauri.conf.json`'s `plugins.updater.endpoints`,
 * verifies the signed manifest against the embedded public key, and
 * downloads the new bundle. After install we call
 * `@tauri-apps/plugin-process`'s `relaunch()` to apply the update.
 */

export interface UpdateAvailable {
  status: "available";
  version: string;
  notes: string;
  /** ISO timestamp from the manifest's `pub_date`. */
  date: string | undefined;
  /** Triggers download + install + relaunch. */
  install: () => Promise<void>;
}

export interface UpdateUpToDate {
  status: "up_to_date";
}

export interface UpdateError {
  status: "error";
  message: string;
}

export type UpdateCheckResult = UpdateAvailable | UpdateUpToDate | UpdateError;

/**
 * Check the configured endpoint for a newer signed bundle.
 *
 * Returns one of three states; never throws. Surface the result in
 * the Settings panel or a toast — never block app boot on an updater
 * failure (offline, GitHub rate-limited, etc.).
 */
export async function checkForUpdates(): Promise<UpdateCheckResult> {
  try {
    const { check } = await import("@tauri-apps/plugin-updater");
    const update = await check();
    if (update === null) {
      return { status: "up_to_date" };
    }
    return {
      status: "available",
      version: update.version,
      notes: update.body ?? "",
      date: update.date,
      install: async () => {
        await update.downloadAndInstall();
        // Apply the update by relaunching. The plugin-process module
        // is the canonical way; relaunch() returns when the new
        // process is launching, then the current one exits cleanly.
        const { relaunch } = await import("@tauri-apps/plugin-process");
        await relaunch();
      },
    };
  } catch (e) {
    return {
      status: "error",
      message: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * Stable label for the Settings panel's "Last checked" copy.
 *
 * Renders the localised date; falls back to the ISO string if the
 * browser can't format the value (legacy WebKit on Linux runners).
 */
export function formatUpdateDate(iso: string | undefined): string {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
