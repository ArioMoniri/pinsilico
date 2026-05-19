/**
 * Lazy-loaded Mol* mounting helper.
 *
 * Split out of MolstarViewer.tsx so it can be replaced by a test stub
 * via `vi.mock`. The real implementation uses the molstar package's
 * `createPluginUI` (or the headless `PluginContext` API the spec
 * prefers); Phase 9 fills in the full implementation. This file ships
 * the seam — when the real implementation lands, MolstarViewer doesn't
 * need to change.
 */

import type { RepresentationSpec } from "./representations";

/** Handle returned to the React component for teardown. */
export interface MolstarHandle {
  destroy: () => void;
}

/**
 * Mount a Mol* plugin into `container`, load `pdbText`, and apply the
 * representation preset.
 *
 * Phase 8b ships a stub: throws unless overridden in tests. Phase 9
 * fills in the real molstar call. Splitting the seam now means
 * MolstarViewer's effect/cleanup contract is settled and locked.
 */
export async function mountPlugin(
  container: HTMLDivElement,
  pdbText: string,
  spec: RepresentationSpec,
): Promise<MolstarHandle> {
  // Suppress unused-param lint while keeping the symbols visible in the
  // signature for Phase 9 wiring.
  void container;
  void pdbText;
  void spec;
  throw new Error(
    "Mol* plugin mount lands with Phase 9 atomistic-view wiring; this stub is for the seam only.",
  );
}
