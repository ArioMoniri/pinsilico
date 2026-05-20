import type { JSX } from "react";

import { useSessionStore } from "../stores/session";
import { useSceneStore } from "../stores/scene";

interface StatusBarProps {
  /** One-line transient status (e.g. "Running simulation…"). */
  message: string | null;
}

/**
 * Bottom status bar. Surfaces counts, current selection, and the most
 * recent action message so users always have orientation context
 * without needing to dig into panels.
 */
export function StatusBar({ message }: StatusBarProps): JSX.Element {
  const proteinCount = useSessionStore((s) => Object.keys(s.proteins).length);
  const ligandCount = useSessionStore((s) => Object.keys(s.ligands).length);
  const activeProtein = useSceneStore((s) => s.activeProteinId);
  const activePocket = useSceneStore((s) => s.activePocketId);

  return (
    <footer style={containerStyle} role="status">
      <span>
        🧬 {proteinCount} {proteinCount === 1 ? "protein" : "proteins"} · 💊 {ligandCount}{" "}
        {ligandCount === 1 ? "ligand" : "ligands"}
      </span>
      <span style={{ color: "#8b9097" }}>
        {activeProtein === null
          ? "No active protein"
          : `Active: ${activeProtein}${activePocket ? ` · pocket ${activePocket}` : ""}`}
      </span>
      <span style={{ color: "#8b9097", justifySelf: "end" }}>{message ?? "Ready"}</span>
    </footer>
  );
}

const containerStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "auto 1fr auto",
  gap: "1.5rem",
  alignItems: "center",
  padding: "0.35rem 1rem",
  background: "#0f1115",
  borderTop: "1px solid #20242b",
  color: "#b6bcc6",
  fontSize: "0.78rem",
  fontFamily: "ui-monospace, monospace",
};
