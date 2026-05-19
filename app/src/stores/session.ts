/**
 * Top-level workspace state.
 *
 * Holds the connection bits (API base, token) the Tauri shell hands
 * to the webview at boot, plus the high-level workspace state the
 * Phase 9 panels read.
 */

import { create } from "zustand";
import type { PdbEntryResponse, PocketResponse } from "../lib/api";

export type ProteinRole = "target" | "homolog" | "off_target";

export interface ProteinRecord {
  identifier: string;
  source: "rcsb" | "alphafold" | "upload";
  role: ProteinRole;
  pdb_text: string;
  pockets: PocketResponse[];
}

export interface LigandRecord {
  identifier: string;
  source: "pubchem" | "chembl" | "drugbank" | "upload";
  smiles: string;
  is_inhibitor: boolean;
  is_natural_ligand: boolean;
}

export interface SessionState {
  apiBase: string | null;
  token: string | null;
  proteins: Record<string, ProteinRecord>;
  ligands: Record<string, LigandRecord>;
  setConnection(apiBase: string, token: string): void;
  addProtein(p: ProteinRecord): void;
  setProteinPockets(id: string, pockets: PocketResponse[]): void;
  removeProtein(id: string): void;
  addLigand(l: LigandRecord): void;
  removeLigand(id: string): void;
  toggleInhibitor(id: string): void;
  reset(): void;
}

export const useSessionStore = create<SessionState>((set) => ({
  apiBase: null,
  token: null,
  proteins: {},
  ligands: {},
  setConnection: (apiBase, token) => set({ apiBase, token }),
  addProtein: (p) => set((s) => ({ proteins: { ...s.proteins, [p.identifier]: p } })),
  setProteinPockets: (id, pockets) =>
    set((s) =>
      s.proteins[id] === undefined
        ? s
        : { proteins: { ...s.proteins, [id]: { ...s.proteins[id]!, pockets } } },
    ),
  removeProtein: (id) =>
    set((s) => {
      const next = { ...s.proteins };
      delete next[id];
      return { proteins: next };
    }),
  addLigand: (l) => set((s) => ({ ligands: { ...s.ligands, [l.identifier]: l } })),
  removeLigand: (id) =>
    set((s) => {
      const next = { ...s.ligands };
      delete next[id];
      return { ligands: next };
    }),
  toggleInhibitor: (id) =>
    set((s) =>
      s.ligands[id] === undefined
        ? s
        : {
            ligands: {
              ...s.ligands,
              [id]: {
                ...s.ligands[id]!,
                is_inhibitor: !s.ligands[id]!.is_inhibitor,
              },
            },
          },
    ),
  reset: () => set({ proteins: {}, ligands: {} }),
}));

/** Helper for tests that build PdbEntryResponse → ProteinRecord. */
export function proteinFromEntry(
  entry: PdbEntryResponse,
  source: ProteinRecord["source"],
  role: ProteinRole = "target",
): ProteinRecord {
  return {
    identifier: entry.identifier,
    source,
    role,
    pdb_text: entry.pdb_text,
    pockets: [],
  };
}
