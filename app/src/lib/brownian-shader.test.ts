import { describe, expect, it } from "vitest";
import { BROWNIAN_WGSL, parseShaderMetadata } from "./brownian-shader";

describe("BROWNIAN_WGSL", () => {
  it("declares a compute entry point named main", () => {
    const md = parseShaderMetadata(BROWNIAN_WGSL);
    expect(md.entryPoint).toBe("main");
  });

  it("uses workgroup size 64 (a sane SIMD-friendly default)", () => {
    const md = parseShaderMetadata(BROWNIAN_WGSL);
    expect(md.workgroupSize).toBe(64);
  });

  it("declares a read_write particles binding and a uniforms binding", () => {
    expect(BROWNIAN_WGSL).toMatch(/var<storage, read_write> particles/);
    expect(BROWNIAN_WGSL).toMatch(/var<uniform> u/);
  });

  it("includes the box-wall clamp matching CPU semantics", () => {
    expect(BROWNIAN_WGSL).toMatch(/clamp\(pos\.x, -half, half\)/);
  });

  it("includes the bound→released transition matching CPU semantics", () => {
    expect(BROWNIAN_WGSL).toMatch(/p\.bound_site_id = -1/);
  });
});

describe("parseShaderMetadata", () => {
  it("rejects shaders without @compute fn", () => {
    expect(() => parseShaderMetadata("// no compute")).toThrow();
  });

  it("rejects shaders without @workgroup_size", () => {
    expect(() => parseShaderMetadata("@compute fn main() {}")).toThrow();
  });
});
