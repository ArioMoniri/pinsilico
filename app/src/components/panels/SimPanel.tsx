import { useState } from "react";
import type { JSX } from "react";

export type SimMode = "inhibitor_only" | "ligand_only" | "competition";
export type AnimationStyle = "arena" | "atomistic";

export interface SimPanelValues {
  mode: SimMode;
  inhibitorConcentrationUM: number;
  ligandConcentrationUM: number;
  iterations: number;
  seed: number;
  animationStyle: AnimationStyle;
  useAttraction: boolean;
  temperatureK: number;
  playbackSpeed: number;
}

interface SimPanelProps {
  initial?: Partial<SimPanelValues>;
  onRun: (values: SimPanelValues) => void;
  onFastForward?: (values: SimPanelValues) => void;
}

const DEFAULTS: SimPanelValues = {
  mode: "competition",
  inhibitorConcentrationUM: 10.0,
  ligandConcentrationUM: 50.0,
  iterations: 1000,
  seed: 42,
  animationStyle: "arena",
  useAttraction: true,
  temperatureK: 298.15,
  playbackSpeed: 1,
};

export function SimPanel({ initial, onRun, onFastForward }: SimPanelProps): JSX.Element {
  const [values, setValues] = useState<SimPanelValues>({ ...DEFAULTS, ...(initial ?? {}) });

  const update = <K extends keyof SimPanelValues>(k: K, v: SimPanelValues[K]): void => {
    setValues((s) => ({ ...s, [k]: v }));
  };

  return (
    <section aria-label="Simulation controls" style={{ padding: "0.75rem" }}>
      <h2 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>Simulation</h2>

      <fieldset style={fieldsetStyle}>
        <legend style={legendStyle}>Mode</legend>
        {(["inhibitor_only", "ligand_only", "competition"] as const).map((m) => (
          <label key={m} style={radioLabelStyle}>
            <input
              type="radio"
              name="sim-mode"
              checked={values.mode === m}
              onChange={() => {
                update("mode", m);
              }}
            />
            {m.replace("_", " ")}
          </label>
        ))}
      </fieldset>

      <label style={fieldStyle}>
        Inhibitor concentration (µM)
        <input
          type="number"
          min={0}
          step={0.01}
          value={values.inhibitorConcentrationUM}
          onChange={(e) => {
            update("inhibitorConcentrationUM", Number(e.target.value));
          }}
          aria-label="Inhibitor concentration in micromolar"
        />
      </label>

      <label style={fieldStyle}>
        Ligand concentration (µM)
        <input
          type="number"
          min={0}
          step={0.01}
          value={values.ligandConcentrationUM}
          onChange={(e) => {
            update("ligandConcentrationUM", Number(e.target.value));
          }}
          aria-label="Ligand concentration in micromolar"
        />
      </label>

      <label style={fieldStyle}>
        Iterations
        <input
          type="number"
          min={1}
          max={100000}
          step={1}
          value={values.iterations}
          onChange={(e) => {
            update("iterations", Number(e.target.value));
          }}
          aria-label="Number of iterations"
        />
      </label>

      <label style={fieldStyle}>
        Seed
        <input
          type="number"
          value={values.seed}
          onChange={(e) => {
            update("seed", Number(e.target.value));
          }}
          aria-label="Deterministic seed"
        />
      </label>

      <label style={fieldStyle}>
        Temperature (K)
        <input
          type="number"
          min={200}
          max={400}
          step={0.05}
          value={values.temperatureK}
          onChange={(e) => {
            update("temperatureK", Number(e.target.value));
          }}
          aria-label="Temperature in kelvin"
        />
      </label>

      <fieldset style={fieldsetStyle}>
        <legend style={legendStyle}>Animation</legend>
        {(["arena", "atomistic"] as const).map((a) => (
          <label key={a} style={radioLabelStyle}>
            <input
              type="radio"
              name="anim-style"
              checked={values.animationStyle === a}
              onChange={() => {
                update("animationStyle", a);
              }}
            />
            {a}
          </label>
        ))}
      </fieldset>

      <label style={{ ...fieldStyle, flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
        <input
          type="checkbox"
          checked={values.useAttraction}
          onChange={(e) => {
            update("useAttraction", e.target.checked);
          }}
          aria-label="Use encounter-potential acceleration"
        />
        <span title="Weak attractive shift toward unoccupied pockets. NOT real electrostatics — see docs/physics-model.md">
          Use encounter potential
        </span>
      </label>

      <label style={fieldStyle}>
        Playback speed
        <select
          value={values.playbackSpeed}
          onChange={(e) => {
            update("playbackSpeed", Number(e.target.value));
          }}
          aria-label="Playback speed"
        >
          {[0.25, 0.5, 1, 2, 4].map((r) => (
            <option key={r} value={r}>
              {r}x
            </option>
          ))}
        </select>
      </label>

      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
        <button
          type="button"
          onClick={() => {
            onRun(values);
          }}
          style={primaryButtonStyle}
        >
          Run
        </button>
        {onFastForward !== undefined && (
          <button
            type="button"
            onClick={() => {
              onFastForward(values);
            }}
            style={panelButtonStyle}
          >
            Fast-forward
          </button>
        )}
      </div>
    </section>
  );
}

export { DEFAULTS as DEFAULT_SIM_VALUES };

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
  margin: "0.5rem 0",
};

const fieldsetStyle: React.CSSProperties = {
  border: "1px solid #2a2f38",
  borderRadius: 4,
  padding: "0.4rem 0.6rem",
  margin: "0.5rem 0",
};

const legendStyle: React.CSSProperties = { padding: "0 0.3rem", fontSize: "0.85rem" };
const radioLabelStyle: React.CSSProperties = { display: "block", padding: "0.15rem 0" };

const panelButtonStyle: React.CSSProperties = {
  background: "#1d2129",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  padding: "0.4rem 0.8rem",
  borderRadius: 4,
  cursor: "pointer",
};

const primaryButtonStyle: React.CSSProperties = {
  ...panelButtonStyle,
  background: "#3d6eb8",
  borderColor: "#5483c9",
  fontWeight: 600,
};
