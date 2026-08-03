/**
  * TracedProfileSvgViewer renders traced closed profile outer contour and inner holes as SVG.
  */

import React, { useState } from 'react';
import type { Point2D, TracedContour } from '../types/schema';

interface TracedProfileSvgViewerProps {
  outerContour: TracedContour | null | undefined;
  holeContours?: TracedContour[];
  width?: number;
  height?: number;
  highlightFeatureId?: string | null;
  onSelectFeature?: (id: string) => void;
  isOverlay?: boolean;
  isExample?: boolean;
  calibrationMode?: boolean;
  calibrationPointA?: Point2D | null;
  calibrationPointB?: Point2D | null;
  onCalibrationPick?: (point: Point2D) => void;
}

function computeBBox(
  outer: TracedContour | null | undefined,
  holes: TracedContour[]
): { minX: number; maxX: number; minY: number; maxY: number } | null {
  const allPoints = [
    ...(outer?.points ?? []),
    ...holes.flatMap((h) => h.points),
  ];
  if (allPoints.length === 0) return null;
  const xs = allPoints.map((p) => p.x);
  const ys = allPoints.map((p) => p.y);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}

function traceToSvgPoint(
  point: { x: number; y: number },
  minX: number,
  minY: number,
  scale: number,
  offsetX: number,
  offsetY: number,
  contentH: number
): Point2D {
  return {
    x: offsetX + (point.x - minX) * scale,
    y: offsetY + contentH - (point.y - minY) * scale,
  };
}

function toSvgPoints(
  points: { x: number; y: number }[],
  minX: number,
  minY: number,
  scale: number,
  offsetX: number,
  offsetY: number,
  contentH: number
): string {
  return points
    .map((p) => {
      const svgPoint = traceToSvgPoint(p, minX, minY, scale, offsetX, offsetY, contentH);
      return `${svgPoint.x.toFixed(2)},${svgPoint.y.toFixed(2)}`;
    })
    .join(" ");
}

function samePoint(a: Point2D | null | undefined, b: Point2D): boolean {
  if (!a) return false;
  return Math.hypot(a.x - b.x, a.y - b.y) <= 0.01;
}

const PADDING = 24;
const MIN_RESPONSIVE_HEIGHT = 360;

export const TracedProfileSvgViewer: React.FC<TracedProfileSvgViewerProps> = ({
  outerContour,
  holeContours = [],
  width,
  height,
  highlightFeatureId,
  onSelectFeature,
  isOverlay = false,
  isExample = false,
  calibrationMode = false,
  calibrationPointA = null,
  calibrationPointB = null,
  onCalibrationPick,
}) => {
  const [hoveredNodeIndex, setHoveredNodeIndex] = useState<number | null>(null);
  const displayOuter = isExample || !outerContour || outerContour.points.length < 3
    ? {
        id: 'outer_contour',
        points: [
          { x: -20, y: -20 },
          { x: -6, y: -20 },
          { x: -6, y: -14 },
          { x: 6, y: -14 },
          { x: 6, y: -20 },
          { x: 20, y: -20 },
          { x: 20, y: -6 },
          { x: 14, y: -6 },
          { x: 14, y: 6 },
          { x: 20, y: 6 },
          { x: 20, y: 20 },
          { x: 6, y: 20 },
          { x: 6, y: 14 },
          { x: -6, y: 14 },
          { x: -6, y: 20 },
          { x: -20, y: 20 },
          { x: -20, y: 6 },
          { x: -14, y: 6 },
          { x: -14, y: -6 },
          { x: -20, y: -6 },
        ],
        is_closed: true,
        provenance: 'example',
        confidence: 1.0,
        point_count: 20,
      }
    : outerContour;

  const displayHoles = isExample || !outerContour
    ? [
        {
          id: 'region_1',
          points: Array.from({ length: 12 }, (_, i) => ({
            x: Math.round(6 * Math.cos((2 * Math.PI * i) / 12) * 100) / 100,
            y: Math.round(6 * Math.sin((2 * Math.PI * i) / 12) * 100) / 100,
          })),
          is_closed: true,
          classification: 'hole' as const,
          decision: 'include' as const,
          provenance: 'example',
          confidence: 1.0,
          point_count: 12,
        },
      ]
    : holeContours;

  const bbox = computeBBox(displayOuter, displayHoles);
  if (!bbox) return null;

  const rangeX = bbox.maxX - bbox.minX || 1;
  const rangeY = bbox.maxY - bbox.minY || 1;
  const requestedWidth = width ?? 640;
  const requestedHeight = height ?? Math.max(MIN_RESPONSIVE_HEIGHT, Math.round(requestedWidth * 0.68));
  const drawW = Math.max(1, requestedWidth - PADDING * 2);
  const drawH = Math.max(1, requestedHeight - PADDING * 2);
  const scale = Math.min(drawW / rangeX, drawH / rangeY);
  const contentW = rangeX * scale;
  const contentH = rangeY * scale;
  const offsetX = PADDING + Math.max(0, (drawW - contentW) / 2);
  const offsetY = PADDING + Math.max(0, (drawH - contentH) / 2);
  const actualW = requestedWidth;
  const actualH = requestedHeight;
  const aspectRatio = actualW / actualH;
  const minHeight = height ?? MIN_RESPONSIVE_HEIGHT;

  const outerSvg = toSvgPoints(displayOuter.points, bbox.minX, bbox.minY, scale, offsetX, offsetY, contentH);
  const nodeSvgPoints = displayOuter.points.map((p) => traceToSvgPoint(p, bbox.minX, bbox.minY, scale, offsetX, offsetY, contentH));

  const isOuterHighlighted = highlightFeatureId === 'outer_contour';
  const markerA = calibrationPointA
    ? traceToSvgPoint(calibrationPointA, bbox.minX, bbox.minY, scale, offsetX, offsetY, contentH)
    : null;
  const markerB = calibrationPointB
    ? traceToSvgPoint(calibrationPointB, bbox.minX, bbox.minY, scale, offsetX, offsetY, contentH)
    : null;

  return (
    <div
      data-testid="traced-profile-viewer"
      style={{
        position: 'relative',
        width: width ? `${width}px` : '100%',
        maxWidth: '100%',
        minHeight: isOverlay ? undefined : minHeight,
        aspectRatio: `${aspectRatio}`,
      }}
    >
      {isExample && (
        <div
          style={{
            position: 'absolute',
            top: 6,
            left: 8,
            zIndex: 10,
            background: 'rgba(255, 145, 0, 0.2)',
            color: '#ffab40',
            border: '1px solid #ff9100',
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          EXAMPLE ILLUSTRATION - NOT YOUR MODEL
        </div>
      )}
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${actualW} ${actualH}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Traced closed profile SVG"
        role="img"
        style={{
          display: 'block',
          background: isOverlay ? 'transparent' : '#0d1117',
          borderRadius: isOverlay ? 0 : 6,
          cursor: calibrationMode ? 'crosshair' : undefined,
          minHeight: isOverlay ? undefined : minHeight,
        }}
      >
        <g>
          <polygon
            points={outerSvg}
            fill={isOuterHighlighted ? 'rgba(0, 229, 255, 0.25)' : '#00e5ff22'}
            stroke={isOuterHighlighted ? '#00e5ff' : '#00b0ff'}
            strokeWidth={isOuterHighlighted ? 3 : 2}
            style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
            onClick={() => onSelectFeature?.('outer_contour')}
          />

          {displayHoles.map((hole, i) => {
            const holeId = hole.id || `region_${i + 1}`;
            const isHighlighted = highlightFeatureId === holeId;
            const pts = toSvgPoints(hole.points, bbox.minX, bbox.minY, scale, offsetX, offsetY, contentH);
            let strokeColor = '#00e676';
            let fillColor = 'rgba(0, 230, 118, 0.25)';
            if (hole.decision === 'ignore') {
              strokeColor = '#ff9100';
              fillColor = 'rgba(255, 145, 0, 0.25)';
            } else if (hole.decision === 'unsure') {
              strokeColor = '#d500f9';
              fillColor = 'rgba(213, 0, 249, 0.25)';
            }
            if (isHighlighted) {
              strokeColor = '#ffffff';
              fillColor = 'rgba(255, 255, 255, 0.4)';
            }
            return (
              <polygon
                key={holeId}
                points={pts}
                fill={fillColor}
                stroke={strokeColor}
                strokeWidth={isHighlighted ? 2.5 : 1.5}
                strokeDasharray={hole.decision === 'ignore' ? '4 2' : undefined}
                style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                onClick={() => onSelectFeature?.(holeId)}
              />
            );
          })}

          {nodeSvgPoints.map((node, index) => {
            const tracePoint = displayOuter.points[index];
            const selectedA = samePoint(calibrationPointA, tracePoint);
            const selectedB = samePoint(calibrationPointB, tracePoint);
            const hovered = hoveredNodeIndex === index;
            const visible = calibrationMode || selectedA || selectedB;
            const fill = selectedA ? '#f85149' : selectedB ? '#3fb950' : hovered ? '#ffffff' : '#f0b72f';
            const stroke = selectedA || selectedB ? '#ffffff' : hovered ? '#f0b72f' : '#0d1117';
            return (
              <g key={`node-${index}`}>
                <circle
                  data-testid="trace-node-hit-target"
                  cx={node.x}
                  cy={node.y}
                  r={11}
                  fill="transparent"
                  pointerEvents={calibrationMode ? 'all' : 'none'}
                  onMouseEnter={() => setHoveredNodeIndex(index)}
                  onMouseLeave={() => setHoveredNodeIndex(null)}
                  onClick={(event) => {
                    if (!calibrationMode || !onCalibrationPick) return;
                    event.stopPropagation();
                    onCalibrationPick(tracePoint);
                  }}
                />
                <circle
                  data-testid="trace-node"
                  cx={node.x}
                  cy={node.y}
                  r={hovered ? 4 : selectedA || selectedB ? 4.2 : 2.6}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={selectedA || selectedB ? 1.6 : 1.2}
                  opacity={visible ? 1 : 0.18}
                  pointerEvents="none"
                />
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
              strokeWidth={1.6}
              strokeDasharray="5 3"
              pointerEvents="none"
            />
          )}
          {markerA && (
            <g pointerEvents="none">
              <circle data-testid="calibration-marker-a" cx={markerA.x} cy={markerA.y} r={4} fill="#f85149" stroke="#ffffff" strokeWidth={1.5} />
              <text x={markerA.x + 6} y={markerA.y - 6} fill="#ffffff" fontSize={10}>A</text>
            </g>
          )}
          {markerB && (
            <g pointerEvents="none">
              <circle data-testid="calibration-marker-b" cx={markerB.x} cy={markerB.y} r={4} fill="#3fb950" stroke="#ffffff" strokeWidth={1.5} />
              <text x={markerB.x + 6} y={markerB.y - 6} fill="#ffffff" fontSize={10}>B</text>
            </g>
          )}
        </g>

      </svg>
    </div>
  );
};

export default TracedProfileSvgViewer;
