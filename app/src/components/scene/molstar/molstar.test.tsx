import { describe, expect, it } from "vitest";
import { DEFAULT_REPRESENTATION, representationFor } from "./representations";
import { findFirstBindingIndex, interpolateLigandFrames } from "./trajectory";
import type { LigandFrame } from "./trajectory";

describe("DEFAULT_REPRESENTATION", () => {
  it("matches the BUILD_PROMPT preset", () => {
    expect(DEFAULT_REPRESENTATION.protein).toBe("cartoon");
    expect(DEFAULT_REPRESENTATION.ligand).toBe("ball-and-stick");
    expect(DEFAULT_REPRESENTATION.pocketResidues).toBe("ball-and-stick");
    expect(DEFAULT_REPRESENTATION.surfaceOverlay).toBe(true);
  });
});

describe("representationFor", () => {
  it("surface view disables the overlay (avoid drawing surface twice)", () => {
    expect(representationFor("surface").surfaceOverlay).toBe(false);
  });

  it("ball-and-stick view keeps the surface overlay on", () => {
    expect(representationFor("ball-and-stick").surfaceOverlay).toBe(true);
  });

  it("ligand and pocket-residue representations stay constant", () => {
    for (const view of ["cartoon", "surface", "ball-and-stick"] as const) {
      const spec = representationFor(view);
      expect(spec.ligand).toBe("ball-and-stick");
      expect(spec.pocketResidues).toBe("ball-and-stick");
    }
  });
});

const FRAMES: LigandFrame[] = [
  { index: 0, com: [0, 0, 0], bound: false },
  { index: 1, com: [4, 0, 0], bound: false },
  { index: 2, com: [4, 0, 0], bound: true },
  { index: 3, com: [4, 0, 0], bound: true },
  { index: 4, com: [10, 0, 0], bound: false },
];

describe("interpolateLigandFrames", () => {
  it("identity at playbackRate=1", () => {
    const out = interpolateLigandFrames(FRAMES, 1);
    expect(out).toHaveLength(FRAMES.length);
    expect(out[0]!.com).toEqual([0, 0, 0]);
    expect(out[4]!.com).toEqual([10, 0, 0]);
  });

  it("rejects non-positive playback rate", () => {
    expect(() => interpolateLigandFrames(FRAMES, 0)).toThrow(/playbackRate/);
    expect(() => interpolateLigandFrames(FRAMES, -1)).toThrow();
  });

  it("returns empty list for empty input", () => {
    expect(interpolateLigandFrames([], 1)).toEqual([]);
  });

  it("playbackRate=2 produces ~2x the number of frames", () => {
    const out = interpolateLigandFrames(FRAMES, 2);
    expect(out.length).toBeGreaterThanOrEqual(FRAMES.length * 2 - 1);
  });

  it("bound state snaps at transitions, no flicker mid-event", () => {
    const out = interpolateLigandFrames(FRAMES, 4);
    // No frame should have bound=true with com strictly between frames 1 and 2
    for (const f of out) {
      if (f.bound) {
        // x must be the bound x (4) once bound
        expect(f.com[0]).toBeCloseTo(4, 1);
      }
    }
  });
});

describe("findFirstBindingIndex", () => {
  it("locates the free→bound transition", () => {
    expect(findFirstBindingIndex(FRAMES)).toBe(2);
  });

  it("returns -1 when no binding occurs", () => {
    expect(
      findFirstBindingIndex([
        { index: 0, com: [0, 0, 0], bound: false },
        { index: 1, com: [1, 0, 0], bound: false },
      ]),
    ).toBe(-1);
  });
});
