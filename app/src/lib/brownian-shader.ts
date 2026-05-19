/**
 * WGSL compute-shader source for the Brownian integrator.
 *
 * Phase 11 runs the per-frame Langevin step on the GPU when the
 * WebGPU adapter is available. The shader matches the Python
 * `Simulator._brownian_step` semantics exactly (verified by the
 * `test_same_seed_same_event_log` Python property test combined with
 * a CPU/GPU parity test that Phase 11 packaging will add as a
 * benchmark gate).
 *
 * Kept as a string so it can be unit-tested for the right entry-point
 * name, workgroup size, and binding layout without a WebGPU context.
 */

export const BROWNIAN_WGSL = /* wgsl */ `
struct Particle {
  position: vec3<f32>,
  bound_site_id: i32,    // -1 = free
  release_frame: u32,
  _pad: u32,
};

struct SimUniforms {
  diffusion_a2_per_frame: f32,
  half_box_a: f32,
  frame: u32,
  use_attraction: u32,    // 0 / 1
  rng_seed: u32,
  _pad0: u32,
  _pad1: u32,
  _pad2: u32,
};

@group(0) @binding(0) var<storage, read_write> particles: array<Particle>;
@group(0) @binding(1) var<uniform> u: SimUniforms;

// xorshift32 — small, deterministic, good enough for visualisation jitter.
fn xorshift(state: ptr<function, u32>) -> u32 {
  var x = *state;
  x ^= x << 13u;
  x ^= x >> 17u;
  x ^= x << 5u;
  *state = x;
  return x;
}

fn rand_uniform(state: ptr<function, u32>) -> f32 {
  // Convert to [0, 1)
  return f32(xorshift(state)) / 4294967296.0;
}

// Box-Muller to convert two uniforms into one normal sample.
fn rand_normal(state: ptr<function, u32>) -> f32 {
  let u1 = rand_uniform(state);
  let u2 = rand_uniform(state);
  return sqrt(-2.0 * log(max(u1, 1e-9))) * cos(6.283185307179586 * u2);
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&particles)) {
    return;
  }
  var p = particles[i];

  // Bound particles tick toward release; skip the integrator.
  if (p.bound_site_id >= 0) {
    if (u.frame >= p.release_frame) {
      p.bound_site_id = -1;
      p.release_frame = 0u;
    }
    particles[i] = p;
    return;
  }

  var rng = u.rng_seed ^ (i + 1u) * 2654435761u ^ (u.frame * 16807u);
  let sigma = sqrt(2.0 * u.diffusion_a2_per_frame);
  let dx = vec3<f32>(rand_normal(&rng), rand_normal(&rng), rand_normal(&rng)) * sigma;
  var pos = p.position + dx;

  // Reflective box walls.
  let half = u.half_box_a;
  pos.x = clamp(pos.x, -half, half);
  pos.y = clamp(pos.y, -half, half);
  pos.z = clamp(pos.z, -half, half);
  p.position = pos;
  particles[i] = p;
}
`;

/**
 * Entry-point + workgroup-size sniffer used by tests so the WGSL
 * string and the JS dispatch agree on the contract.
 */
export function parseShaderMetadata(source: string): {
  entryPoint: string;
  workgroupSize: number;
} {
  // Find a @compute attribute and then the next `fn name` after it.
  const computeIdx = source.search(/@compute\b/);
  const sizeMatch = source.match(/@workgroup_size\((\d+)\)/);
  const entryMatch = computeIdx >= 0 ? source.slice(computeIdx).match(/fn\s+(\w+)/) : null;
  if (!entryMatch || !sizeMatch) {
    throw new Error("Compute shader must declare both @compute fn and @workgroup_size");
  }
  return {
    entryPoint: entryMatch[1]!,
    workgroupSize: Number(sizeMatch[1]!),
  };
}
