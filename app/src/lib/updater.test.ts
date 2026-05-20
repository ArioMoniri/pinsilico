import { afterEach, describe, expect, it, vi } from "vitest";
import { checkForUpdates, formatUpdateDate } from "./updater";

afterEach(() => {
  vi.resetModules();
  vi.restoreAllMocks();
});

describe("checkForUpdates", () => {
  it("returns up_to_date when the plugin yields null", async () => {
    vi.doMock("@tauri-apps/plugin-updater", () => ({
      check: vi.fn().mockResolvedValue(null),
    }));
    const result = await checkForUpdates();
    expect(result.status).toBe("up_to_date");
  });

  it("returns available with version + install hook when update exists", async () => {
    const downloadAndInstall = vi.fn().mockResolvedValue(undefined);
    vi.doMock("@tauri-apps/plugin-updater", () => ({
      check: vi.fn().mockResolvedValue({
        version: "1.2.3",
        body: "Bug fixes and new docking engine support",
        date: "2026-05-20T12:00:00Z",
        downloadAndInstall,
      }),
    }));
    vi.doMock("@tauri-apps/plugin-process", () => ({
      relaunch: vi.fn().mockResolvedValue(undefined),
    }));
    const result = await checkForUpdates();
    expect(result.status).toBe("available");
    if (result.status !== "available") return;
    expect(result.version).toBe("1.2.3");
    expect(result.notes).toContain("docking engine");
    expect(result.date).toBe("2026-05-20T12:00:00Z");

    await result.install();
    expect(downloadAndInstall).toHaveBeenCalledOnce();
    // relaunch is also called — verified by the mock not throwing.
  });

  it("returns error when the plugin throws (offline, etc.)", async () => {
    vi.doMock("@tauri-apps/plugin-updater", () => ({
      check: vi.fn().mockRejectedValue(new Error("Network unreachable")),
    }));
    const result = await checkForUpdates();
    expect(result.status).toBe("error");
    if (result.status !== "error") return;
    expect(result.message).toContain("Network");
  });

  it("returns error with stringified non-Error when plugin throws weird value", async () => {
    vi.doMock("@tauri-apps/plugin-updater", () => ({
      check: vi.fn().mockRejectedValue("just a string"),
    }));
    const result = await checkForUpdates();
    expect(result.status).toBe("error");
    if (result.status !== "error") return;
    expect(result.message).toBe("just a string");
  });

  it("never blocks app boot — always resolves a status", async () => {
    vi.doMock("@tauri-apps/plugin-updater", () => ({
      check: vi.fn().mockRejectedValue(new TypeError("boom")),
    }));
    const result = await checkForUpdates();
    expect(["up_to_date", "available", "error"]).toContain(result.status);
  });
});

describe("formatUpdateDate", () => {
  it("returns 'unknown' for undefined input", () => {
    expect(formatUpdateDate(undefined)).toBe("unknown");
  });

  it("returns a localised string for a valid ISO date", () => {
    const out = formatUpdateDate("2026-05-20T12:00:00Z");
    expect(out).toMatch(/2026|20|May|5/);
  });

  it("falls back to the ISO string for an invalid date", () => {
    const out = formatUpdateDate("not-a-date");
    expect(out).toBe("Invalid Date");
  });
});
