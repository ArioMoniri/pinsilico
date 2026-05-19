/**
 * View-switcher + active selection state.
 *
 * Both 3D views (Phase 8) read from this store so toggling between
 * the abstract arena and the atomistic Mol* view doesn't lose the
 * user's active-protein / active-pocket selection.
 */

import { create } from "zustand";

export type ActiveView = "arena" | "atomistic";

export interface SceneState {
  view: ActiveView;
  activeProteinId: string | null;
  activePocketId: string | null;
  isPaused: boolean;
  setView(view: ActiveView): void;
  setActiveProtein(id: string | null): void;
  setActivePocket(id: string | null): void;
  setPaused(paused: boolean): void;
  togglePaused(): void;
}

export const useSceneStore = create<SceneState>((set) => ({
  view: "arena",
  activeProteinId: null,
  activePocketId: null,
  isPaused: false,
  setView: (view) => set({ view }),
  setActiveProtein: (id) => set({ activeProteinId: id, activePocketId: null }),
  setActivePocket: (id) => set({ activePocketId: id }),
  setPaused: (paused) => set({ isPaused: paused }),
  togglePaused: () => set((s) => ({ isPaused: !s.isPaused })),
}));
