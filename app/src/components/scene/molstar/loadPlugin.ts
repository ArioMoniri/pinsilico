/**
 * Mol* mount helper — headless `PluginContext.mount`.
 *
 * Previous versions wrapped Mol*'s React UI (`createPluginUI` from
 * `mol-plugin-ui`), but inside Tauri's WKWebView the combined React-18
 * + Mol*-internal-React mount sequence kept throwing a DOMException
 * (`The object can not be found here`) — a NOT_FOUND_ERR that
 * surfaced as a whitewashed viewport even with the rAF defer + the
 * outer ErrorBoundary. Switching to the headless `PluginContext` +
 * `mount(container)` API skips the React UI layer entirely and just
 * gives us the WebGL canvas + a plugin handle for loading data.
 *
 * Tradeoffs: no Mol* sidebars / structure tree / measurement tools.
 * The user gets the rotatable cartoon + the toolbar/Workspace
 * controls we provide. That's the right balance for v1.x — we own
 * the chrome, Mol* owns the rendering.
 */

import { PluginContext } from "molstar/lib/mol-plugin/context";
import { DefaultPluginSpec } from "molstar/lib/mol-plugin/spec";

import type { RepresentationSpec } from "./representations";

/** Handle returned to the React component for teardown. */
export interface MolstarHandle {
  destroy: () => void;
}

/**
 * Mount a headless Mol* plugin into `container`, load `pdbText`, and
 * apply the default 'auto' preset. Throws on any Mol* failure — the
 * React caller surfaces the message to the user.
 */
export async function mountPlugin(
  container: HTMLDivElement,
  pdbText: string,
  spec: RepresentationSpec,
): Promise<MolstarHandle> {
  // Defer one animation frame so React layout settles and the
  // container has its final dimensions before Mol* measures.
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  if (!container.isConnected) {
    throw new Error("Mol* mount cancelled — container detached before init");
  }

  const plugin = new PluginContext(DefaultPluginSpec());
  await plugin.init();
  // `mount(target)` does the canvas creation + attachment for us; no
  // need to call initContainer separately for this minimal-viewer use
  // case.
  plugin.mount(container);

  // Parse the PDB block as raw data → trajectory → default preset.
  const data = await plugin.builders.data.rawData({
    data: pdbText,
    label: "protein",
  });
  const trajectory = await plugin.builders.structure.parseTrajectory(data, "pdb");
  await plugin.builders.structure.hierarchy.applyPreset(trajectory, "default");

  // Honour representation spec as a hint only (v1.x).
  void spec;

  return {
    destroy: () => {
      try {
        plugin.dispose();
      } catch {
        // Best-effort cleanup; ignore DOMException from racing unmounts.
      }
    },
  };
}
