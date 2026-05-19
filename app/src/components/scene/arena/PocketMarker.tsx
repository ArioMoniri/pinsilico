import type { PocketResponse } from "../../../lib/api";

interface PocketMarkerProps {
  pocket: PocketResponse;
  selected?: boolean;
  onSelect?: (() => void) | undefined;
}

/**
 * Real fpocket-detected pocket centroid rendered as a coloured sphere.
 *
 * Sizing: `radius = cbrt(volume_a3)` gives a visually proportional ball
 * to the docking sphere the simulator uses. Druggability tints the halo:
 * green at ≥ 0.8, amber at 0.5–0.8, grey otherwise.
 */
export function PocketMarker({
  pocket,
  selected = false,
  onSelect,
}: PocketMarkerProps): JSX.Element {
  const radius = Math.cbrt(Math.max(pocket.volume_a3, 1));
  const haloColor =
    pocket.druggability_score >= 0.8
      ? "#3dd68c"
      : pocket.druggability_score >= 0.5
        ? "#f5c452"
        : "#888a91";

  const handleClick =
    onSelect === undefined
      ? undefined
      : (): void => {
          onSelect();
        };
  return (
    <group position={pocket.centroid_xyz} {...(handleClick ? { onClick: handleClick } : {})}>
      <mesh>
        <sphereGeometry args={[radius, 16, 16]} />
        <meshStandardMaterial
          color={haloColor}
          roughness={0.4}
          metalness={0.0}
          transparent
          opacity={selected ? 0.9 : 0.55}
        />
      </mesh>
      {selected ? (
        <mesh>
          <sphereGeometry args={[radius * 1.25, 16, 16]} />
          <meshBasicMaterial color={haloColor} transparent opacity={0.18} />
        </mesh>
      ) : null}
    </group>
  );
}
