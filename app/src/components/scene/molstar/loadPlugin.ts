/**
 * Lazy-loaded Mol* mounting helper — Phase 9.
 *
 * Split out of MolstarViewer.tsx so it can be replaced by a test stub
 * via `vi.mock`. The real implementation here uses `createPluginUI`
 * from the molstar package: a full plugin context is mounted into the
 * supplied container, the PDB text is parsed into a trajectory, and
 * the default structure preset is applied with the representation the
 * caller passed.
 *
 * Tests mock this module so they don't pull the ~2 MB Mol* bundle.
 */

import { createPluginUI } from "molstar/lib/mol-plugin-ui";
import { renderReact18 } from "molstar/lib/mol-plugin-ui/react18";
import { DefaultPluginUISpec } from "molstar/lib/mol-plugin-ui/spec";
// Mol*'s default UI styling — without it the canvas renders but the
// overlay (camera controls, axes, loading indicator) is invisible and
// in some browsers the viewer collapses to a 0x0 box. The Vite build
// inlines this CSS into the main chunk, so there's no runtime fetch.
import "molstar/build/viewer/molstar.css";

import type { RepresentationSpec } from "./representations";

/** Handle returned to the React component for teardown. */
export interface MolstarHandle {
  destroy: () => void;
}

/**
 * Mount a Mol* plugin into `container`, load `pdbText`, and apply the
 * representation preset. Throws on any Mol* failure — the React caller
 * surfaces the message to the user.
 */
export async function mountPlugin(
  container: HTMLDivElement,
  pdbText: string,
  spec: RepresentationSpec,
): Promise<MolstarHandle> {
  // Defer mount by one animation frame. In React 18 strict mode the
  // effect that calls us fires twice back-to-back during dev mount;
  // without this defer Mol* can synchronously try to attach a node
  // whose previous instance is still mid-removal, throwing
  //   DOMException: The object can not be found here.
  // One rAF is enough to let React settle between the two passes;
  // production builds still benefit from the slightly delayed mount.
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

  // Bail if the container has already been detached (React unmounted
  // us during the rAF wait). The caller's cancellation flag will also
  // catch this on its end.
  if (!container.isConnected) {
    throw new Error("Mol* mount cancelled — container detached before init");
  }

  // Hide the heavy default chrome — the workspace already has its own
  // toolbar + panels and the Mol* sidebars would clash. Users still
  // get the viewport, axes, and camera controls.
  const plugin = await createPluginUI({
    target: container,
    render: renderReact18,
    spec: {
      ...DefaultPluginUISpec(),
      layout: {
        initial: {
          isExpanded: false,
          showControls: false,
          regionState: {
            left: "hidden",
            top: "hidden",
            right: "hidden",
            bottom: "hidden",
          },
        },
      },
    },
  });

  // Parse the PDB block as raw data, build a trajectory, then apply
  // the default 'auto' preset (cartoon + ligand surface + waters).
  const data = await plugin.builders.data.rawData({
    data: pdbText,
    label: "protein",
  });
  const trajectory = await plugin.builders.structure.parseTrajectory(data, "pdb");
  await plugin.builders.structure.hierarchy.applyPreset(trajectory, "default");

  // The representation spec ships in from Phase 8b. v1.1 honours
  // it only as a hint — `applyPreset('default')` produces a good
  // baseline view; Phase 10 will switch representation per-spec.
  void spec;

  return {
    destroy: () => {
      try {
        plugin.dispose();
      } catch {
        // Best-effort cleanup; if Mol*'s internals are already torn
        // down (rare race on rapid protein switching) we silence the
        // secondary error so the React unmount path stays clean.
      }
    },
  };
}
