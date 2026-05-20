/**
 * User-facing UI/runtime settings.
 *
 * Separate from the session store because these survive across
 * sessions (the user picks a renderer preference once and we honour it
 * on every launch). v1.3 stores everything in-memory; later phases may
 * persist via Tauri's filesystem plugin.
 */

import { create } from "zustand";

import type { RendererPreference, RendererTier } from "../lib/renderer";

export interface SettingsState {
  rendererPreference: RendererPreference;
  /** Active tier returned by `pickRenderer` — purely informational. */
  rendererTier: RendererTier | null;
  setRendererPreference(p: RendererPreference): void;
  setRendererTier(t: RendererTier | null): void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  rendererPreference: "auto",
  rendererTier: null,
  setRendererPreference: (p) => set({ rendererPreference: p }),
  setRendererTier: (t) => set({ rendererTier: t }),
}));
