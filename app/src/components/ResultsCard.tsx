import type { JSX } from "react";

import type { FastForwardResponse } from "../lib/api";

interface ResultsCardProps {
  /** Last completed Fast-forward result, if any. */
  fastForward: FastForwardResponse | null;
  /** Last completed Run trajectory summary, if any. */
  run: { framesExecuted: number; boundCount: number; particleCount: number } | null;
  onDismiss: () => void;
}

/**
 * Results card.
 *
 * Floats over the bottom-right of the viewport when a sim run finishes.
 * The status bar only had room for a one-line summary; the card gives
 * users a glanceable histogram (Fast-forward) and a bound-fraction bar
 * (Run). Dismiss with the × button.
 */
export function ResultsCard({ fastForward, run, onDismiss }: ResultsCardProps): JSX.Element | null {
  if (fastForward === null && run === null) return null;

  return (
    <aside style={cardStyle} aria-label="Simulation results">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={titleStyle}>Last simulation</h3>
        <button type="button" onClick={onDismiss} aria-label="Dismiss results" style={dismissStyle}>
          ×
        </button>
      </header>

      {fastForward !== null && (
        <section style={sectionStyle}>
          <h4 style={subtitleStyle}>
            Fast-forward — {fastForward.n_events.toLocaleString()} events
          </h4>
          <ul style={listStyle}>
            {Object.entries(fastForward.counts)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([site, count]) => {
                const pct = (count / fastForward.n_events) * 100;
                return (
                  <li key={site} style={rowStyle}>
                    <span style={siteLabelStyle} title={site}>
                      {site}
                    </span>
                    <span style={barTrackStyle}>
                      <span style={{ ...barFillStyle, width: `${pct.toFixed(1)}%` }} />
                    </span>
                    <span style={countStyle}>{count.toLocaleString()}</span>
                  </li>
                );
              })}
          </ul>
        </section>
      )}

      {run !== null && (
        <section style={sectionStyle}>
          <h4 style={subtitleStyle}>Trajectory — {run.framesExecuted.toLocaleString()} frames</h4>
          <div style={statRowStyle}>
            <span style={statLabelStyle}>Particles bound</span>
            <span style={statValueStyle}>
              {run.boundCount} / {run.particleCount} (
              {((run.boundCount / Math.max(run.particleCount, 1)) * 100).toFixed(0)}%)
            </span>
          </div>
          <span style={barTrackStyle}>
            <span
              style={{
                ...barFillStyle,
                width: `${((run.boundCount / Math.max(run.particleCount, 1)) * 100).toFixed(1)}%`,
                background: "#ff8a4a",
              }}
            />
          </span>
        </section>
      )}
    </aside>
  );
}

const cardStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 12,
  right: 12,
  width: "min(360px, calc(100% - 24px))",
  background: "rgba(15, 17, 21, 0.96)",
  border: "1px solid #20242b",
  borderRadius: 8,
  padding: "0.7rem 0.85rem",
  color: "#e6e9ef",
  boxShadow: "0 6px 18px rgba(0, 0, 0, 0.55)",
  fontSize: "0.82rem",
  zIndex: 30,
};

const titleStyle: React.CSSProperties = { margin: 0, fontSize: "0.92rem", fontWeight: 600 };

const subtitleStyle: React.CSSProperties = {
  margin: "0 0 0.4rem",
  fontSize: "0.78rem",
  color: "#8b9097",
  fontWeight: 500,
};

const sectionStyle: React.CSSProperties = { marginTop: "0.55rem" };

const listStyle: React.CSSProperties = { listStyle: "none", margin: 0, padding: 0 };

const rowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 60px 50px",
  gap: "0.4rem",
  alignItems: "center",
  padding: "0.15rem 0",
};

const siteLabelStyle: React.CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.75rem",
};

const barTrackStyle: React.CSSProperties = {
  display: "inline-block",
  height: 6,
  background: "#20242b",
  borderRadius: 3,
  overflow: "hidden",
};

const barFillStyle: React.CSSProperties = {
  display: "block",
  height: "100%",
  background: "#3d6eb8",
};

const countStyle: React.CSSProperties = {
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.75rem",
  textAlign: "right",
  color: "#b6bcc6",
};

const statRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  marginBottom: "0.3rem",
};

const statLabelStyle: React.CSSProperties = { color: "#8b9097" };
const statValueStyle: React.CSSProperties = { fontFamily: "ui-monospace, monospace" };

const dismissStyle: React.CSSProperties = {
  background: "transparent",
  color: "#8b9097",
  border: "none",
  fontSize: "1.05rem",
  cursor: "pointer",
  lineHeight: 1,
  padding: "0 0.3rem",
};
