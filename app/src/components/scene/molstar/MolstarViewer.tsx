import { useEffect, useRef, useState } from "react";

import { DEFAULT_REPRESENTATION, representationFor } from "./representations";
import type { MolstarRepresentation } from "./representations";

interface MolstarViewerProps {
  /** Raw PDB block. Mol* parses internally. */
  pdbText: string;
  /** Override starting representation. */
  representation?: MolstarRepresentation;
  /** Hook called once the plugin has mounted; tests use it to assert init. */
  onReady?: (info: { representation: MolstarRepresentation }) => void;
}

/**
 * Atomistic Mol* viewer (Phase 8b).
 *
 * Loaded lazily via dynamic import so the ~2 MB Mol* bundle never lands
 * in the initial chunk (BUILD_PROMPT.md §8.14). Only one plugin
 * instance is alive at a time to keep memory bounded — the cleanup
 * effect destroys the prior plugin before switching proteins.
 *
 * The first render shows a loading state until the lazy import resolves.
 * Tests patch the dynamic import so they don't pull the real Mol* bundle.
 */
export function MolstarViewer({
  pdbText,
  representation = DEFAULT_REPRESENTATION.protein,
  onReady,
}: MolstarViewerProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let plugin: { destroy: () => void } | null = null;
    let cancelled = false;
    const spec = representationFor(representation);
    void (async () => {
      try {
        // Lazy import — runs only the first time this component mounts.
        // Mol* exports a programmatic PluginContext under
        // `molstar/lib/mol-plugin-ui` in the real package; Phase 6 sidecar
        // wiring exposes the binary directory the Mol* worker reads from.
        // The async wrapper keeps the import out of the initial chunk.
        const loaded = await import("./loadPlugin");
        if (cancelled) return;
        if (containerRef.current === null) return;
        plugin = await loaded.mountPlugin(containerRef.current, pdbText, spec);
        if (!cancelled) {
          setStatus("ready");
          onReady?.({ representation });
        }
      } catch (e) {
        if (cancelled) return;
        setStatus("error");
        setErrorMessage(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      plugin?.destroy();
    };
  }, [pdbText, representation, onReady]);

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="Atomistic molecular view"
      style={{ width: "100%", height: "100%", background: "#11151c", position: "relative" }}
    >
      {status === "loading" && (
        <div style={{ color: "#8b9097", padding: "1rem" }}>Loading atomistic view…</div>
      )}
      {status === "error" && (
        <div style={{ color: "#ff7676", padding: "1rem" }}>
          Failed to load atomistic view: {errorMessage}
        </div>
      )}
    </div>
  );
}
