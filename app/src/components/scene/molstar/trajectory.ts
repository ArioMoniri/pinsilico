/**
 * Trajectory frame builder for the Mol* atomistic view.
 *
 * Phase 8 replays a single binding event by interpolating the ligand's
 * xyz from "free incoming" through "approaching pocket" to "harmonic-
 * bound around the docked pose" and back to "departing". The function
 * here is the deterministic mapping (input frames → output frames at
 * the user's chosen playback rate). The actual Mol* coordinate-update
 * loop lives in MolstarViewer.
 */

export interface LigandFrame {
  /** Frame index in the source simulation. */
  index: number;
  /** Ligand centre-of-mass position (Å). */
  com: [number, number, number];
  /** True iff the ligand was bound at this frame. */
  bound: boolean;
}

/**
 * Linearly interpolate a fast-forwarded swarm trajectory into a
 * playback-rate-adjusted sequence of frames.
 *
 * @param frames Source frames at simulation rate (typically 20 Hz).
 * @param playbackRate Multiplier (0.25, 0.5, 1, 2, 4 are the SimPanel options).
 * @returns Sampled frames preserving the bound-state transitions.
 */
export function interpolateLigandFrames(
  frames: LigandFrame[],
  playbackRate: number,
): LigandFrame[] {
  if (frames.length === 0) return [];
  if (playbackRate <= 0) {
    throw new Error(`playbackRate must be positive, got ${playbackRate}`);
  }
  // Step >1 means skip frames; step <1 means linearly interpolate between.
  const step = 1 / playbackRate;
  const out: LigandFrame[] = [];
  for (let t = 0; t < frames.length - 1 + 1e-9; t += step) {
    const i = Math.floor(t);
    const j = Math.min(i + 1, frames.length - 1);
    const lerpT = t - i;
    const a = frames[i]!;
    const b = frames[j]!;
    const boundNow = lerpT < 0.5 ? a.bound : b.bound;
    // Bound state snaps the COM to the bound frame's position so the
    // harmonic-restraint UI doesn't show the ligand sliding while still
    // tagged "bound".
    const com: [number, number, number] = boundNow
      ? [...(a.bound ? a.com : b.com)]
      : [
          a.com[0] + (b.com[0] - a.com[0]) * lerpT,
          a.com[1] + (b.com[1] - a.com[1]) * lerpT,
          a.com[2] + (b.com[2] - a.com[2]) * lerpT,
        ];
    out.push({ index: Math.round(t), com, bound: boundNow });
  }
  return out;
}

/**
 * Find the index of the first binding event (free → bound transition)
 * in a frame list. Returns -1 if none.
 */
export function findFirstBindingIndex(frames: LigandFrame[]): number {
  for (let i = 1; i < frames.length; i++) {
    if (!frames[i - 1]!.bound && frames[i]!.bound) return i;
  }
  return -1;
}
