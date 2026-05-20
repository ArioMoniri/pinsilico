import { useState, type JSX } from "react";

interface FixerDialogProps {
  open: boolean;
  onClose: () => void;
  /** Latest diagnostic message from the workspace boot — surfaced verbatim. */
  lastError: string | null;
  /**
   * Retry the sidecar handshake. Returns true when the IPC channel
   * comes back up; the dialog flips to a "Connected" state and
   * auto-dismisses on success.
   */
  onRetry: () => Promise<boolean>;
}

/**
 * "Sidecar offline" fixer.
 *
 * Opens from the toolbar pill (red) or the status bar when the sidecar
 * handshake fails. Walks the user through the canonical recovery path:
 *
 *   1. Show what we tried + what came back (no log scraping needed).
 *   2. Retry button (re-runs `awaitSidecarReady` without reloading).
 *   3. Hint about `python scripts/build_sidecar.py` for dev builds.
 *   4. Link to the GitHub issue tracker for users who hit a real bug.
 *
 * Most "Sidecar offline" reports we've seen are stale dev builds where
 * the PyInstaller bundle was missing — a single Retry usually fixes it
 * once the user has run the build script.
 */
export function FixerDialog({
  open,
  onClose,
  lastError,
  onRetry,
}: FixerDialogProps): JSX.Element | null {
  const [retrying, setRetrying] = useState(false);
  const [outcome, setOutcome] = useState<"idle" | "success" | "still-offline">("idle");

  if (!open) return null;

  const retry = async (): Promise<void> => {
    setOutcome("idle");
    setRetrying(true);
    const ok = await onRetry();
    setRetrying(false);
    setOutcome(ok ? "success" : "still-offline");
    if (ok) {
      // Give the user a beat to see the green tick before auto-close.
      setTimeout(() => {
        onClose();
        setOutcome("idle");
      }, 800);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Fix sidecar"
      style={backdropStyle}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div style={panelStyle}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Fix sidecar</h2>
          <button type="button" onClick={onClose} aria-label="Close" style={iconButtonStyle}>
            ×
          </button>
        </header>

        <p style={paraStyle}>
          The Python sidecar didn&apos;t respond. PInSilico can run docking, fpocket, and the
          simulation engine only when the sidecar is reachable — the React workspace alone can show
          structures and ligands, but everything that needs computation will be disabled until the
          connection comes back.
        </p>

        <section style={sectionStyle}>
          <h3 style={h3Style}>Last error</h3>
          <pre style={preStyle}>{lastError ?? "(no message recorded)"}</pre>
        </section>

        <section style={sectionStyle}>
          <h3 style={h3Style}>What this usually means</h3>
          <ul style={ulStyle}>
            <li>
              <strong>Stale dev build:</strong> the Rust shell couldn&apos;t find the bundled
              sidecar binary. From a checkout, run{" "}
              <code style={codeStyle}>python scripts/build_sidecar.py</code> once, then click{" "}
              <em>Retry</em> below (no app restart needed if the spawn succeeds on the second try).
            </li>
            <li>
              <strong>PyInstaller bundle is broken:</strong> the spawned sidecar exited before
              emitting its four-line banner. Rebuild with the same command above, then retry.
            </li>
            <li>
              <strong>macOS quarantined the bundled binary:</strong> first launch of a
              freshly-downloaded <code style={codeStyle}>.dmg</code> can stall the sidecar behind
              Gatekeeper. Quit and reopen the app once.
            </li>
          </ul>
        </section>

        {outcome === "success" && <p style={successStyle}>✓ Sidecar reconnected.</p>}
        {outcome === "still-offline" && (
          <p style={errorBoxStyle}>
            Still offline. Check the <em>Last error</em> above; if the message is the same, you
            likely need to rebuild the sidecar bundle.
          </p>
        )}

        <footer
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.5rem",
            marginTop: "0.75rem",
          }}
        >
          <a
            href="https://github.com/ArioMoniri/pinsilico/issues"
            target="_blank"
            rel="noreferrer"
            style={secondaryLinkStyle}
          >
            Report a bug
          </a>
          <button type="button" onClick={onClose} style={secondaryButtonStyle}>
            Close
          </button>
          <button
            type="button"
            onClick={() => {
              void retry();
            }}
            disabled={retrying}
            style={primaryButtonStyle}
          >
            {retrying ? "Retrying…" : "Retry connection"}
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
  width: "min(540px, calc(100vw - 4rem))",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.6)",
};

const paraStyle: React.CSSProperties = {
  color: "#b6bcc6",
  fontSize: "0.88rem",
  marginTop: "0.6rem",
  lineHeight: 1.55,
};

const sectionStyle: React.CSSProperties = { marginTop: "0.6rem" };

const h3Style: React.CSSProperties = {
  margin: "0 0 0.3rem",
  fontSize: "0.82rem",
  color: "#8b9097",
  fontWeight: 500,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const preStyle: React.CSSProperties = {
  margin: 0,
  padding: "0.5rem 0.6rem",
  background: "#0a0c10",
  border: "1px solid #20242b",
  borderRadius: 4,
  color: "#f0a0a0",
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.75rem",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const ulStyle: React.CSSProperties = {
  margin: "0 0 0 1rem",
  padding: 0,
  fontSize: "0.85rem",
  color: "#b6bcc6",
  lineHeight: 1.55,
};

const codeStyle: React.CSSProperties = {
  background: "#0a0c10",
  padding: "0.05rem 0.3rem",
  borderRadius: 3,
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.82rem",
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

const secondaryLinkStyle: React.CSSProperties = {
  ...secondaryButtonStyle,
  textDecoration: "none",
  display: "inline-block",
};

const iconButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "none",
  fontSize: "1.4rem",
  cursor: "pointer",
  lineHeight: 1,
};

const successStyle: React.CSSProperties = {
  background: "#1b3a26",
  color: "#7bd99c",
  border: "1px solid #2e6e44",
  padding: "0.4rem 0.6rem",
  borderRadius: 4,
  marginTop: "0.5rem",
  fontSize: "0.85rem",
};

const errorBoxStyle: React.CSSProperties = {
  background: "#3b1c1c",
  color: "#f0a0a0",
  border: "1px solid #7a3535",
  padding: "0.4rem 0.6rem",
  borderRadius: 4,
  marginTop: "0.5rem",
  fontSize: "0.85rem",
};
