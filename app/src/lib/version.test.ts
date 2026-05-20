import { describe, expect, it } from "vitest";
import { APP_VERSION } from "./version";

/**
 * Smoke test for the TS-side version constant. Anchors the cross-stack
 * version sync (Cargo.toml / package.json / tauri.conf.json /
 * pyproject.toml / __init__.py / version.ts).
 *
 * Avoids hard-coding the literal so future bumps don't have to touch
 * the test. The six-way version sync is enforced separately by
 * `scripts/release.py`'s `assert_versions_agree()`, which release.yml
 * and auto-release.yml both run.
 */
describe("APP_VERSION", () => {
  it("is a literal semver-like string", () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+(-[0-9A-Za-z-]+)?$/);
  });

  it("is non-empty and a constant", () => {
    expect(APP_VERSION).toBeTruthy();
    expect(typeof APP_VERSION).toBe("string");
  });
});
