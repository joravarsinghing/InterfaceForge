import React, { useState } from 'react';
import { CalibrationBoundary, Dimension, Point2D, ProfileType } from '../types/schema';

interface SvgProfileViewerProps {
  profileType: ProfileType;
  dimensions: Dimension[];
  calibrationBoundary?: CalibrationBoundary | null;
  calibrationConfirmed?: boolean;
  points?: Point2D[];
  width?: number;
  height?: number;
  calibrationMode?: boolean;
  calibrationPointA?: Point2D | null;
  calibrationPointB?: Point2D | null;
  onCalibrationPick?: (point: Point2D) => void;
}

interface Bounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

function finitePoint(point: Point2D): boolean {
  return Number.isFinite(point.x) && Number.isFinite(point.y);
}

function boundsFor(points: Point2D[]): Bounds {
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}

function paddedBounds(bounds: Bounds): Bounds {
  const width = bounds.maxX - bounds.minX || 1;
  const height = bounds.maxY - bounds.minY || 1;
  const pad = Math.max(width, height) * 0.18 + 8;
  return {
    minX: bounds.minX - pad,
    maxX: bounds.maxX + pad,
    minY: bounds.minY - pad,
    maxY: bounds.maxY + pad,
  };
}

function pathData(points: Point2D[]): string {
  if (points.length === 0) return '';
  const [first, ...rest] = points;
  return `M ${first.x.toFixed(3)} ${first.y.toFixed(3)} ${rest.map((point) => `L ${point.x.toFixed(3)} ${point.y.toFixed(3)}`).join(' ')} Z`;
}

function calibrationNodesFor(profileType: ProfileType, points: Point2D[]): Point2D[] {
  if (profileType !== 'rounded_rectangle' || points.length < 16 || points.length % 4 !== 0) {
    return points;
  }
  const quarterLength = points.length / 4;
  return Array.from({ length: 4 }, (_, quarter) => {
    const start = quarter * quarterLength;
    return [points[start], points[start + quarterLength - 1]];
  }).flat();
}
export const SvgProfileViewer: React.FC<SvgProfileViewerProps> = ({
  profileType,
  calibrationBoundary = null,
  points = [],
  width = 360,
  height = 280,
  calibrationMode = false,
  calibrationPointA = null,
  calibrationPointB = null,
  onCalibrationPick,
}) => {
  const [hoveredNodeIndex, setHoveredNodeIndex] = useState<number | null>(null);
  const sourcePoints = calibrationBoundary?.points?.filter(finitePoint).length ? calibrationBoundary.points.filter(finitePoint) : points.filter(finitePoint);
  const boundaryPoints = sourcePoints.length >= 3 ? sourcePoints : profileType === 'circle' ? [{ x: -25, y: 0 }, { x: 0, y: 25 }, { x: 25, y: 0 }, { x: 0, y: -25 }] : [{ x: -30, y: -20 }, { x: 30, y: -20 }, { x: 30, y: 20 }, { x: -30, y: 20 }];
  const bounds = paddedBounds(boundsFor(boundaryPoints));
  const viewBoxWidth = bounds.maxX - bounds.minX;
  const viewBoxHeight = bounds.maxY - bounds.minY;
  const markerA = calibrationPointA && finitePoint(calibrationPointA) ? calibrationPointA : null;
  const markerB = calibrationPointB && finitePoint(calibrationPointB) ? calibrationPointB : null;
  const calibrationNodes = calibrationNodesFor(profileType, boundaryPoints);
  const selectedCalibrationNodes = [markerA, markerB]
    .filter((point): point is Point2D => Boolean(point))
    .filter((point) => !calibrationNodes.some((node) => Math.abs(node.x - point.x) < 0.000001 && Math.abs(node.y - point.y) < 0.000001));
  const displayCalibrationNodes = [...calibrationNodes, ...selectedCalibrationNodes];
  const visualScale = Math.max(viewBoxWidth, viewBoxHeight);
  const nodeRadius = visualScale * 0.010;
  const selectedRadius = visualScale * 0.014;
  const labelSize = visualScale * 0.025;
  const labelOffset = visualScale * 0.018;

  return (
    <div className="svg-profile-viewer" style={{ textAlign: 'center' }}>
      <svg
        width={width}
        height={height}
        viewBox={`${bounds.minX} ${bounds.minY} ${viewBoxWidth} ${viewBoxHeight}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`SVG geometry preview for ${profileType} profile`}
        style={{
          background: '#0d1117',
          borderRadius: '8px',
          border: '1px solid #30363d',
          maxWidth: '100%',
          height: 'auto',
          cursor: calibrationMode ? 'pointer' : undefined,
        }}
      >
        <title>{`${profileType} Profile Preview`}</title>
        <desc>Primitive profile in canonical profile coordinates. Calibration clicks and stored markers use this same coordinate space.</desc>

        <defs>
          <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#21262d" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect x={bounds.minX} y={bounds.minY} width={viewBoxWidth} height={viewBoxHeight} fill="url(#grid-pattern)" />
        <line x1={bounds.minX} y1="0" x2={bounds.maxX} y2="0" stroke="#30363d" strokeWidth="1" strokeDasharray="4 4" />
        <line x1="0" y1={bounds.minY} x2="0" y2={bounds.maxY} stroke="#30363d" strokeWidth="1" strokeDasharray="4 4" />

        <path
          d={pathData(boundaryPoints)}
          fill="rgba(56, 139, 253, 0.15)"
          stroke="#58a6ff"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />

        {displayCalibrationNodes.map((point, index) => {
          const selectedA = Boolean(markerA && Math.abs(markerA.x - point.x) < 0.000001 && Math.abs(markerA.y - point.y) < 0.000001);
          const selectedB = Boolean(markerB && Math.abs(markerB.x - point.x) < 0.000001 && Math.abs(markerB.y - point.y) < 0.000001);
          const hovered = hoveredNodeIndex === index;
          const visible = calibrationMode || selectedA || selectedB;
          return (
            <g key={`calibration-node-${index}`}>
              <circle data-testid="calibration-node-hit-target" cx={point.x} cy={point.y} r={Math.max(3, Math.max(viewBoxWidth, viewBoxHeight) * 0.018)} fill="transparent" pointerEvents={calibrationMode ? 'all' : 'none'} onMouseEnter={() => setHoveredNodeIndex(index)} onMouseLeave={() => setHoveredNodeIndex(null)} onClick={(event) => { if (!calibrationMode || !onCalibrationPick) return; event.stopPropagation(); onCalibrationPick(point); }} />
              <circle data-testid="calibration-node" cx={point.x} cy={point.y} r={hovered || selectedA || selectedB ? selectedRadius : nodeRadius} fill={selectedA ? '#f85149' : selectedB ? '#3fb950' : hovered ? '#ffffff' : '#f0b72f'} stroke={selectedA || selectedB || hovered ? '#ffffff' : '#0d1117'} strokeWidth={selectedA || selectedB ? 1.6 : 1.2} opacity={visible ? 1 : 0.18} pointerEvents="none" vectorEffect="non-scaling-stroke" />
            </g>
          );
        })}

        {markerA && markerB && (
          <line
            x1={markerA.x}
            y1={markerA.y}
            x2={markerB.x}
            y2={markerB.y}
            stroke="#f0f6fc"
            strokeWidth="1.6"
            strokeDasharray="5 3"
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
        {markerA && (
          <g pointerEvents="none">
            <circle data-testid="calibration-marker-a" cx={markerA.x} cy={markerA.y} r={selectedRadius} fill="#f85149" stroke="#ffffff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            <text x={markerA.x + labelOffset} y={markerA.y - labelOffset} fill="#ffffff" fontSize={labelSize}>A</text>
          </g>
        )}
        {markerB && (
          <g pointerEvents="none">
            <circle data-testid="calibration-marker-b" cx={markerB.x} cy={markerB.y} r={selectedRadius} fill="#3fb950" stroke="#ffffff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            <text x={markerB.x + labelOffset} y={markerB.y - labelOffset} fill="#ffffff" fontSize={labelSize}>B</text>
          </g>
        )}

        <circle cx="0" cy="0" r="3" fill="#f0883e" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
};

export default SvgProfileViewer;