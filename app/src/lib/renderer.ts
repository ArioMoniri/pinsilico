/**
 * Renderer-tier picker.
 *
 * Detects WebGPU support and returns the tier the arena scene should
 * use. BUILD_PROMPT.md §11 calls for WebGPU compute when available with
 * a WebGL2 fallback; the user-facing Settings panel exposes an
 * override (`pipeline` setting: `auto` | `webgpu` | `webgl2`).
 *
 * Feature detection is intentionally async — `navigator.gpu.requestAdapter()`
 * is the only reliable way to confirm a WebGPU adapter is actually
 * usable on this machine. A device with `navigator.gpu` defined but no
 * matching adapter is a "WebGPU advertised, not available" case we
 * want to fall back from cleanly.
 */

export type RendererTier = "webgpu" | "webgl2";
export type RendererPreference = "auto" | "webgpu" | "webgl2";

interface DetectionResult {
  tier: RendererTier;
  reason: string;
}

/** Minimal subset of the GPU API we touch during detection. */
interface MinimalGpu {
  requestAdapter: () => Promise<unknown>;
}

interface NavigatorWithGpu {
  gpu?: MinimalGpu;
}

/**
 * Returns the renderer tier to use.
 *
 * @param preference - User Settings override. ``auto`` runs detection.
 * @param nav - Injected navigator. Tests pass a stub.
 */
export async function pickRenderer(
  preference: RendererPreference = "auto",
  nav: NavigatorWithGpu = typeof navigator === "undefined" ? {} : (navigator as NavigatorWithGpu),
): Promise<DetectionResult> {
  if (preference === "webgl2") {
    return { tier: "webgl2", reason: "user preference: webgl2" };
  }
  if (preference === "webgpu") {
    // Honour the user's force-WebGPU choice but still feature-detect
    // so we can return a clear reason if the chosen path isn't viable.
    const ok = await tryAdapter(nav);
    return ok
      ? { tier: "webgpu", reason: "user preference: webgpu (adapter present)" }
      : { tier: "webgl2", reason: "user forced webgpu, but no adapter is available" };
  }
  // auto: WebGPU if an adapter is reachable.
  if (await tryAdapter(nav)) {
    return { tier: "webgpu", reason: "auto: webgpu adapter present" };
  }
  return { tier: "webgl2", reason: "auto: no webgpu, falling back to webgl2" };
}

async function tryAdapter(nav: NavigatorWithGpu): Promise<boolean> {
  if (!nav.gpu) return false;
  try {
    const adapter = await nav.gpu.requestAdapter();
    return adapter !== null && adapter !== undefined;
  } catch {
    return false;
  }
}

/**
 * Tier-string → human-readable label for the Settings panel.
 */
export function rendererLabel(tier: RendererTier): string {
  return tier === "webgpu" ? "WebGPU (compute)" : "WebGL2 (fallback)";
}
