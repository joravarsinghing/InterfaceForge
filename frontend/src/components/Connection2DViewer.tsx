import React from 'react';
import type { Connection, InterfaceDefinition, Manufacturing } from '../types/schema';

interface Connection2DViewerProps {
  interfaceA?: InterfaceDefinition | null;
  interfaceB?: InterfaceDefinition | null;
  connection: Connection;
  manufacturing: Manufacturing;
}

function getOuterDim(iface?: InterfaceDefinition | null): number {
  if (!iface || !iface.dimensions) return 50.0;
  const dims: Record<string, number> = {};
  iface.dimensions.forEach((d) => {
    if (d.value > 0) dims[d.id] = d.value;
  });
  if (iface.profile_type === 'circle') {
    return dims['outer_diameter'] || 50.0;
  } else if (iface.profile_type === 'rectangle' || iface.profile_type === 'rounded_rectangle') {
    const w = dims['width'] || 50.0;
    const h = dims['height'] || 50.0;
    return Math.hypot(w, h);
  }
  return 50.0;
}

export const Connection2DViewer: React.FC<Connection2DViewerProps> = ({
  interfaceA,
  interfaceB,
  connection,
  manufacturing,
}) => {
  const dimA = getOuterDim(interfaceA);
  const dimB = getOuterDim(interfaceB);

  const length = Math.max(10, Math.min(connection.length_mm || 10, 300));
  const offsetX = connection.offset_x_mm || 0;
  const angle = connection.angle_deg || 0;
  const wall = Math.max(0.4, manufacturing.wall_thickness_mm || 2.4);

  // SVG viewport setup: Center origin at bottom middle (250, 300)
  const viewBoxWidth = 500;
  const viewBoxHeight = 360;
  const originX = 250;
  const originY = 300;

  // Scale factor to map mm to pixels
  const maxSpan = Math.max(dimA, dimB, length) * 1.5 + Math.abs(offsetX);
  const scale = Math.min(1.8, Math.max(0.4, 200 / maxSpan));

  // Interface A coordinates (bottom, Z=0)
  const halfA = (dimA / 2) * scale;
  const aLeftX = originX - halfA;
  const aRightX = originX + halfA;
  const aY = originY;

  // Interface B coordinates (top, Z=length, offset by X, rotated by angle)
  const halfB = (dimB / 2) * scale;
  const bCenterUnrotX = originX + offsetX * scale;
  const bCenterUnrotY = originY - length * scale;

  // Angular rotation around center B
  const rad = (angle * Math.PI) / 180;
  const bLeftDx = -halfB * Math.cos(rad);
  const bLeftDy = -halfB * Math.sin(rad);
  const bRightDx = halfB * Math.cos(rad);
  const bRightDy = halfB * Math.sin(rad);

  const bLeftX = bCenterUnrotX + bLeftDx;
  const bLeftY = bCenterUnrotY + bLeftDy;
  const bRightX = bCenterUnrotX + bRightDx;
  const bRightY = bCenterUnrotY + bRightDy;

  const wallPx = wall * scale;

  // Outer hull path: A-Left -> B-Left -> B-Right -> A-Right -> Close
  const outerPath = `M ${aLeftX} ${aY} L ${bLeftX} ${bLeftY} L ${bRightX} ${bRightY} L ${aRightX} ${aY} Z`;

  // Inner hull path (offset by wall thickness)
  const innerALeftX = aLeftX + wallPx;
  const innerARightX = aRightX - wallPx;
  const innerBLeftX = bLeftX + wallPx * Math.cos(rad);
  const innerBLeftY = bLeftY + wallPx * Math.sin(rad);
  const innerBRightX = bRightX - wallPx * Math.cos(rad);
  const innerBRightY = bRightY - wallPx * Math.sin(rad);

  const innerPath = `M ${innerALeftX} ${aY} L ${innerBLeftX} ${innerBLeftY} L ${innerBRightX} ${innerBRightY} L ${innerARightX} ${aY} Z`;

  return (
    <div className="connection-2d-viewer-container" style={{ textAlign: 'center' }}>
      <svg
        role="img"
        aria-label="Live 2D schematic of connection configuration"
        viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
        width="100%"
        height="320"
        style={{
          background: '#0d1117',
          borderRadius: '8px',
          border: '1px solid #30363d',
        }}
      >
        <title>Connection 2D Schematic Guide</title>
        <desc>
          Visualizes 2D cross-section elevation for transition length ({connection.length_mm} mm),
          mode ({connection.mode}), X offset ({connection.offset_x_mm} mm), angle ({connection.angle_deg} deg),
          and wall thickness ({manufacturing.wall_thickness_mm} mm).
        </desc>

        {/* Reference Grid & Axes */}
        <defs>
          <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#21262d" strokeWidth="0.8" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-pattern)" />

        {/* Centerline Ray */}
        <line
          x1={originX}
          y1={aY + 20}
          x2={originX}
          y2={originY - length * scale - 40}
          stroke="#484f58"
          strokeDasharray="4 4"
          strokeWidth="1.5"
        />
        <line
          x1={originX}
          y1={aY}
          x2={bCenterUnrotX}
          y2={bCenterUnrotY}
          stroke="#58a6ff"
          strokeDasharray="6 3"
          strokeWidth="2"
        />

        {/* Outer Adapter Shell */}
        <path d={outerPath} fill="rgba(56, 139, 253, 0.15)" stroke="#58a6ff" strokeWidth="2" />

        {/* Inner Passage Void */}
        <path d={innerPath} fill="#0d1117" stroke="#1f6feb" strokeWidth="1.5" strokeDasharray="3 3" />

        {/* Interface A Base Bar (Bottom) */}
        <line x1={aLeftX - 10} y1={aY} x2={aRightX + 10} y2={aY} stroke="#3fb950" strokeWidth="4" />
        <text x={aRightX + 15} y={aY + 4} fill="#3fb950" fontSize="11" fontWeight="bold">
          Interface A ({dimA.toFixed(1)}mm) [Tol: {manufacturing.clearance_a_mm}mm]
        </text>

        {/* Interface B Top Bar */}
        <line
          x1={bLeftX - 10 * Math.cos(rad)}
          y1={bLeftY - 10 * Math.sin(rad)}
          x2={bRightX + 10 * Math.cos(rad)}
          y2={bRightY + 10 * Math.sin(rad)}
          stroke="#a371f7"
          strokeWidth="4"
        />
        <text
          x={bRightX + 15 * Math.cos(rad)}
          y={bRightY + 4}
          fill="#a371f7"
          fontSize="11"
          fontWeight="bold"
        >
          Interface B ({dimB.toFixed(1)}mm) [Tol: {manufacturing.clearance_b_mm}mm]
        </text>

        {/* Transition Length Callout */}
        <line
          x1={originX - halfA - 30}
          y1={aY}
          x2={originX - halfA - 30}
          y2={bCenterUnrotY}
          stroke="#d29922"
          strokeWidth="1.5"
        />
        <line
          x1={originX - halfA - 35}
          y1={aY}
          x2={originX - halfA - 25}
          y2={aY}
          stroke="#d29922"
          strokeWidth="1.5"
        />
        <line
          x1={originX - halfA - 35}
          y1={bCenterUnrotY}
          x2={originX - halfA - 25}
          y2={bCenterUnrotY}
          stroke="#d29922"
          strokeWidth="1.5"
        />
        <text
          x={originX - halfA - 35}
          y={(aY + bCenterUnrotY) / 2}
          fill="#d29922"
          fontSize="11"
          textAnchor="end"
          alignmentBaseline="middle"
        >
          Length: {connection.length_mm}mm
        </text>

        {/* Offset Callout if > 0 */}
        {Math.abs(connection.offset_x_mm) > 0 && (
          <g>
            <line
              x1={originX}
              y1={bCenterUnrotY - 15}
              x2={bCenterUnrotX}
              y2={bCenterUnrotY - 15}
              stroke="#f0883e"
              strokeWidth="1.5"
            />
            <text
              x={(originX + bCenterUnrotX) / 2}
              y={bCenterUnrotY - 20}
              fill="#f0883e"
              fontSize="11"
              textAnchor="middle"
            >
              X: {connection.offset_x_mm}mm
            </text>
          </g>
        )}

        {/* Angle Indicator if > 0 */}
        {Math.abs(connection.angle_deg) > 0 && (
          <text
            x={bCenterUnrotX}
            y={bCenterUnrotY + 25}
            fill="#f778ba"
            fontSize="11"
            textAnchor="middle"
            fontWeight="bold"
          >
            Angle: {connection.angle_deg} deg
          </text>
        )}

        {/* Wall Thickness Annotation */}
        <text x={originX} y={aY - 10} fill="#8b949e" fontSize="10" textAnchor="middle">
          Wall: {manufacturing.wall_thickness_mm}mm | Mode: {connection.mode.toUpperCase()}
        </text>
      </svg>
    </div>
  );
};
