import { describe, expect, it } from "vitest";
import { pickRenderer, rendererLabel } from "./renderer";

describe("pickRenderer", () => {
  it("returns webgl2 when user forces it", async () => {
    const r = await pickRenderer("webgl2", { gpu: { requestAdapter: () => Promise.resolve({}) } });
    expect(r.tier).toBe("webgl2");
    expect(r.reason).toContain("user preference");
  });

  it("returns webgpu when user forces it AND adapter is present", async () => {
    const r = await pickRenderer("webgpu", { gpu: { requestAdapter: () => Promise.resolve({}) } });
    expect(r.tier).toBe("webgpu");
  });

  it("falls back to webgl2 when user forces webgpu but adapter is missing", async () => {
    const r = await pickRenderer("webgpu", {
      gpu: { requestAdapter: () => Promise.resolve(null) },
    });
    expect(r.tier).toBe("webgl2");
    expect(r.reason).toMatch(/forced webgpu/);
  });

  it("auto picks webgpu when an adapter exists", async () => {
    const r = await pickRenderer("auto", { gpu: { requestAdapter: () => Promise.resolve({}) } });
    expect(r.tier).toBe("webgpu");
  });

  it("auto falls back to webgl2 when navigator.gpu is missing", async () => {
    const r = await pickRenderer("auto", {});
    expect(r.tier).toBe("webgl2");
    expect(r.reason).toMatch(/no webgpu/i);
  });

  it("auto falls back to webgl2 when requestAdapter throws", async () => {
    const r = await pickRenderer("auto", {
      gpu: {
        requestAdapter: () => Promise.reject(new Error("driver crash")),
      },
    });
    expect(r.tier).toBe("webgl2");
  });

  it("auto falls back when adapter resolves to undefined", async () => {
    const r = await pickRenderer("auto", {
      gpu: { requestAdapter: () => Promise.resolve(undefined) },
    });
    expect(r.tier).toBe("webgl2");
  });
});

describe("rendererLabel", () => {
  it("labels each tier", () => {
    expect(rendererLabel("webgpu")).toMatch(/webgpu/i);
    expect(rendererLabel("webgl2")).toMatch(/webgl2/i);
  });
});
