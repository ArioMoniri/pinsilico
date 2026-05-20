import type { JSX } from "react";

import { Workspace } from "./components/Workspace";

/**
 * Application root.
 *
 * Phase 0 shipped a literal title placeholder here; Phase 7 swaps it
 * for the full {@link Workspace} shell — toolbar, three-pane layout
 * (proteins · 3D viewport · simulation), and a status bar.
 */
export function App(): JSX.Element {
  return <Workspace />;
}
