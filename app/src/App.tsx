import { APP_VERSION } from "./lib/version";

/**
 * Phase 0 placeholder. Renders a single label matching the Tauri window
 * title. Phase 7 replaces this with the full workspace shell + routes.
 */
export function App(): JSX.Element {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: "#1a1a1a",
        background: "#fafafa",
      }}
    >
      <h1 style={{ margin: 0, fontWeight: 600 }}>PInSilico</h1>
      <p style={{ margin: "0.5rem 0 0", opacity: 0.6 }}>v{APP_VERSION}</p>
    </main>
  );
}
