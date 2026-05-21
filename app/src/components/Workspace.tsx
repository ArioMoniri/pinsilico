import { useCallback, useEffect, useMemo, useState, type JSX } from "react";

import {
  ApiError,
  PinsilicoClient,
  type FastForwardResponse,
  type SessionLoadResponse,
} from "../lib/api";
import { awaitSidecarReady } from "../lib/tauri";
import { buildExampleKit } from "../lib/example_kit";
import { useSessionStore } from "../stores/session";
import { ProteinPanel } from "./panels/ProteinPanel";
import { LigandPanel } from "./panels/LigandPanel";
import { SimPanel, type SimPanelValues } from "./panels/SimPanel";
import { Toolbar, type SidecarStatus } from "./Toolbar";
import { StatusBar } from "./StatusBar";
import { Viewport } from "./Viewport";
import { ErrorBoundary } from "./ErrorBoundary";
import { AddProteinDialog } from "./dialogs/AddProteinDialog";
import { AddLigandDialog } from "./dialogs/AddLigandDialog";
import { DockingDialog } from "./dialogs/DockingDialog";
import { FixerDialog } from "./dialogs/FixerDialog";
import { SettingsDialog } from "./dialogs/SettingsDialog";

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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [dockingOpen, setDockingOpen] = useState(false);
  const [fixerOpen, setFixerOpen] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [, setLastResult] = useState<FastForwardResponse | null>(null);
  const [detectingProteinId, setDetectingProteinId] = useState<string | null>(null);
  const [trajectoryPositions, setTrajectoryPositions] = useState<Float32Array | null>(null);
  const [trajectoryBound, setTrajectoryBound] = useState<boolean[]>([]);

  // Sidecar handshake — runs at mount and is also called by the
  // FixerDialog's Retry button. A successful IPC handshake is itself
  // proof the sidecar process is alive, the banner was fully parsed,
  // and the API base + token are valid — we don't run a separate
  // /health HTTP probe here because that round-trip is subject to
  // webview CORS / macOS ATS rules that can fail-closed even when the
  // sidecar is healthy. Real API calls (e.g. /db/rcsb in
  // AddProteinDialog) surface fetch failures inline with the action
  // that triggered them.
  const runHandshake = useCallback(async (): Promise<boolean> => {
    setSidecarStatus("connecting");
    setStatusMessage("Connecting to sidecar…");
    const discovery = await awaitSidecarReady();
    if (discovery === null) {
      setSidecarStatus("error");
      setStatusMessage("Sidecar did not respond. Run `python scripts/build_sidecar.py` if dev.");
      return false;
    }
    setConnection(discovery.apiBase, discovery.token);
    setSidecarVersion(discovery.version);
    setSidecarStatus("ready");
    setStatusMessage("Connected.");
    return true;
  }, [setConnection]);

  useEffect(() => {
    let cancelled = false;
    void runHandshake().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [runHandshake]);

  const client = useMemo<PinsilicoClient | null>(() => {
    if (apiBase === null || token === null) return null;
    return new PinsilicoClient({ apiBase, token });
  }, [apiBase, token]);

  // Drop a small known-good protein + a few ligands into the session
  // store. The example kit is fully client-side (the PDB and SMILES
  // are bundled in `lib/example_kit.ts`) so it works even with the
  // sidecar offline — useful when the user wants to verify the UI
  // before troubleshooting the backend.
  const onLoadExampleKit = (): void => {
    const kit = buildExampleKit();
    const store = useSessionStore.getState();
    for (const p of kit.proteins) store.addProtein(p);
    for (const lig of kit.ligands) store.addLigand(lig);
    setStatusMessage(kit.blurb);
  };

  // Save the workspace to a deterministic `.pinsilico` bundle. The
  // sidecar serialises (it owns the zip-layout invariants) and returns
  // the bytes; we hand them to the browser as a Download.
  const onSaveSession = (): void => {
    if (client === null) {
      setStatusMessage("Sidecar not connected — can't save session.");
      return;
    }
    const state = useSessionStore.getState();
    const payload = {
      seed: 0,
      proteins: Object.values(state.proteins).map((p) => ({
        identifier: p.identifier,
        source: p.source,
        role: p.role,
        pdb_text: p.pdb_text,
        pockets: p.pockets.map((pk) => ({
          identifier: pk.identifier,
          centroid_xyz: pk.centroid_xyz,
          volume_a3: pk.volume_a3,
          hydrophobicity: pk.hydrophobicity,
          druggability_score: pk.druggability_score,
          residue_ids: pk.residue_ids,
        })),
      })),
      ligands: Object.values(state.ligands).map((lig) => ({
        identifier: lig.identifier,
        source: lig.source,
        smiles: lig.smiles,
        is_inhibitor: lig.is_inhibitor,
        is_natural_ligand: lig.is_natural_ligand,
      })),
    };
    setStatusMessage("Saving session…");
    void client
      .sessionSave(payload)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `pinsilico-session.pinsilico`;
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        setStatusMessage("Session saved.");
      })
      .catch((e: unknown) => {
        setStatusMessage(e instanceof ApiError ? `${e.code}: ${e.message}` : "Save failed.");
      });
  };

  // Open a `.pinsilico` bundle. The sidecar parses (it owns the zip
  // invariants) and returns JSON; we replace the session-store state
  // wholesale.
  const onLoadSession = (): void => {
    if (client === null) {
      setStatusMessage("Sidecar not connected — can't load session.");
      return;
    }
    const picker = document.createElement("input");
    picker.type = "file";
    picker.accept = ".pinsilico,application/zip";
    picker.addEventListener("change", () => {
      const file = picker.files?.[0];
      if (file === undefined) return;
      setStatusMessage(`Loading ${file.name}…`);
      void client
        .sessionLoad(file)
        .then((bundle: SessionLoadResponse) => {
          const store = useSessionStore.getState();
          store.reset();
          for (const p of bundle.proteins) {
            store.addProtein({
              identifier: p.identifier,
              source: p.source as "rcsb" | "alphafold" | "upload",
              role: p.role as "target" | "homolog" | "off_target",
              pdb_text: p.pdb_text,
              pockets: p.pockets.map((pk) => ({
                identifier: pk.identifier,
                centroid_xyz: pk.centroid_xyz,
                volume_a3: pk.volume_a3 ?? 0,
                hydrophobicity: pk.hydrophobicity ?? 0,
                druggability_score: pk.druggability_score ?? 0,
                residue_ids: pk.residue_ids ?? [],
              })),
            });
          }
          for (const lig of bundle.ligands) {
            store.addLigand({
              identifier: lig.identifier,
              source: lig.source as "pubchem" | "chembl" | "drugbank" | "upload",
              smiles: lig.smiles,
              is_inhibitor: lig.is_inhibitor,
              is_natural_ligand: lig.is_natural_ligand,
            });
          }
          setStatusMessage(
            `Loaded ${bundle.proteins.length} protein(s) and ${bundle.ligands.length} ligand(s).`,
          );
        })
        .catch((e: unknown) => {
          setStatusMessage(e instanceof ApiError ? `${e.code}: ${e.message}` : "Load failed.");
        });
    });
    picker.click();
  };

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
        if (e instanceof ApiError && e.message.includes("fpocket binary not found")) {
          setStatusMessage(
            "fpocket isn't bundled in this release. Install it manually (apt/brew + build from source) and set FPOCKET_BIN, or use the Example kit which ships a pre-detected pocket.",
          );
        } else {
          setStatusMessage(
            e instanceof ApiError ? `${e.code}: ${e.message}` : "Pocket detection failed.",
          );
        }
      })
      .finally(() => {
        setDetectingProteinId(null);
      });
  };

  // Live-streamed simulation run. The sidecar yields one SSE frame
  // per (downsampled) integration step; we update the Arena positions
  // as each frame arrives so the user sees real-time playback rather
  // than a "compute then teleport" jump. Falls back to /sim/run for
  // browsers without streaming-body fetch support.
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
    // Seed the simulator with a random particle cloud centred near
    // the first site so the swarm renders inside the camera frustum
    // from frame 1 (Arena's default camera frames the protein at
    // radius ≈ 12 Å). 200 particles in a ±18 Å box gives a visible
    // cloud without overwhelming the InstancedMesh.
    const rng = mulberry32(values.seed);
    const halfBox = 18;
    const firstSite = sites[0]?.centroid_xyz ?? [0, 0, 0];
    const particles = Array.from({ length: 200 }, () => ({
      position: [
        firstSite[0] + (rng() * 2 - 1) * halfBox,
        firstSite[1] + (rng() * 2 - 1) * halfBox,
        firstSite[2] + (rng() * 2 - 1) * halfBox,
      ] as [number, number, number],
    }));

    // Seed the Arena buffer immediately so the user sees the initial
    // cloud the moment they hit Run, not only after the first sim
    // frame lands over SSE.
    const initialFlat = new Float32Array(particles.length * 3);
    particles.forEach((p, i) => {
      initialFlat[3 * i] = p.position[0];
      initialFlat[3 * i + 1] = p.position[1];
      initialFlat[3 * i + 2] = p.position[2];
    });
    setTrajectoryPositions(initialFlat);
    setTrajectoryBound(new Array(particles.length).fill(false));
    setStatusMessage(`Streaming ${values.iterations} frames across ${sites.length} sites…`);
    const req = {
      sites,
      particles,
      temperature_k: values.temperatureK,
      seed: values.seed,
      n_frames: Math.min(values.iterations, 100_000),
      use_attraction: values.useAttraction,
      mode: values.mode,
    };
    // Smooth-playback shim: the WKWebView buffers `fetch` body chunks
    // aggressively, so SSE frames often arrive in a single burst when
    // the request completes. Without this, the Arena would jump from
    // the initial cloud straight to the final state and the user sees
    // "nothing happens" followed by a teleport. We interpolate locally
    // between the last delivered frame and the new one over ~120 ms
    // per frame so the swarm always reads as moving, regardless of
    // how the underlying stream is buffered.
    let lastFlat: Float32Array = initialFlat;
    let lastBound: boolean[] = new Array(particles.length).fill(false);
    let animFrame: number | null = null;
    let framesSeen = 0;

    const animateTo = (target: Float32Array, bound: boolean[], durationMs: number): void => {
      if (animFrame !== null) cancelAnimationFrame(animFrame);
      const start = performance.now();
      const from = lastFlat;
      const step = (now: number): void => {
        const t = Math.min(1, (now - start) / durationMs);
        const lerp = new Float32Array(target.length);
        for (let i = 0; i < target.length; i++) {
          lerp[i] = (from[i] ?? 0) * (1 - t) + (target[i] ?? 0) * t;
        }
        setTrajectoryPositions(lerp);
        if (t < 1) {
          animFrame = requestAnimationFrame(step);
        } else {
          lastFlat = target;
          lastBound = bound;
          setTrajectoryBound(bound);
          animFrame = null;
        }
      };
      animFrame = requestAnimationFrame(step);
    };

    void client
      .simStream(req, (frame) => {
        framesSeen += 1;
        const flat = new Float32Array(frame.positions.length * 3);
        frame.positions.forEach(([x, y, z], i) => {
          flat[3 * i] = x;
          flat[3 * i + 1] = y;
          flat[3 * i + 2] = z;
        });
        animateTo(flat, frame.bound, 120);
      })
      .then((total) => {
        const boundCount = lastBound.filter(Boolean).length;
        setStatusMessage(
          `Sim done — ${total} frames over ${framesSeen} updates · ${boundCount}/${particles.length} particles bound`,
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
        onSaveSession={onSaveSession}
        onLoadSession={onLoadSession}
        onOpenSettings={() => {
          setSettingsOpen(true);
        }}
        onOpenFixer={() => {
          setFixerOpen(true);
        }}
        onLoadExampleKit={onLoadExampleKit}
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
            onOpenDocking={() => {
              setDockingOpen(true);
            }}
          />
        </aside>

        <main style={viewportStyle}>
          <ErrorBoundary label="3D viewport">
            <Viewport positions={trajectoryPositions} bound={trajectoryBound} />
          </ErrorBoundary>
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

      <FixerDialog
        open={fixerOpen}
        onClose={() => {
          setFixerOpen(false);
        }}
        lastError={sidecarStatus === "error" ? statusMessage : null}
        onRetry={runHandshake}
      />

      <DockingDialog
        client={client}
        open={dockingOpen}
        onClose={() => {
          setDockingOpen(false);
        }}
      />

      <SettingsDialog
        open={settingsOpen}
        onClose={() => {
          setSettingsOpen(false);
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
