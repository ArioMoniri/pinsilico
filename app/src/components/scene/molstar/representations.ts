/**
 * Pure-function representation preset for the Mol* viewer.
 *
 * Kept separate from MolstarViewer so the deterministic mapping
 * `(view-mode) → representation-spec` is unit-testable without spinning
 * up a Mol* plugin instance.
 */

export type MolstarRepresentation = "cartoon" | "surface" | "ball-and-stick";

export interface RepresentationSpec {
  protein: MolstarRepresentation;
  ligand: MolstarRepresentation;
  pocketResidues: MolstarRepresentation;
  /** Translucent surface overlay on top of the cartoon. */
  surfaceOverlay: boolean;
}

/**
 * The Phase 8 default preset: protein cartoon, ligand ball-and-stick,
 * pocket residues as sticks, optional translucent surface overlay.
 * BUILD_PROMPT.md §8.b spells this out explicitly.
 */
export const DEFAULT_REPRESENTATION: Readonly<RepresentationSpec> = Object.freeze({
  protein: "cartoon",
  ligand: "ball-and-stick",
  pocketResidues: "ball-and-stick",
  surfaceOverlay: true,
});

/** Picker invoked by the atomistic-view toolbar. */
export function representationFor(view: MolstarRepresentation): RepresentationSpec {
  return {
    protein: view,
    ligand: "ball-and-stick",
    pocketResidues: "ball-and-stick",
    surfaceOverlay: view !== "surface",
  };
}
