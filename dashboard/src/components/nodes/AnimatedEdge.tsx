import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

/**
 * Custom edge: dashed when idle; when traffic is flowing, bright cyan particles
 * travel along the path. Thickness scales with traffic volume.
 */
export function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps) {
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const volume = Number((data as { volume?: number })?.volume ?? 0);
  const feedback = Boolean((data as { feedback?: boolean })?.feedback);
  const active = volume > 0;
  const color = feedback ? "#FF9500" : "#00D2FF";
  const width = Math.min(5, 1 + Math.log2(volume + 1));

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: color,
          strokeWidth: width,
          opacity: active ? 0.55 : 0.2,
          strokeDasharray: active ? "0" : "6 6",
          filter: active ? `drop-shadow(0 0 6px ${color})` : "none",
        }}
      />
      {active && (
        <>
          <circle r={3.2} fill={color} style={{ filter: `drop-shadow(0 0 6px ${color})` }}>
            <animateMotion dur="1.6s" repeatCount="indefinite" path={path} />
          </circle>
          <circle r={2.2} fill="#E8F4FF">
            <animateMotion dur="1.6s" begin="0.8s" repeatCount="indefinite" path={path} />
          </circle>
        </>
      )}
    </>
  );
}
