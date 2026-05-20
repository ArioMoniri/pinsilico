import { useEffect, useMemo, useState, type JSX } from "react";

import { ApiError, PinsilicoClient, type FastForwardResponse } from "../lib/api";
import { awaitSidecarReady } from "../lib/tauri";
import { useSessionStore } from "../stores/session";
import { ProteinPanel } from "./panels/ProteinPanel";
import { LigandPanel } from "./panels/LigandPanel";
import { SimPanel, type SimPanelValues } from "./panels/SimPanel";
import { Toolbar, type SidecarStatus } from "./Toolbar";
import { StatusBar } from "./StatusBar";
import { Viewport } from "./Viewport";
import { AddProteinDialog } from "./dialogs/AddProteinDialog";
import { AddLigandDialog } from "./dialogs/AddLigandDialog";

/**
 * Phase 7 workspace shell.
 *
 * Layout:
 *
 *   ┌─────────────────────── Toolbar ───────────────────────┐
 *   │ Title · view switch · sidecar pill · + Add            │
 *   ├──────────────┬─────────────────────────┬──────────────┤
 *   │ ProteinPanel │ 3D Viewport             │ SimPanel     │
 *   │  (300 px)    │  (Arena | Mol*)         │  (320 px)    │
 *   ├──────────────┴─────────────────────────┴──────────────┤
 *   │ StatusBar: counts · active · last message            │
 *   └───────────────────────────────────────────────────────┘
 *
 * Sidecar bootstrap:
 *   1. On mount, poll the Rust IPC commands until the four-line banner
 *      has been parsed.
 *   2. Store the apiBase + token in the session store and build a
 *      `PinsilicoClient` for the dialog + sim runner to use.
 *   3. If the sidecar never comes up (e.g. dev mode without
 *      build_sidecar.py having run), the toolbar pill turns red and
 *      data-loading actions show a "sidecar not connected" inline error.
 */
export function Workspace(): JSX.Element {
  const setConnection = useSessionStore((s) => s.setConnection);
  const apiBase = useSessionStore((s) => s.apiBase);
  const token = useSessionStore((s) => s.token);

  const [sidecarStatus, setSidecarStatus] = useState<SidecarStatus>("connecting");
  const [sidecarVersion, setSidecarVersion] = useState<string | null>(null);
  const [addProteinOpen, setAddProteinOpen] = useState(false);
  const [addLigandOpen, setAddLigandOpen] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [, setLastResult] = useState<FastForwardResponse | null>(null);
  const [detectingProteinId, setDetectingProteinId] = useState<string | null>(null);
  const [trajectoryPositions, setTrajectoryPositions] = useState<Float32Array | null>(null);
  const [trajectoryBound, setTrajectoryBound] = useState<boolean[]>([]);

  // Initial sidecar handshake. Re-runs only if dependencies change
  // (which they don't here — this is mount-once). A successful IPC
  // handshake is itself proof the sidecar process is alive, the
  // banner was fully parsed, and the API base + token are valid —
  // we don't run a separate /health HTTP probe here because that
  // round-trip is subject to webview CORS / macOS ATS rules that can
  // fail-closed even when the sidecar is healthy. Real API calls
  // (e.g. /db/rcsb in AddProteinDialog) surface fetch failures
  // inline with the action that triggered them.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const discovery = await awaitSidecarReady();
      if (cancelled) return;
      if (discovery === null) {
        setSidecarStatus("error");
        setStatusMessage("Sidecar did not respond. Run `python scripts/build_sidecar.py` if dev.");
        return;
      }
      setConnection(discovery.apiBase, discovery.token);
      setSidecarVersion(discovery.version);
      setSidecarStatus("ready");
      setStatusMessage("Connected.");
    })();
    return () => {
      cancelled = true;
    };
  }, [setConnection]);

  const client = useMemo<PinsilicoClient | null>(() => {
    if (apiBase === null || token === null) return null;
    return new PinsilicoClient({ apiBase, token });
  }, [apiBase, token]);

  // Run fpocket on a single protein and fold the resulting pockets
  // back into the session store. The button on each protein card
  // calls this; sim runs use the pockets here as binding sites.
  const onDetectPockets = (proteinId: string): void => {
    if (client === null) {
      setStatusMessage("Sidecar not connected — can't detect pockets.");
      return;
    }
    const protein = useSessionStore.getState().proteins[proteinId];
    if (protein === undefined) return;
    setDetectingProteinId(proteinId);
    setStatusMessage(`Detecting pockets in ${proteinId}…`);
    void client
      .pocketDetect(protein.pdb_text)
      .then((result) => {
        useSessionStore.getState().setProteinPockets(proteinId, result.pockets);
        setStatusMessage(`Detected ${result.pockets.length} pocket(s) in ${proteinId}.`);
      })
      .catch((e: unknown) => {
        setStatusMessage(
          e instanceof ApiError ? `${e.code}: ${e.message}` : "Pocket detection failed.",
        );
      })
      .finally(() => {
        setDetectingProteinId(null);
      });
  };

  // Synchronous simulation run via /sim/run. Returns the final particle
  // positions which we feed into the Arena viewport for visualisation.
  // Live SSE streaming lands in a future phase.
  const onSimTrajectoryRun = (values: SimPanelValues): void => {
    if (client === null) {
      setStatusMessage("Sidecar not connected — can't run simulation.");
      return;
    }
    const proteins = useSessionStore.getState().proteins;
    const sites = Object.values(proteins).flatMap((p) =>
      p.pockets.map((pk) => ({
        identifier: `${p.identifier}/${pk.identifier}`,
        centroid_xyz: pk.centroid_xyz,
        radius_a: Math.cbrt((3 * pk.volume_a3) / (4 * Math.PI)),
        dg_kcal_mol: -4 - 6 * pk.druggability_score,
      })),
    );
    if (sites.length === 0) {
      setStatusMessage("No detected pockets yet — load a protein and detect pockets first.");
      return;
    }
    // Seed the simulator with a random particle cloud so the Arena
    // has something to integrate against. The sidecar accepts a
    // particles[] field; we drop 64 starting positions in a box.
    const rng = mulberry32(values.seed);
    const boxHalf = 80;
    const particles = Array.from({ length: 64 }, () => ({
      position: [
        (rng() * 2 - 1) * boxHalf,
        (rng() * 2 - 1) * boxHalf,
        (rng() * 2 - 1) * boxHalf,
      ] as [number, number, number],
    }));
    setStatusMessage(`Integrating ${values.iterations} frames across ${sites.length} sites…`);
    void client
      .simRun({
        sites,
        particles,
        temperature_k: values.temperatureK,
        seed: values.seed,
        n_frames: Math.min(values.iterations, 100_000),
        use_attraction: values.useAttraction,
        mode: values.mode,
      })
      .then((result) => {
        const flat = new Float32Array(result.final_positions.length * 3);
        result.final_positions.forEach(([x, y, z], i) => {
          flat[3 * i] = x;
          flat[3 * i + 1] = y;
          flat[3 * i + 2] = z;
        });
        setTrajectoryPositions(flat);
        setTrajectoryBound(result.bound_site_ids.map((s) => s !== null));
        const boundCount = result.bound_site_ids.filter((s) => s !== null).length;
        setStatusMessage(
          `${result.frames_executed} frames · ${boundCount}/${particles.length} particles bound.`,
        );
      })
      .catch((e: unknown) => {
        setStatusMessage(e instanceof ApiError ? `${e.code}: ${e.message}` : "Simulation failed.");
      });
  };

  const onSimRun = (values: SimPanelValues): void => {
    if (client === null) {
      setStatusMessage("Sidecar not connected — can't run simulation.");
      return;
    }
    // Phase 7c minimal sim integration: fast-forward against whichever
    // proteins have detected pockets. A no-pocket scenario shows an
    // inline message rather than a silent no-op.
    const proteins = useSessionStore.getState().proteins;
    // Derive site fields the sim API needs but PocketResponse doesn't
    // expose directly. Volume → spherical radius; druggability score
    // (0..1) → a placeholder ΔG between -4 (poor) and -10 kcal/mol
    // (strong). v1.2 should replace this with a real Boltz/Smina-cached
    // ΔG per pocket — for v1.1 this keeps the sim runner usable
    // end-to-end without a separate docking step.
    const sites = Object.values(proteins).flatMap((p) =>
      p.pockets.map((pk) => ({
        identifier: `${p.identifier}/${pk.identifier}`,
        centroid_xyz: pk.centroid_xyz,
        radius_a: Math.cbrt((3 * pk.volume_a3) / (4 * Math.PI)),
        dg_kcal_mol: -4 - 6 * pk.druggability_score,
      })),
    );
    if (sites.length === 0) {
      setStatusMessage("No detected pockets yet — load a protein and detect pockets first.");
      return;
    }
    setStatusMessage(`Running ${values.iterations} events across ${sites.length} sites…`);
    void client
      .simFastForward({
        sites,
        temperature_k: values.temperatureK,
        seed: values.seed,
        n_events: values.iterations,
      })
      .then((result) => {
        setLastResult(result);
        const top = Object.entries(result.counts).sort(([, a], [, b]) => b - a)[0];
        setStatusMessage(
          top !== undefined
            ? `${result.n_events} events sampled · top site ${top[0]} (${top[1]} hits)`
            : `${result.n_events} events sampled.`,
        );
      })
      .catch((e: unknown) => {
        setStatusMessage(e instanceof ApiError ? `${e.code}: ${e.message}` : "Simulation failed.");
      });
  };

  return (
    <div style={shellStyle}>
      <Toolbar
        sidecarStatus={sidecarStatus}
        sidecarVersion={sidecarVersion}
        onAddProtein={() => {
          setAddProteinOpen(true);
        }}
      />

      <div style={bodyStyle}>
        <aside style={leftPanelStyle}>
          <ProteinPanel
            onOpenAddDialog={() => {
              setAddProteinOpen(true);
            }}
            onDetectPockets={onDetectPockets}
            detectingProteinId={detectingProteinId}
          />
          <LigandPanel
            onOpenAddDialog={() => {
              setAddLigandOpen(true);
            }}
          />
        </aside>

        <main style={viewportStyle}>
          <Viewport positions={trajectoryPositions} bound={trajectoryBound} />
        </main>

        <aside style={rightPanelStyle}>
          <SimPanel onRun={onSimTrajectoryRun} onFastForward={onSimRun} />
        </aside>
      </div>

      <StatusBar message={statusMessage} />

      <AddProteinDialog
        client={client}
        open={addProteinOpen}
        onClose={() => {
          setAddProteinOpen(false);
        }}
        onLoaded={(entry) => {
          setStatusMessage(`Loaded ${entry.identifier}.`);
        }}
      />

      <AddLigandDialog
        client={client}
        open={addLigandOpen}
        onClose={() => {
          setAddLigandOpen(false);
        }}
        onLoaded={(record) => {
          setStatusMessage(`Loaded ligand ${record.identifier}.`);
        }}
      />
    </div>
  );
}

const shellStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateRows: "auto 1fr auto",
  height: "100vh",
  width: "100vw",
  background: "#0a0c10",
  color: "#e6e9ef",
  fontFamily: "system-ui, -apple-system, sans-serif",
};

const bodyStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "300px 1fr 320px",
  minHeight: 0,
  overflow: "hidden",
};

const leftPanelStyle: React.CSSProperties = {
  background: "#13161c",
  borderRight: "1px solid #20242b",
  overflowY: "auto",
  minHeight: 0,
};

const viewportStyle: React.CSSProperties = {
  position: "relative",
  minWidth: 0,
  minHeight: 0,
};

const rightPanelStyle: React.CSSProperties = {
  background: "#13161c",
  borderLeft: "1px solid #20242b",
  overflowY: "auto",
  minHeight: 0,
};

// Tiny, deterministic PRNG for seeding the simulation particle cloud.
// Same algorithm used in the sidecar tests so the JS-side seed → initial
// positions mapping stays reproducible. Adapted from
// https://github.com/bryc/code/blob/master/jshash/PRNGs.md#mulberry32
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function next(): number {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
