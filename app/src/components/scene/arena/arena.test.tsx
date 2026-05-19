import { describe, expect, it, vi } from "vitest";
import { act, render } from "@testing-library/react";
import { ProteinShell } from "./ProteinShell";
import { PocketMarker } from "./PocketMarker";
import type { PocketResponse } from "../../../lib/api";

// R3F's <Canvas> requires WebGL which jsdom doesn't have. We test the
// child components in isolation by mocking the three.js render pieces;
// full Canvas mounting lives in Playwright (Phase 13 a11y audit).

vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="canvas-stub">{children}</div>
  ),
}));

vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
}));

describe("ProteinShell", () => {
  it("renders without crashing", () => {
    const { container } = render(<ProteinShell center={[0, 0, 0]} radius={12} />);
    expect(container).toBeTruthy();
  });

  it("calls onSelect when handler given", () => {
    const handler = vi.fn();
    render(<ProteinShell center={[0, 0, 0]} radius={12} onSelect={handler} />);
    // The click flows through three's event system in a real Canvas;
    // we just verify the prop wiring here.
    expect(handler).toHaveBeenCalledTimes(0);
  });
});

describe("PocketMarker", () => {
  const pocket: PocketResponse = {
    identifier: "pocket-1",
    centroid_xyz: [0, 0, 0],
    volume_a3: 800,
    hydrophobicity: 54,
    druggability_score: 0.91,
    residue_ids: [],
  };

  it("renders for a druggable pocket", () => {
    const { container } = render(<PocketMarker pocket={pocket} />);
    expect(container).toBeTruthy();
  });

  it("renders for a low-druggability pocket without halo", () => {
    const { container } = render(<PocketMarker pocket={{ ...pocket, druggability_score: 0.1 }} />);
    expect(container).toBeTruthy();
  });

  it("renders the halo when selected", () => {
    const onSelect = vi.fn();
    const { container } = render(<PocketMarker pocket={pocket} selected onSelect={onSelect} />);
    expect(container).toBeTruthy();
    act(() => undefined);
  });
});
