import { useMemo } from "react";
import * as THREE from "three";

interface ParticleSwarmProps {
  /** xyz positions of every particle, flat array (length = N * 3). */
  positions: Float32Array;
  /** Bound state per particle — true means draw the bound colour. */
  bound: boolean[];
  /** Radius of each particle in scene Å. */
  particleRadius?: number;
}

const FREE_COLOR = new THREE.Color("#4ab0ff");
const BOUND_COLOR = new THREE.Color("#ff8a4a");

/**
 * Instanced particle swarm.
 *
 * One ``InstancedMesh`` for the whole swarm so 500 particles cost one
 * draw call. Phase 11 lifts the per-frame matrix-update loop into a
 * WebGPU compute shader; for now the loop runs on the CPU.
 */
export function ParticleSwarm({
  positions,
  bound,
  particleRadius = 1.6,
}: ParticleSwarmProps): JSX.Element {
  const count = positions.length / 3;

  // Build the instanced mesh once, reuse on every frame. The standard
  // material gets a small emissive lift so the particles read clearly
  // against the dark Arena background even before the directional
  // light has a clean angle on them.
  const { mesh, dummy } = useMemo(() => {
    const geo = new THREE.SphereGeometry(particleRadius, 12, 12);
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      emissive: new THREE.Color(0x222a36),
      emissiveIntensity: 0.6,
      roughness: 0.45,
      metalness: 0.05,
    });
    const m = new THREE.InstancedMesh(geo, mat, Math.max(count, 1));
    m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    return { mesh: m, dummy: new THREE.Object3D() };
  }, [count, particleRadius]);

  // Sync positions + colour every render. R3F re-runs this on prop change.
  useMemo(() => {
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const baseIx = i * 3;
      dummy.position.set(
        positions[baseIx] ?? 0,
        positions[baseIx + 1] ?? 0,
        positions[baseIx + 2] ?? 0,
      );
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      const c = bound[i] ? BOUND_COLOR : FREE_COLOR;
      colors[baseIx] = c.r;
      colors[baseIx + 1] = c.g;
      colors[baseIx + 2] = c.b;
    }
    mesh.geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    mesh.instanceMatrix.needsUpdate = true;
  }, [positions, bound, count, mesh, dummy]);

  return <primitive object={mesh} />;
}
