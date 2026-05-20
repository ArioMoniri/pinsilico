import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  /** Subtree to protect. */
  children: ReactNode;
  /** Friendly label shown in the fallback UI ("Atomistic viewer", etc.). */
  label: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Localised React error boundary.
 *
 * Wraps a feature subtree so an exception inside (typically a third-
 * party lib like Mol* or React Three Fiber) renders a small inline
 * error card instead of crashing the whole workspace to a white page.
 * The user can dismiss the card via `Reset` to remount the children.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface the failure to the developer console for inspection;
    // production users see the fallback card.
    console.error(`[${this.props.label}] crashed:`, error, info);
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  override render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <div style={cardStyle} role="alert">
          <h3 style={headingStyle}>{this.props.label} crashed</h3>
          <pre style={preStyle}>{this.state.error.message}</pre>
          <button type="button" onClick={this.reset} style={buttonStyle}>
            Reset
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const cardStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  padding: "1.5rem",
  gap: "0.6rem",
  background: "#0a0c10",
  color: "#e6e9ef",
};

const headingStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "0.95rem",
  color: "#f0a0a0",
  fontWeight: 600,
};

const preStyle: React.CSSProperties = {
  margin: 0,
  maxWidth: "min(80ch, calc(100% - 2rem))",
  padding: "0.6rem 0.8rem",
  background: "#13161c",
  border: "1px solid #3b1c1c",
  borderRadius: 4,
  color: "#f0a0a0",
  fontFamily: "ui-monospace, monospace",
  fontSize: "0.8rem",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const buttonStyle: React.CSSProperties = {
  background: "#1d2129",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  padding: "0.3rem 0.85rem",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: "0.85rem",
};
