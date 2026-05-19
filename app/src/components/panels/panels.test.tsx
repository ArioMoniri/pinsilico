import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ProteinPanel } from "./ProteinPanel";
import { DEFAULT_SIM_VALUES, SimPanel } from "./SimPanel";
import { proteinFromEntry, useSessionStore } from "../../stores/session";

describe("ProteinPanel", () => {
  beforeEach(() => {
    act(() => useSessionStore.setState({ apiBase: null, token: null, proteins: {}, ligands: {} }));
  });
  afterEach(() => {
    cleanup();
  });

  it("renders empty state when no proteins are loaded", () => {
    render(<ProteinPanel />);
    expect(screen.getByText(/no proteins loaded/i)).toBeInTheDocument();
  });

  it("calls onOpenAddDialog when Add is clicked", () => {
    const onAdd = vi.fn();
    render(<ProteinPanel onOpenAddDialog={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add protein/i }));
    expect(onAdd).toHaveBeenCalledOnce();
  });

  it("lists proteins and removes them", () => {
    act(() =>
      useSessionStore.getState().addProtein(
        proteinFromEntry(
          {
            identifier: "1HSG",
            title: "",
            organism: null,
            resolution_angstrom: null,
            pdb_text: "HEADER\n",
          },
          "rcsb",
        ),
      ),
    );
    render(<ProteinPanel />);
    expect(screen.getByText("1HSG")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /remove 1HSG/i }));
    expect(useSessionStore.getState().proteins["1HSG"]).toBeUndefined();
  });

  it("changing the role select updates the store", () => {
    act(() =>
      useSessionStore.getState().addProtein(
        proteinFromEntry(
          {
            identifier: "1HSG",
            title: "",
            organism: null,
            resolution_angstrom: null,
            pdb_text: "",
          },
          "rcsb",
        ),
      ),
    );
    render(<ProteinPanel />);
    const select = screen.getByLabelText(/role for 1HSG/i);
    fireEvent.change(select, { target: { value: "homolog" } });
    expect(useSessionStore.getState().proteins["1HSG"]!.role).toBe("homolog");
  });
});

describe("SimPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("ships the BUILD_PROMPT defaults", () => {
    expect(DEFAULT_SIM_VALUES.mode).toBe("competition");
    expect(DEFAULT_SIM_VALUES.useAttraction).toBe(true);
    expect(DEFAULT_SIM_VALUES.temperatureK).toBeCloseTo(298.15);
  });

  it("Run button passes current values to onRun", () => {
    const onRun = vi.fn();
    render(<SimPanel onRun={onRun} />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(onRun).toHaveBeenCalledOnce();
    const args = onRun.mock.calls[0]![0];
    expect(args.iterations).toBe(1000);
    expect(args.mode).toBe("competition");
  });

  it("changing iterations updates the value passed to Run", () => {
    const onRun = vi.fn();
    render(<SimPanel onRun={onRun} />);
    const input = screen.getByLabelText(/number of iterations/i);
    fireEvent.change(input, { target: { value: "5000" } });
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(onRun.mock.calls[0]![0].iterations).toBe(5000);
  });

  it("Fast-forward button only renders when the prop is given", () => {
    const onRun = vi.fn();
    const { rerender } = render(<SimPanel onRun={onRun} />);
    expect(screen.queryByRole("button", { name: /fast-forward/i })).toBeNull();
    const onFastForward = vi.fn();
    rerender(<SimPanel onRun={onRun} onFastForward={onFastForward} />);
    fireEvent.click(screen.getByRole("button", { name: /fast-forward/i }));
    expect(onFastForward).toHaveBeenCalledOnce();
  });

  it("toggles the encounter-potential checkbox", () => {
    const onRun = vi.fn();
    render(<SimPanel onRun={onRun} />);
    const checkbox = screen.getByLabelText(
      /use encounter-potential acceleration/i,
    ) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(onRun.mock.calls[0]![0].useAttraction).toBe(false);
  });

  it("switches mode via the radio inputs", () => {
    const onRun = vi.fn();
    render(<SimPanel onRun={onRun} />);
    fireEvent.click(screen.getByLabelText(/inhibitor only/i));
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(onRun.mock.calls[0]![0].mode).toBe("inhibitor_only");
  });
});
