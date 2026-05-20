import type { JSX } from "react";

import { useSceneStore } from "../stores/scene";
import { APP_VERSION } from "../lib/version";

export type SidecarStatus = "connecting" | "ready" | "error";

interface ToolbarProps {
  sidecarStatus: SidecarStatus;
  sidecarVersion: string | null;
  onAddProtein: () => void;
}

/**
 * Top toolbar.
 *
 * Hosts the product title, the arena ↔ atomistic view switcher, the
 * sidecar connection pill, and the "Add protein" entry point.
 */
export function Toolbar({
  sidecarStatus,
  sidecarVersion,
  onAddProtein,
}: ToolbarProps): JSX.Element {
  const view = useSceneStore((s) => s.view);
  const setView = useSceneStore((s) => s.setView);

  return (
    <header style={containerStyle}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
        <h1 style={titleStyle}>PInSilico</h1>
        <span style={versionStyle}>v{APP_VERSION}</span>
      </div>

      <nav aria-label="3D view" style={{ display: "flex", gap: "0.25rem" }}>
        {(["arena", "atomistic"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => {
              setView(v);
            }}
            aria-pressed={view === v}
            style={view === v ? viewButtonActiveStyle : viewButtonStyle}
          >
            {v === "arena" ? "Arena" : "Atomistic"}
          </button>
        ))}
      </nav>

      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <SidecarPill status={sidecarStatus} version={sidecarVersion} />
        <button type="button" onClick={onAddProtein} style={primaryButtonStyle}>
          + Add protein
        </button>
      </div>
    </header>
  );
}

function SidecarPill({
  status,
  version,
}: {
  status: SidecarStatus;
  version: string | null;
}): JSX.Element {
  const palette = {
    connecting: { bg: "#3d3a17", border: "#6e6a30", text: "#f0d97b", label: "Connecting…" },
    ready: {
      bg: "#1b3a26",
      border: "#2e6e44",
      text: "#7bd99c",
      label: `Sidecar v${version ?? "?"}`,
    },
    error: { bg: "#3b1c1c", border: "#7a3535", text: "#f0a0a0", label: "Sidecar offline" },
  }[status];
  return (
    <span
      role="status"
      aria-label={`Sidecar ${status}`}
      style={{
        background: palette.bg,
        border: `1px solid ${palette.border}`,
        color: palette.text,
        padding: "0.2rem 0.6rem",
        borderRadius: 999,
        fontSize: "0.78rem",
        fontFamily: "ui-monospace, monospace",
      }}
    >
      ● {palette.label}
    </span>
  );
}

const containerStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "auto 1fr auto",
  alignItems: "center",
  gap: "1.5rem",
  padding: "0.6rem 1rem",
  background: "#0f1115",
  borderBottom: "1px solid #20242b",
  color: "#e6e9ef",
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
  fontWeight: 600,
  letterSpacing: "0.01em",
};

const versionStyle: React.CSSProperties = {
  fontSize: "0.78rem",
  color: "#8b9097",
  fontFamily: "ui-monospace, monospace",
};

const viewButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "1px solid #2a2f38",
  padding: "0.3rem 0.85rem",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: "0.85rem",
};

const viewButtonActiveStyle: React.CSSProperties = {
  ...viewButtonStyle,
  background: "#1d2129",
  color: "#e6e9ef",
  borderColor: "#3d6eb8",
};

const primaryButtonStyle: React.CSSProperties = {
  background: "#3d6eb8",
  color: "#fff",
  border: "1px solid #5483c9",
  padding: "0.35rem 0.85rem",
  borderRadius: 4,
  cursor: "pointer",
  fontWeight: 600,
  fontSize: "0.85rem",
};
