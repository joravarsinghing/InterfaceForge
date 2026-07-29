/**
  * TracedProfileSvgViewer renders traced closed profile outer contour and inner holes as SVG.
  * S10.3 read-only display for review page.
  */

import React from 'react';
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

/**
  * Compute the bounding box of all points across outer and hole contours.
  */
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

/**
  * Convert contour points to an SVG polygon points string, scaled to viewport.
  */
function traceToSvgPoint(
  point: { x: number; y: number },
  minX: number,
  minY: number,
  scaleX: number,
  scaleY: number,
  svgHeight: number
): Point2D {
  return {
    x: (point.x - minX) * scaleX,
    y: svgHeight - (point.y - minY) * scaleY,
  };
}

function toSvgPoints(
  points: { x: number; y: number }[],
  minX: number,
  minY: number,
  scaleX: number,
  scaleY: number,
  svgHeight: number
): string {
  return points
    .map((p) => {
      const svgPoint = traceToSvgPoint(p, minX, minY, scaleX, scaleY, svgHeight);
      return `${svgPoint.x.toFixed(2)},${svgPoint.y.toFixed(2)}`;
    })
    .join(' ');
}

const PADDING = 20;

export const TracedProfileSvgViewer: React.FC<TracedProfileSvgViewerProps> = ({
  outerContour,
  holeContours = [],
  width = 320,
  height = 300,
  highlightFeatureId,
  onSelectFeature,
  isOverlay = false,
  isExample = false,
  calibrationMode = false,
  calibrationPointA = null,
  calibrationPointB = null,
  onCalibrationPick,
}) => {
  // If isExample or no outerContour, render a clear example demonstration profile illustration
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

  const drawW = width - PADDING * 2;
  const drawH = height - PADDING * 2;
  const rangeX = bbox.maxX - bbox.minX || 1;
  const rangeY = bbox.maxY - bbox.minY || 1;
  const scaleX = drawW / rangeX;
  const scaleY = drawH / rangeY;
  const scale = Math.min(scaleX, scaleY);

  const outerSvg = toSvgPoints(
    displayOuter.points,
    bbox.minX,
    bbox.minY,
    scale,
    scale,
    drawH
  );

  const actualW = rangeX * scale + PADDING * 2;
  const actualH = rangeY * scale + PADDING * 2;

  const isOuterHighlighted = highlightFeatureId === 'outer_contour';
  const markerA = calibrationPointA
    ? traceToSvgPoint(calibrationPointA, bbox.minX, bbox.minY, scale, scale, drawH)
    : null;
  const markerB = calibrationPointB
    ? traceToSvgPoint(calibrationPointB, bbox.minX, bbox.minY, scale, scale, drawH)
    : null;
  const handleSvgClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!calibrationMode || !onCalibrationPick) return;
    const svg = event.currentTarget;
    let local: Point2D | null = null;
    if (typeof svg.createSVGPoint === 'function') {
      const pt = svg.createSVGPoint();
      pt.x = event.clientX;
      pt.y = event.clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return;
      local = pt.matrixTransform(ctm.inverse());
    } else {
      const rect = svg.getBoundingClientRect();
      const attrViewBox = (svg.getAttribute('viewBox') || `0 0 ${actualW} ${actualH}`)
        .split(/\s+/)
        .map((value) => parseFloat(value));
      const viewBox = {
        x: attrViewBox[0] || 0,
        y: attrViewBox[1] || 0,
        width: attrViewBox[2] || actualW,
        height: attrViewBox[3] || actualH,
      };
      const relX = rect.width > 0 ? (event.clientX - rect.left) / rect.width : 0.5;
      const relY = rect.height > 0 ? (event.clientY - rect.top) / rect.height : 0.5;
      local = {
        x: viewBox.x + relX * viewBox.width,
        y: viewBox.y + relY * viewBox.height,
      };
    }
    const xInGroup = local.x - PADDING;
    const yInGroup = local.y - PADDING;
    onCalibrationPick({
      x: bbox.minX + xInGroup / scale,
      y: bbox.minY + (drawH - yInGroup) / scale,
    });
  };

  return (
    <div style={{ position: 'relative', width, height }}>
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
        width={width}
        height={height}
        viewBox={`0 0 ${actualW} ${actualH}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label="Traced closed profile SVG"
        role="img"
        style={{
          display: 'block',
          background: isOverlay ? 'transparent' : '#0d1117',
          borderRadius: isOverlay ? 0 : 6,
          cursor: calibrationMode ? 'crosshair' : undefined,
        }}
        onClick={handleSvgClick}
      >
        <g transform={`translate(${PADDING}, ${PADDING})`}>
          {/* Outer contour polygon */}
          <polygon
            points={outerSvg}
            fill={isOuterHighlighted ? 'rgba(0, 229, 255, 0.25)' : '#00e5ff22'}
            stroke={isOuterHighlighted ? '#00e5ff' : '#00b0ff'}
            strokeWidth={isOuterHighlighted ? 3 : 2}
            style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
            onClick={() => onSelectFeature?.('outer_contour')}
          />

          {/* Inner hole/cavity polygons */}
          {displayHoles.map((hole, i) => {
            const holeId = hole.id || `region_${i + 1}`;
            const isHighlighted = highlightFeatureId === holeId;
            const pts = toSvgPoints(hole.points, bbox.minX, bbox.minY, scale, scale, drawH);

            let strokeColor = '#00e676'; // green for included
            let fillColor = 'rgba(0, 230, 118, 0.25)';
            if (hole.decision === 'ignore') {
              strokeColor = '#ff9100'; // orange for ignored
              fillColor = 'rgba(255, 145, 0, 0.25)';
            } else if (hole.decision === 'unsure') {
              strokeColor = '#d500f9'; // purple for unsure
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
              <circle cx={markerA.x} cy={markerA.y} r={5} fill="#f85149" stroke="#ffffff" strokeWidth={1.5} />
              <text x={markerA.x + 8} y={markerA.y - 8} fill="#ffffff" fontSize={11}>A</text>
            </g>
          )}
          {markerB && (
            <g pointerEvents="none">
              <circle cx={markerB.x} cy={markerB.y} r={5} fill="#3fb950" stroke="#ffffff" strokeWidth={1.5} />
              <text x={markerB.x + 8} y={markerB.y - 8} fill="#ffffff" fontSize={11}>B</text>
            </g>
          )}
        </g>

        {/* Bottom Legend */}
        {!isOverlay && (
          <g transform={`translate(8, ${actualH - 24})`}>
            <rect x={0} y={0} width={12} height={4} fill="#00e5ff" rx={1} />
            <text x={16} y={5} fill="#8b949e" fontSize={9}>
              Outer boundary
            </text>

            <rect x={100} y={0} width={12} height={4} fill="#00e676" rx={1} />
            <text x={116} y={5} fill="#8b949e" fontSize={9}>
              Included opening
            </text>

            <rect x={180} y={0} width={10} height={4} fill="#ff9100" rx={1} />
            <text x={194} y={5} fill="#8b949e" fontSize={8}>
              Ignored region
            </text>

            <rect x={255} y={0} width={10} height={4} fill="#d500f9" rx={1} />
            <text x={269} y={5} fill="#8b949e" fontSize={8}>
              Uncertain contour
            </text>
          </g>
        )}
      </svg>
    </div>
  );
};

export default TracedProfileSvgViewer;
