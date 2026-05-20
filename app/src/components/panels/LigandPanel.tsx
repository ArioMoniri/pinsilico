import type { JSX } from "react";

import type { LigandRecord } from "../../stores/session";
import { useSessionStore } from "../../stores/session";

interface LigandPanelProps {
  /** Opened by the workspace when the user clicks "Add ligand". */
  onOpenAddDialog?: () => void;
}

/**
 * Ligand library panel. Mirrors {@link ProteinPanel}: lists each loaded
 * ligand with its provenance + SMILES preview, exposes an inhibitor
 * toggle, and a remove button. The workspace owns the API client; this
 * panel only renders the session-store slice.
 */
export function LigandPanel({ onOpenAddDialog }: LigandPanelProps): JSX.Element {
  const ligands = useSessionStore((s) => s.ligands);
  const removeLigand = useSessionStore((s) => s.removeLigand);
  const toggleInhibitor = useSessionStore((s) => s.toggleInhibitor);

  const entries = Object.values(ligands);

  return (
    <section aria-label="Ligand library" style={{ padding: "0.75rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "0.95rem" }}>Ligands ({entries.length})</h2>
        <button
          type="button"
          onClick={onOpenAddDialog}
          aria-label="Add ligand"
          style={panelButtonStyle}
        >
          + Add
        </button>
      </header>
      {entries.length === 0 ? (
        <p style={{ color: "#8b9097", marginTop: "0.5rem" }}>
          No ligands loaded. Click <em>Add</em> to import a SMILES string, fetch from ChEMBL /
          PubChem / DrugBank, or upload an SDF file.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0" }}>
          {entries.map((l: LigandRecord) => (
            <li
              key={l.identifier}
              style={{
                padding: "0.5rem 0",
                borderBottom: "1px solid #20242b",
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: "0.5rem",
                alignItems: "start",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div>
                  <strong>{l.identifier}</strong>
                  <small style={{ color: "#8b9097", marginLeft: "0.4rem" }}>{l.source}</small>
                  {l.is_natural_ligand && (
                    <small style={natTagStyle} aria-label="Natural ligand">
                      natural
                    </small>
                  )}
                </div>
                <code style={smilesStyle} title={l.smiles}>
                  {l.smiles}
                </code>
                <label style={inhibitorRowStyle}>
                  <input
                    type="checkbox"
                    checked={l.is_inhibitor}
                    onChange={() => {
                      toggleInhibitor(l.identifier);
                    }}
                    aria-label={`Treat ${l.identifier} as an inhibitor`}
                  />
                  <span>Inhibitor candidate</span>
                </label>
              </div>
              <button
                type="button"
                onClick={() => {
                  removeLigand(l.identifier);
                }}
                aria-label={`Remove ${l.identifier}`}
                style={panelButtonStyle}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const panelButtonStyle: React.CSSProperties = {
  background: "#1d2129",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  padding: "0.25rem 0.6rem",
  borderRadius: 4,
  cursor: "pointer",
};

const smilesStyle: React.CSSProperties = {
  display: "block",
  fontSize: "0.72rem",
  color: "#8b9097",
  fontFamily: "ui-monospace, monospace",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  marginTop: "0.15rem",
};

const inhibitorRowStyle: React.CSSProperties = {
  display: "flex",
  gap: "0.4rem",
  alignItems: "center",
  marginTop: "0.3rem",
  fontSize: "0.78rem",
  color: "#b6bcc6",
};

const natTagStyle: React.CSSProperties = {
  background: "#1b3a26",
  color: "#7bd99c",
  border: "1px solid #2e6e44",
  padding: "0.05rem 0.35rem",
  borderRadius: 999,
  fontSize: "0.65rem",
  marginLeft: "0.4rem",
};
