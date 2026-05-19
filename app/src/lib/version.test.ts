import { describe, expect, it } from "vitest";
import { APP_VERSION } from "./version";

/**
 * Phase 0 smoke test for the TS-side version constant. Anchors the
 * cross-stack version sync (Cargo.toml / Cargo CARGO_PKG_VERSION /
 * package.json / pyproject.toml / tauri.conf.json / __init__.py).
 *
 * Phase 7 adds component tests; Phase 12 packaging adds the CI six-way
 * version check that ties these literals together.
 */
describe("APP_VERSION", () => {
  it("matches the Phase 0 release", () => {
    expect(APP_VERSION).toBe("0.0.1");
  });

  it("is a literal semver-like string", () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+(-[0-9A-Za-z-]+)?$/);
  });
});
