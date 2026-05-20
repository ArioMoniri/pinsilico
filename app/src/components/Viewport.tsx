import type { JSX } from "react";
import { Suspense, lazy, useMemo } from "react";

import { useSceneStore } from "../stores/scene";
import { useSessionStore } from "../stores/session";
import { Arena } from "./scene/arena/Arena";

const MolstarViewer = lazy(() =>
  import("./scene/molstar/MolstarViewer").then((m) => ({ default: m.MolstarViewer })),
);

interface ViewportProps {
  positions: Float32Array | null;
  bound: boolean[];
}

/**
 * 3D viewport switcher. Renders the abstract Arena or the atomistic
 * Mol* viewer depending on the active view in the scene store.
 *
 * When no proteins are loaded, both views show a friendly empty state
 * so users get a clear next-step prompt instead of an empty canvas.
 */
export function Viewport({ positions, bound }: ViewportProps): JSX.Element {
  const view = useSceneStore((s) => s.view);
  const activeProteinId = useSceneStore((s) => s.activeProteinId);
  const proteins = useSessionStore((s) => s.proteins);
  const proteinEntries = useMemo(() => Object.values(proteins), [proteins]);

  if (proteinEntries.length === 0) {
    return (
      <div style={emptyStyle}>
        <div style={{ textAlign: "center", maxWidth: 480 }}>
          <h2 style={{ margin: "0 0 0.5rem", fontWeight: 600, color: "#e6e9ef" }}>
            No proteins loaded
          </h2>
          <p style={{ color: "#8b9097", lineHeight: 1.55 }}>
            Click <strong style={{ color: "#e6e9ef" }}>+ Add protein</strong> in the toolbar to load
            a PDB ID from RCSB, fetch a predicted structure from AlphaFold, or upload a local PDB
            file. The 3D viewport renders the protein in the abstract <em>Arena</em> view (R3F) or
            the atomistic <em>Mol*</em> view, switchable from the toolbar.
          </p>
        </div>
      </div>
    );
  }

  if (view === "arena") {
    return (
      <div style={canvasContainerStyle}>
        <Arena positions={positions ?? new Float32Array(0)} bound={bound} />
      </div>
    );
  }

  // Atomistic view — render the active protein. Falls back to the first
  // loaded protein if nothing is explicitly selected.
  const activeProtein =
    (activeProteinId !== null ? proteins[activeProteinId] : undefined) ?? proteinEntries[0];

  if (activeProtein === undefined) {
    return <div style={emptyStyle}>No protein selected.</div>;
  }

  return (
    <div style={canvasContainerStyle}>
      <Suspense
        fallback={<div style={{ ...emptyStyle, color: "#8b9097" }}>Loading atomistic viewer…</div>}
      >
        <MolstarViewer pdbText={activeProtein.pdb_text} />
      </Suspense>
    </div>
  );
}

const canvasContainerStyle: React.CSSProperties = {
  position: "relative",
  width: "100%",
  height: "100%",
  background: "#0a0c10",
  overflow: "hidden",
};

const emptyStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  background: "#0a0c10",
  padding: "2rem",
  color: "#e6e9ef",
};
