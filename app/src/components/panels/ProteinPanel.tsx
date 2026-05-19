import type { JSX } from "react";

import type { ProteinRecord, ProteinRole } from "../../stores/session";
import { useSessionStore } from "../../stores/session";

const ROLES: { value: ProteinRole; label: string }[] = [
  { value: "target", label: "Target" },
  { value: "homolog", label: "Homolog" },
  { value: "off_target", label: "Off-target" },
];

interface ProteinPanelProps {
  /** Opened by the workspace when the user clicks "Add protein". */
  onOpenAddDialog?: () => void;
}

export function ProteinPanel({ onOpenAddDialog }: ProteinPanelProps): JSX.Element {
  const proteins = useSessionStore((s) => s.proteins);
  const addProtein = useSessionStore((s) => s.addProtein);
  const removeProtein = useSessionStore((s) => s.removeProtein);

  const entries = Object.values(proteins);

  const setRole = (id: string, role: ProteinRole): void => {
    const current = proteins[id];
    if (current === undefined) return;
    addProtein({ ...current, role });
  };

  return (
    <section aria-label="Protein library" style={{ padding: "0.75rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "0.95rem" }}>Proteins ({entries.length})</h2>
        <button
          type="button"
          onClick={onOpenAddDialog}
          aria-label="Add protein"
          style={panelButtonStyle}
        >
          + Add
        </button>
      </header>
      {entries.length === 0 ? (
        <p style={{ color: "#8b9097", marginTop: "0.5rem" }}>
          No proteins loaded. Click <em>Add</em> to load a PDB file or search RCSB / AlphaFold.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0" }}>
          {entries.map((p: ProteinRecord) => (
            <li
              key={p.identifier}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto auto",
                gap: "0.5rem",
                padding: "0.4rem 0",
                borderBottom: "1px solid #20242b",
              }}
            >
              <span>
                <strong>{p.identifier}</strong>
                <small style={{ color: "#8b9097", marginLeft: "0.4rem" }}>
                  {p.source} · {p.pockets.length} pockets
                </small>
              </span>
              <select
                value={p.role}
                onChange={(e) => {
                  setRole(p.identifier, e.target.value as ProteinRole);
                }}
                aria-label={`Role for ${p.identifier}`}
                style={smallSelectStyle}
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  removeProtein(p.identifier);
                }}
                aria-label={`Remove ${p.identifier}`}
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

const smallSelectStyle: React.CSSProperties = {
  background: "#1d2129",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  padding: "0.25rem 0.4rem",
  borderRadius: 4,
};
