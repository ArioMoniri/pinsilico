import { useMemo } from "react";

interface ProteinShellProps {
  /** Centre of the protein in scene space (Å). */
  center: [number, number, number];
  /** Radius in Å — typically the radius of gyration. */
  radius: number;
  /** Tint for the body's material. */
  color?: string;
  /** Click handler — fired when the user picks this protein in the arena. */
  onSelect?: () => void;
}

/**
 * Simplified protein body for the abstract arena view.
 *
 * Renders an icosphere (low-poly sphere) sized to the protein's radius of
 * gyration. The Phase 8 spec optionally replaces this with a decimated
 * Connolly surface mesh streamed from the sidecar's pocket/surface
 * module — both options remain in scope; the Settings panel toggles
 * between them.
 */
export function ProteinShell({
  center,
  radius,
  color = "#7a90b8",
  onSelect,
}: ProteinShellProps): JSX.Element {
  const handleClick = useMemo(() => onSelect ?? (() => undefined), [onSelect]);
  return (
    <mesh position={center} onClick={handleClick}>
      <icosahedronGeometry args={[radius, 2]} />
      <meshStandardMaterial
        color={color}
        roughness={0.6}
        metalness={0.1}
        transparent
        opacity={0.7}
      />
    </mesh>
  );
}
