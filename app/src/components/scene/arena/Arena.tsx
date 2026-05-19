import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { JSX } from "react";
import type { PocketResponse } from "../../../lib/api";
import { useSceneStore } from "../../../stores/scene";
import { useSessionStore } from "../../../stores/session";
import { ParticleSwarm } from "./Particle";
import { PocketMarker } from "./PocketMarker";
import { ProteinShell } from "./ProteinShell";

interface ArenaProps {
  positions: Float32Array;
  bound: boolean[];
}

/**
 * Abstract arena view.
 *
 * Composes:
 * - One ProteinShell per loaded protein (real PDB-derived radius).
 * - One PocketMarker per fpocket-detected pocket on that protein.
 * - One ParticleSwarm for all diffusing particles.
 * - drei OrbitControls with damping; click a protein to focus the
 *   atomistic view (Phase 8b) on it.
 */
export function Arena({ positions, bound }: ArenaProps): JSX.Element {
  const proteins = useSessionStore((s) => s.proteins);
  const setActiveProtein = useSceneStore((s) => s.setActiveProtein);
  const setActivePocket = useSceneStore((s) => s.setActivePocket);
  const activePocketId = useSceneStore((s) => s.activePocketId);
  const setView = useSceneStore((s) => s.setView);

  const proteinEntries = Object.values(proteins);
  // Lay proteins along the x-axis with simple spacing for Phase 8;
  // Phase 9 SimPanel will allow custom layouts.
  const radius = 12.0;
  const spacing = radius * 3.5;

  return (
    <Canvas
      camera={{ position: [0, 30, 80], fov: 50 }}
      style={{ width: "100%", height: "100%", background: "#0d1117" }}
    >
      <ambientLight intensity={0.4} />
      <directionalLight position={[20, 30, 20]} intensity={0.8} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.1} />

      {proteinEntries.map((p, i) => {
        const center: [number, number, number] = [
          (i - (proteinEntries.length - 1) / 2) * spacing,
          0,
          0,
        ];
        const handleSelect = (): void => {
          setActiveProtein(p.identifier);
          setView("atomistic");
        };
        return (
          <group key={p.identifier} position={center}>
            <ProteinShell center={[0, 0, 0]} radius={radius} onSelect={handleSelect} />
            {p.pockets.map((pocket: PocketResponse) => (
              <PocketMarker
                key={pocket.identifier}
                pocket={pocket}
                selected={activePocketId === pocket.identifier}
                onSelect={() => {
                  setActivePocket(pocket.identifier);
                }}
              />
            ))}
          </group>
        );
      })}

      <ParticleSwarm positions={positions} bound={bound} />
    </Canvas>
  );
}
