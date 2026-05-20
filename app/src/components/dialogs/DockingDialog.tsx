import { useMemo, useState, type JSX } from "react";

import {
  ApiError,
  type DockingPose,
  type DockingRunResponse,
  type PinsilicoClient,
} from "../../lib/api";
import { useSessionStore } from "../../stores/session";

interface DockingDialogProps {
  client: PinsilicoClient | null;
  open: boolean;
  onClose: () => void;
}

/**
 * Smina / Vina docking dispatch dialog.
 *
 * Picks a receptor + pocket + ligand from the session store, sends them
 * to the sidecar's `/docking/run` route, and shows the top poses with
 * their binding affinities. The pocket centroid + radius (volume → sphere)
 * defines the docking box.
 *
 * v1.3 surfaces the Smina/Vina path only. DiffDock + Boltz-2 adapters
 * exist in the sidecar but need a model-weights workflow that lands
 * with v1.4.
 */
export function DockingDialog({ client, open, onClose }: DockingDialogProps): JSX.Element | null {
  const proteins = useSessionStore((s) => s.proteins);
  const ligands = useSessionStore((s) => s.ligands);

  const proteinEntries = useMemo(() => Object.values(proteins), [proteins]);
  const ligandEntries = useMemo(() => Object.values(ligands), [ligands]);

  const [engine, setEngine] = useState<"smina" | "vina">("smina");
  const [proteinId, setProteinId] = useState<string>("");
  const [pocketId, setPocketId] = useState<string>("");
  const [ligandId, setLigandId] = useState<string>("");
  const [exhaustiveness, setExhaustiveness] = useState(8);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [poses, setPoses] = useState<DockingPose[]>([]);

  const selectedProtein = proteinId === "" ? proteinEntries[0] : proteins[proteinId];
  const pocketChoices = selectedProtein?.pockets ?? [];
  const selectedPocket = pocketChoices.find((p) => p.identifier === pocketId) ?? pocketChoices[0];
  const selectedLigand = ligandId === "" ? ligandEntries[0] : ligands[ligandId];

  if (!open) return null;

  const close = (): void => {
    setError(null);
    setPoses([]);
    onClose();
  };

  const run = async (): Promise<void> => {
    setError(null);
    setPoses([]);
    if (client === null) {
      setError("Sidecar not connected.");
      return;
    }
    if (selectedProtein === undefined) {
      setError("Pick a protein with at least one detected pocket.");
      return;
    }
    if (selectedPocket === undefined) {
      setError("Detect pockets on this protein first.");
      return;
    }
    if (selectedLigand === undefined) {
      setError("Pick a ligand from the library.");
      return;
    }
    const radius = Math.cbrt((3 * selectedPocket.volume_a3) / (4 * Math.PI));
    const boxSize = Math.max(20, 2 * radius + 8);
    setRunning(true);
    try {
      const response: DockingRunResponse = await client.dockingRun({
        engine,
        receptor_pdb: selectedProtein.pdb_text,
        ligand_smiles: selectedLigand.smiles,
        center_xyz: selectedPocket.centroid_xyz,
        size_xyz: [boxSize, boxSize, boxSize],
        exhaustiveness,
      });
      setPoses(response.poses);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.code}: ${e.message}`);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("Docking failed.");
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Run docking"
      style={backdropStyle}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div style={panelStyle}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Run docking</h2>
          <button type="button" onClick={close} aria-label="Close" style={iconButtonStyle}>
            ×
          </button>
        </header>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.5rem",
            marginTop: "0.75rem",
          }}
        >
          <label style={fieldStyle}>
            Engine
            <select
              value={engine}
              onChange={(e) => {
                setEngine(e.target.value as "smina" | "vina");
              }}
              style={inputStyle}
              aria-label="Docking engine"
            >
              <option value="smina">Smina</option>
              <option value="vina">AutoDock Vina</option>
            </select>
          </label>
          <label style={fieldStyle}>
            Exhaustiveness
            <input
              type="number"
              min={1}
              max={64}
              value={exhaustiveness}
              onChange={(e) => {
                setExhaustiveness(Math.max(1, Math.min(64, Number(e.target.value))));
              }}
              style={inputStyle}
              aria-label="Exhaustiveness"
            />
          </label>

          <label style={fieldStyle}>
            Receptor
            <select
              value={selectedProtein?.identifier ?? ""}
              onChange={(e) => {
                setProteinId(e.target.value);
                setPocketId("");
              }}
              style={inputStyle}
              aria-label="Receptor protein"
            >
              {proteinEntries.length === 0 && <option value="">(no proteins loaded)</option>}
              {proteinEntries.map((p) => (
                <option key={p.identifier} value={p.identifier}>
                  {p.identifier} · {p.pockets.length} pockets
                </option>
              ))}
            </select>
          </label>

          <label style={fieldStyle}>
            Pocket
            <select
              value={selectedPocket?.identifier ?? ""}
              onChange={(e) => {
                setPocketId(e.target.value);
              }}
              style={inputStyle}
              aria-label="Receptor pocket"
              disabled={pocketChoices.length === 0}
            >
              {pocketChoices.length === 0 && <option value="">(detect pockets first)</option>}
              {pocketChoices.map((pk) => (
                <option key={pk.identifier} value={pk.identifier}>
                  {pk.identifier} (drug {pk.druggability_score.toFixed(2)})
                </option>
              ))}
            </select>
          </label>

          <label style={{ ...fieldStyle, gridColumn: "1 / -1" }}>
            Ligand
            <select
              value={selectedLigand?.identifier ?? ""}
              onChange={(e) => {
                setLigandId(e.target.value);
              }}
              style={inputStyle}
              aria-label="Ligand"
            >
              {ligandEntries.length === 0 && <option value="">(add a ligand first)</option>}
              {ligandEntries.map((l) => (
                <option key={l.identifier} value={l.identifier}>
                  {l.identifier} · {l.smiles.slice(0, 40)}
                  {l.smiles.length > 40 ? "…" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error !== null && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}

        {poses.length > 0 && (
          <section style={{ marginTop: "0.75rem" }}>
            <h3 style={{ margin: "0 0 0.4rem", fontSize: "0.88rem", color: "#b6bcc6" }}>
              Top poses
            </h3>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Rank</th>
                  <th style={thStyle}>Affinity (kcal/mol)</th>
                  <th style={thStyle}>RMSD lb</th>
                  <th style={thStyle}>RMSD ub</th>
                </tr>
              </thead>
              <tbody>
                {poses.map((p) => (
                  <tr key={p.rank}>
                    <td style={tdStyle}>{p.rank}</td>
                    <td style={tdStyle}>{p.affinity_kcal_mol.toFixed(2)}</td>
                    <td style={tdStyle}>{p.rmsd_lb.toFixed(2)}</td>
                    <td style={tdStyle}>{p.rmsd_ub.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        <footer
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.5rem",
            marginTop: "0.75rem",
          }}
        >
          <button type="button" onClick={close} style={secondaryButtonStyle}>
            Close
          </button>
          <button
            type="button"
            onClick={() => {
              void run();
            }}
            disabled={running}
            style={primaryButtonStyle}
          >
            {running ? "Running…" : "Dock"}
          </button>
        </footer>
      </div>
    </div>
  );
}

const backdropStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(8, 10, 14, 0.65)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 100,
};

const panelStyle: React.CSSProperties = {
  background: "#13161c",
  color: "#e6e9ef",
  border: "1px solid #20242b",
  borderRadius: 8,
  padding: "1rem",
  width: "min(640px, calc(100vw - 4rem))",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.6)",
};

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
};

const inputStyle: React.CSSProperties = {
  background: "#0f1115",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  borderRadius: 4,
  padding: "0.4rem 0.5rem",
  fontSize: "0.88rem",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.85rem",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "0.3rem 0.5rem",
  borderBottom: "1px solid #2a2f38",
  color: "#8b9097",
  fontWeight: 500,
};

const tdStyle: React.CSSProperties = {
  padding: "0.3rem 0.5rem",
  borderBottom: "1px solid #20242b",
  fontFamily: "ui-monospace, monospace",
};

const primaryButtonStyle: React.CSSProperties = {
  background: "#3d6eb8",
  color: "#fff",
  border: "1px solid #5483c9",
  padding: "0.4rem 1rem",
  borderRadius: 4,
  cursor: "pointer",
  fontWeight: 600,
};

const secondaryButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "1px solid #2a2f38",
  padding: "0.4rem 1rem",
  borderRadius: 4,
  cursor: "pointer",
};

const iconButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "none",
  fontSize: "1.4rem",
  cursor: "pointer",
  lineHeight: 1,
};

const errorStyle: React.CSSProperties = {
  background: "#3b1c1c",
  color: "#f0a0a0",
  border: "1px solid #7a3535",
  padding: "0.4rem 0.6rem",
  borderRadius: 4,
  marginTop: "0.5rem",
  fontSize: "0.85rem",
};
