import React from 'react';
import { Dimension, Point2D, ProfileType } from '../types/schema';

interface SvgProfileViewerProps {
  profileType: ProfileType;
  dimensions: Dimension[];
  points?: Point2D[];
  width?: number;
  height?: number;
  calibrationPointA?: Point2D | null;
  calibrationPointB?: Point2D | null;
}

export const SvgProfileViewer: React.FC<SvgProfileViewerProps> = ({
  profileType,
  dimensions,
  points = [],
  width = 360,
  height = 280,
  calibrationPointA = null,
  calibrationPointB = null,
}) => {
  // Extract dimension values with defaults
  const outerDiameterDim = dimensions.find(
    (d) => d.id === 'outer_diameter' || d.id === 'diameter'
  );
  const widthDim = dimensions.find((d) => d.id === 'width');
  const heightDim = dimensions.find((d) => d.id === 'height');
  const radiusDim = dimensions.find((d) => d.id === 'corner_radius');

  const outerDiameter = outerDiameterDim ? Math.max(1, outerDiameterDim.value) : 50;
  const rectWidth = widthDim ? Math.max(1, widthDim.value) : 60;
  const rectHeight = heightDim ? Math.max(1, heightDim.value) : 40;
  const cornerRadius = radiusDim ? Math.max(0, radiusDim.value) : 5;

  // Scale geometry to fit comfortably inside 200x200 viewBox
  const maxDim =
    profileType === 'circle'
      ? outerDiameter
      : Math.max(rectWidth, rectHeight);
  const scale = maxDim > 0 ? 120 / maxDim : 1;

  const scaledRadius = (outerDiameter / 2) * scale;
  const scaledWidth = rectWidth * scale;
  const scaledHeight = rectHeight * scale;
  const scaledCornerRadius = Math.min(
    cornerRadius * scale,
    Math.min(scaledWidth, scaledHeight) / 2
  );

  const markerA =
    calibrationPointA && Number.isFinite(calibrationPointA.x) && Number.isFinite(calibrationPointA.y)
      ? { x: calibrationPointA.x * scale, y: calibrationPointA.y * scale }
      : null;
  const markerB =
    calibrationPointB && Number.isFinite(calibrationPointB.x) && Number.isFinite(calibrationPointB.y)
      ? { x: calibrationPointB.x * scale, y: calibrationPointB.y * scale }
      : null;

  return (
    <div className="svg-profile-viewer" style={{ textAlign: 'center' }}>
      <svg
        width={width}
        height={height}
        viewBox="-100 -100 200 200"
        role="img"
        aria-label={`SVG geometry preview for ${profileType} profile`}
        style={{
          background: '#0d1117',
          borderRadius: '8px',
          border: '1px solid #30363d',
          maxWidth: '100%',
          height: 'auto',
        }}
      >
        <title>{`${profileType} Profile Preview`}</title>
        <desc>{`Vector visualization of ${profileType} profile with dimension annotations.`}</desc>

        {/* Grid and Axes */}
        <defs>
          <pattern
            id="grid-pattern"
            width="20"
            height="20"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 20 0 L 0 0 0 20"
              fill="none"
              stroke="#21262d"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect x="-100" y="-100" width="200" height="200" fill="url(#grid-pattern)" />
        <line x1="-90" y1="0" x2="90" y2="0" stroke="#30363d" strokeWidth="1" strokeDasharray="4 4" />
        <line x1="0" y1="-90" x2="0" y2="90" stroke="#30363d" strokeWidth="1" strokeDasharray="4 4" />

        {/* Shape Rendering */}
        {profileType === 'circle' && (
          <g>
            <circle
              cx="0"
              cy="0"
              r={scaledRadius}
              fill="rgba(56, 139, 253, 0.15)"
              stroke="#58a6ff"
              strokeWidth="2.5"
            />
            {/* Dimension Line & Label */}
            <line
              x1={-scaledRadius}
              y1="0"
              x2={scaledRadius}
              y2="0"
              stroke="#f0883e"
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
            <text
              x="0"
              y="-8"
              fill="#f0883e"
              fontSize="10"
              fontWeight="bold"
              textAnchor="middle"
            >
                {outerDiameter} mm
            </text>
          </g>
        )}

        {profileType === 'rectangle' && (
          <g>
            <rect
              x={-scaledWidth / 2}
              y={-scaledHeight / 2}
              width={scaledWidth}
              height={scaledHeight}
              fill="rgba(56, 139, 253, 0.15)"
              stroke="#58a6ff"
              strokeWidth="2.5"
            />
            {/* Width Dimension */}
            <text
              x="0"
              y={-scaledHeight / 2 - 6}
              fill="#f0883e"
              fontSize="10"
              fontWeight="bold"
              textAnchor="middle"
            >
              W: {rectWidth} mm
            </text>
            {/* Height Dimension */}
            <text
              x={scaledWidth / 2 + 8}
              y="4"
              fill="#f0883e"
              fontSize="10"
              fontWeight="bold"
              textAnchor="start"
            >
              H: {rectHeight} mm
            </text>
          </g>
        )}

        {profileType === 'rounded_rectangle' && (
          <g>
            <rect
              x={-scaledWidth / 2}
              y={-scaledHeight / 2}
              width={scaledWidth}
              height={scaledHeight}
              rx={scaledCornerRadius}
              ry={scaledCornerRadius}
              fill="rgba(56, 139, 253, 0.15)"
              stroke="#58a6ff"
              strokeWidth="2.5"
            />
            {/* Width Dimension */}
            <text
              x="0"
              y={-scaledHeight / 2 - 6}
              fill="#f0883e"
              fontSize="10"
              fontWeight="bold"
              textAnchor="middle"
            >
              W: {rectWidth} mm
            </text>
            {/* Height Dimension */}
            <text
              x={scaledWidth / 2 + 8}
              y="4"
              fill="#f0883e"
              fontSize="10"
              fontWeight="bold"
              textAnchor="start"
            >
              H: {rectHeight} mm
            </text>
            {/* Corner Radius */}
            <text
              x="0"
              y={scaledHeight / 2 + 16}
              fill="#79c0ff"
              fontSize="9"
              textAnchor="middle"
            >
              r: {cornerRadius} mm
            </text>
          </g>
        )}

        {/* Candidate Points overlay */}
        {points.length > 0 &&
          points.map((pt, idx) => (
            <circle
              key={idx}
              cx={pt.x * scale}
              cy={pt.y * scale}
              r="2"
              fill="#a5d6ff"
            />
          ))}

        {markerA && markerB && (
          <line
            x1={markerA.x}
            y1={markerA.y}
            x2={markerB.x}
            y2={markerB.y}
            stroke="#f0f6fc"
            strokeWidth="1.6"
            strokeDasharray="5 3"
            pointerEvents="none"
          />
        )}
        {markerA && (
          <g pointerEvents="none">
            <circle cx={markerA.x} cy={markerA.y} r="5" fill="#f85149" stroke="#ffffff" strokeWidth="1.5" />
            <text x={markerA.x + 8} y={markerA.y - 8} fill="#ffffff" fontSize="11">A</text>
          </g>
        )}
        {markerB && (
          <g pointerEvents="none">
            <circle cx={markerB.x} cy={markerB.y} r="5" fill="#3fb950" stroke="#ffffff" strokeWidth="1.5" />
            <text x={markerB.x + 8} y={markerB.y - 8} fill="#ffffff" fontSize="11">B</text>
          </g>
        )}

        {/* Center Point */}
        <circle cx="0" cy="0" r="3" fill="#f0883e" />
      </svg>
    </div>
  );
};

export default SvgProfileViewer;
