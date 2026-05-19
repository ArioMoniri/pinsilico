import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { proteinFromEntry, useSessionStore } from "./session";
import { useSceneStore } from "./scene";

describe("useSessionStore", () => {
  beforeEach(() => {
    act(() => useSessionStore.getState().reset());
    act(() =>
      useSessionStore.setState({
        apiBase: null,
        token: null,
        proteins: {},
        ligands: {},
      }),
    );
  });

  it("starts empty", () => {
    const s = useSessionStore.getState();
    expect(s.apiBase).toBeNull();
    expect(s.proteins).toEqual({});
    expect(s.ligands).toEqual({});
  });

  it("setConnection stores the api base and token", () => {
    act(() => useSessionStore.getState().setConnection("http://127.0.0.1:51234", "tok"));
    const s = useSessionStore.getState();
    expect(s.apiBase).toBe("http://127.0.0.1:51234");
    expect(s.token).toBe("tok");
  });

  it("addProtein and removeProtein roundtrip", () => {
    const p = proteinFromEntry(
      {
        identifier: "1HSG",
        title: "",
        organism: null,
        resolution_angstrom: null,
        pdb_text: "HEADER\nEND\n",
      },
      "rcsb",
    );
    act(() => useSessionStore.getState().addProtein(p));
    expect(useSessionStore.getState().proteins["1HSG"]).toBeDefined();
    act(() => useSessionStore.getState().removeProtein("1HSG"));
    expect(useSessionStore.getState().proteins["1HSG"]).toBeUndefined();
  });

  it("setProteinPockets is a no-op for unknown ids", () => {
    act(() => useSessionStore.getState().setProteinPockets("nope", []));
    expect(useSessionStore.getState().proteins["nope"]).toBeUndefined();
  });

  it("setProteinPockets attaches to an existing record", () => {
    const p = proteinFromEntry(
      {
        identifier: "1HSG",
        title: "",
        organism: null,
        resolution_angstrom: null,
        pdb_text: "HEADER\n",
      },
      "rcsb",
    );
    act(() => useSessionStore.getState().addProtein(p));
    act(() =>
      useSessionStore.getState().setProteinPockets("1HSG", [
        {
          identifier: "pocket-1",
          centroid_xyz: [0, 0, 0],
          volume_a3: 100,
          hydrophobicity: 0,
          druggability_score: 0.9,
          residue_ids: [],
        },
      ]),
    );
    const stored = useSessionStore.getState().proteins["1HSG"]!;
    expect(stored.pockets).toHaveLength(1);
    expect(stored.pockets[0]!.identifier).toBe("pocket-1");
  });

  it("toggleInhibitor flips the flag", () => {
    act(() =>
      useSessionStore.getState().addLigand({
        identifier: "indinavir",
        source: "chembl",
        smiles: "CC",
        is_inhibitor: false,
        is_natural_ligand: false,
      }),
    );
    act(() => useSessionStore.getState().toggleInhibitor("indinavir"));
    expect(useSessionStore.getState().ligands["indinavir"]!.is_inhibitor).toBe(true);
    act(() => useSessionStore.getState().toggleInhibitor("indinavir"));
    expect(useSessionStore.getState().ligands["indinavir"]!.is_inhibitor).toBe(false);
  });
});

describe("useSceneStore", () => {
  beforeEach(() => {
    act(() =>
      useSceneStore.setState({
        view: "arena",
        activeProteinId: null,
        activePocketId: null,
        isPaused: false,
      }),
    );
  });

  it("defaults to arena view, not paused", () => {
    expect(useSceneStore.getState().view).toBe("arena");
    expect(useSceneStore.getState().isPaused).toBe(false);
  });

  it("setView toggles between arena and atomistic", () => {
    act(() => useSceneStore.getState().setView("atomistic"));
    expect(useSceneStore.getState().view).toBe("atomistic");
  });

  it("setActiveProtein clears pocket selection", () => {
    act(() => useSceneStore.getState().setActivePocket("pocket-1"));
    act(() => useSceneStore.getState().setActiveProtein("1HSG"));
    expect(useSceneStore.getState().activePocketId).toBeNull();
    expect(useSceneStore.getState().activeProteinId).toBe("1HSG");
  });

  it("togglePaused flips state", () => {
    act(() => useSceneStore.getState().togglePaused());
    expect(useSceneStore.getState().isPaused).toBe(true);
    act(() => useSceneStore.getState().togglePaused());
    expect(useSceneStore.getState().isPaused).toBe(false);
  });
});
