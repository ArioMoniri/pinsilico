import { useEffect, type JSX } from "react";

import { pickRenderer, rendererLabel } from "../../lib/renderer";
import { useSettingsStore } from "../../stores/settings";

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Settings dialog. v1.3 exposes only the renderer preference; later
 * phases add theme + telemetry toggles.
 */
export function SettingsDialog({ open, onClose }: SettingsDialogProps): JSX.Element | null {
  const rendererPreference = useSettingsStore((s) => s.rendererPreference);
  const rendererTier = useSettingsStore((s) => s.rendererTier);
  const setRendererPreference = useSettingsStore((s) => s.setRendererPreference);
  const setRendererTier = useSettingsStore((s) => s.setRendererTier);

  // Re-run detection whenever the user picks a different preference.
  // The result drives Arena's pipeline choice on next mount.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void pickRenderer(rendererPreference).then((result) => {
      if (!cancelled) setRendererTier(result.tier);
    });
    return () => {
      cancelled = true;
    };
  }, [open, rendererPreference, setRendererTier]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      style={backdropStyle}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div style={panelStyle}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Settings</h2>
          <button type="button" onClick={onClose} aria-label="Close" style={iconButtonStyle}>
            ×
          </button>
        </header>

        <fieldset style={fieldsetStyle}>
          <legend style={legendStyle}>Renderer (Arena view)</legend>
          {(["auto", "webgpu", "webgl2"] as const).map((p) => (
            <label key={p} style={radioRowStyle}>
              <input
                type="radio"
                name="renderer-preference"
                checked={rendererPreference === p}
                onChange={() => {
                  setRendererPreference(p);
                }}
              />
              <span>
                {p === "auto" ? "Auto" : p === "webgpu" ? "WebGPU (compute)" : "WebGL2 (fallback)"}
              </span>
            </label>
          ))}
          <p style={hintStyle}>
            {rendererTier === null ? "Detecting…" : `Active tier: ${rendererLabel(rendererTier)}`}.
            Auto picks WebGPU when the system advertises a working adapter; otherwise falls back to
            WebGL2.
          </p>
        </fieldset>

        <footer style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.75rem" }}>
          <button type="button" onClick={onClose} style={primaryButtonStyle}>
            Done
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
  width: "min(440px, calc(100vw - 4rem))",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.6)",
};

const fieldsetStyle: React.CSSProperties = {
  border: "1px solid #2a2f38",
  borderRadius: 4,
  padding: "0.6rem 0.8rem",
  margin: "0.75rem 0 0.4rem",
};

const legendStyle: React.CSSProperties = { padding: "0 0.3rem", fontSize: "0.85rem" };

const radioRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.4rem",
  padding: "0.2rem 0",
  fontSize: "0.88rem",
};

const hintStyle: React.CSSProperties = {
  color: "#8b9097",
  fontSize: "0.78rem",
  marginTop: "0.5rem",
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

const iconButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "none",
  fontSize: "1.4rem",
  cursor: "pointer",
  lineHeight: 1,
};
