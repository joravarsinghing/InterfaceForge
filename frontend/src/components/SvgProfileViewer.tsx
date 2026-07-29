import React from 'react';
import { Dimension, Point2D, ProfileType } from '../types/schema';

interface SvgProfileViewerProps {
  profileType: ProfileType;
  dimensions: Dimension[];
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

function getDimension(dimensions: Dimension[], ids: string[], fallback: number): number {
  const match = dimensions.find((dim) => ids.includes(dim.id) && Number.isFinite(dim.value) && dim.value > 0);
  return match ? match.value : fallback;
}

function primitiveBoundaryPoints(profileType: ProfileType, dimensions: Dimension[], points: Point2D[] = []): Point2D[] {
  const finitePoints = points.filter(finitePoint);
  const pointBounds = finitePoints.length >= 4 ? boundsFor(finitePoints) : null;

  const outerDiameter = getDimension(dimensions, ['outer_diameter', 'diameter'], 50);
  const rectWidth = pointBounds ? pointBounds.maxX - pointBounds.minX : getDimension(dimensions, ['width', 'overall_width'], 60);
  const rectHeight = pointBounds ? pointBounds.maxY - pointBounds.minY : getDimension(dimensions, ['height', 'overall_height'], 40);
  const centerX = pointBounds ? (pointBounds.minX + pointBounds.maxX) / 2 : 0;
  const centerY = pointBounds ? (pointBounds.minY + pointBounds.maxY) / 2 : 0;
  const circleDiameter = pointBounds ? (rectWidth + rectHeight) / 2 : outerDiameter;
  const cornerRadius = Math.min(
    pointBounds ? Math.min(rectWidth, rectHeight) * 0.12 : getDimension(dimensions, ['corner_radius'], 5),
    rectWidth / 2,
    rectHeight / 2
  );

  if (profileType === 'circle') {
    const radius = circleDiameter / 2;
    return Array.from({ length: 64 }, (_, i) => {
      const angle = (2 * Math.PI * i) / 64;
      return { x: centerX + radius * Math.cos(angle), y: centerY + radius * Math.sin(angle) };
    });
  }

  const halfW = rectWidth / 2;
  const halfH = rectHeight / 2;
  if (profileType === 'rectangle' || cornerRadius <= 0) {
    return [
      { x: centerX - halfW, y: centerY - halfH },
      { x: centerX + halfW, y: centerY - halfH },
      { x: centerX + halfW, y: centerY + halfH },
      { x: centerX - halfW, y: centerY + halfH },
    ];
  }

  const centers = [
    { x: centerX + halfW - cornerRadius, y: centerY + halfH - cornerRadius, start: 0, end: Math.PI / 2 },
    { x: centerX - halfW + cornerRadius, y: centerY + halfH - cornerRadius, start: Math.PI / 2, end: Math.PI },
    { x: centerX - halfW + cornerRadius, y: centerY - halfH + cornerRadius, start: Math.PI, end: (3 * Math.PI) / 2 },
    { x: centerX + halfW - cornerRadius, y: centerY - halfH + cornerRadius, start: (3 * Math.PI) / 2, end: 2 * Math.PI },
  ];
  return centers.flatMap((center) =>
    Array.from({ length: 9 }, (_, i) => {
      const angle = center.start + ((center.end - center.start) * i) / 8;
      return {
        x: center.x + cornerRadius * Math.cos(angle),
        y: center.y + cornerRadius * Math.sin(angle),
      };
    })
  );
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

function clientPointToViewBoxPoint(svg: SVGSVGElement, clientX: number, clientY: number): Point2D | null {
  if (typeof svg.createSVGPoint === 'function') {
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }

  const rect = svg.getBoundingClientRect();
  const rawViewBox = (svg.getAttribute('viewBox') || '0 0 1 1').split(/\s+/).map((value) => parseFloat(value));
  const viewBox = {
    x: rawViewBox[0] || 0,
    y: rawViewBox[1] || 0,
    width: rawViewBox[2] || 1,
    height: rawViewBox[3] || 1,
  };
  if (rect.width <= 0 || rect.height <= 0) return null;
  const scale = Math.min(rect.width / viewBox.width, rect.height / viewBox.height);
  const renderedW = viewBox.width * scale;
  const renderedH = viewBox.height * scale;
  const offsetX = (rect.width - renderedW) / 2;
  const offsetY = (rect.height - renderedH) / 2;
  return {
    x: viewBox.x + (clientX - rect.left - offsetX) / scale,
    y: viewBox.y + (clientY - rect.top - offsetY) / scale,
  };
}

function pathData(points: Point2D[]): string {
  if (points.length === 0) return '';
  const [first, ...rest] = points;
  return `M ${first.x.toFixed(3)} ${first.y.toFixed(3)} ${rest.map((point) => `L ${point.x.toFixed(3)} ${point.y.toFixed(3)}`).join(' ')} Z`;
}

export const SvgProfileViewer: React.FC<SvgProfileViewerProps> = ({
  profileType,
  dimensions,
  points = [],
  width = 360,
  height = 280,
  calibrationMode = false,
  calibrationPointA = null,
  calibrationPointB = null,
  onCalibrationPick,
}) => {
  const boundaryPoints = primitiveBoundaryPoints(profileType, dimensions, points);
  const bounds = paddedBounds(boundsFor(boundaryPoints));
  const viewBoxWidth = bounds.maxX - bounds.minX;
  const viewBoxHeight = bounds.maxY - bounds.minY;
  const markerA = calibrationPointA && finitePoint(calibrationPointA) ? calibrationPointA : null;
  const markerB = calibrationPointB && finitePoint(calibrationPointB) ? calibrationPointB : null;

  const outerDiameter = getDimension(dimensions, ['outer_diameter', 'diameter'], 50);
  const rectWidth = getDimension(dimensions, ['width', 'overall_width'], 60);
  const rectHeight = getDimension(dimensions, ['height', 'overall_height'], 40);
  const cornerRadius = getDimension(dimensions, ['corner_radius'], 5);

  const handleClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!calibrationMode || !onCalibrationPick) return;
    const point = clientPointToViewBoxPoint(event.currentTarget, event.clientX, event.clientY);
    if (point) onCalibrationPick(point);
  };

  return (
    <div className="svg-profile-viewer" style={{ textAlign: 'center' }}>
      <svg
        width={width}
        height={height}
        viewBox={`${bounds.minX} ${bounds.minY} ${viewBoxWidth} ${viewBoxHeight}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`SVG geometry preview for ${profileType} profile`}
        onClick={handleClick}
        style={{
          background: '#0d1117',
          borderRadius: '8px',
          border: '1px solid #30363d',
          maxWidth: '100%',
          height: 'auto',
          cursor: calibrationMode ? 'crosshair' : undefined,
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

        {profileType === 'circle' ? (
          <text x="0" y={bounds.minY + 18} fill="#f0883e" fontSize="10" fontWeight="bold" textAnchor="middle">
            {outerDiameter} mm
          </text>
        ) : (
          <>
            <text x="0" y={bounds.minY + 18} fill="#f0883e" fontSize="10" fontWeight="bold" textAnchor="middle">
              W: {rectWidth} mm
            </text>
            <text x={bounds.maxX - 8} y="4" fill="#f0883e" fontSize="10" fontWeight="bold" textAnchor="end">
              H: {rectHeight} mm
            </text>
            {profileType === 'rounded_rectangle' && (
              <text x="0" y={bounds.maxY - 10} fill="#79c0ff" fontSize="9" textAnchor="middle">
                r: {cornerRadius} mm
              </text>
            )}
          </>
        )}

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
            <circle data-testid="calibration-marker-a" cx={markerA.x} cy={markerA.y} r="5" fill="#f85149" stroke="#ffffff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            <text x={markerA.x + 8} y={markerA.y - 8} fill="#ffffff" fontSize="11">A</text>
          </g>
        )}
        {markerB && (
          <g pointerEvents="none">
            <circle data-testid="calibration-marker-b" cx={markerB.x} cy={markerB.y} r="5" fill="#3fb950" stroke="#ffffff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
            <text x={markerB.x + 8} y={markerB.y - 8} fill="#ffffff" fontSize="11">B</text>
          </g>
        )}

        <circle cx="0" cy="0" r="3" fill="#f0883e" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
};

export default SvgProfileViewer;
