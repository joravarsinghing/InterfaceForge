import React, { useMemo, useState } from 'react';
import type { InterfaceDefinition, Project } from '../types/schema';

type View = 'front' | 'side' | 'top' | 'isometric';
interface GeometryPreviewProps { project: Project; className?: string; boundingBox?: { x_mm: number; y_mm: number; z_mm: number }; volumeCm3?: number | null; featured?: boolean; summary?: React.ReactNode; }
type Point3 = [number, number, number];

const dimension = (iface: InterfaceDefinition, id: string, fallback: number) => iface.dimensions.find((item) => item.id === id)?.value || fallback;

function ring(iface: InterfaceDefinition, outer: boolean, wall: number, clearance: number): Array<[number, number]> {
  if (iface.profile_type === 'circle') {
    const diameter = dimension(iface, 'outer_diameter', 50) + 2 * clearance - (outer ? 0 : 2 * wall);
    return Array.from({ length: 24 }, (_, i) => { const theta = (2 * Math.PI * i) / 24; const radius = Math.max(diameter, 2) / 2; return [radius * Math.cos(theta), radius * Math.sin(theta)]; });
  }
  const width = dimension(iface, 'width', 50) + 2 * clearance - (outer ? 0 : 2 * wall);
  const height = dimension(iface, 'height', 50) + 2 * clearance - (outer ? 0 : 2 * wall);
  const hw = Math.max(width / 2, 1), hh = Math.max(height / 2, 1);
  const radius = iface.profile_type === 'rounded_rectangle' ? Math.min(dimension(iface, 'corner_radius', 5), hw * 0.8, hh * 0.8) : 0;
  if (!radius) { const corners: Array<[number, number]> = [[hw, 0], [hw, hh], [-hw, hh], [-hw, -hh]]; return Array.from({ length: 24 }, (_, i) => { const t = (i / 24) * 4; const edge = Math.floor(t) % 4; const fraction = t - Math.floor(t); const start = corners[edge], end = corners[(edge + 1) % 4]; return [start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction]; }); }
  return Array.from({ length: 24 }, (_, i) => { const t = (2 * Math.PI * i) / 24; const cx = Math.sign(Math.cos(t)) * (hw - radius); const cy = Math.sign(Math.sin(t)) * (hh - radius); return [cx + radius * Math.cos(t), cy + radius * Math.sin(t)]; });
}

function project(point: Point3, view: View): [number, number] {
  const [x, y, z] = point;
  if (view === 'front') return [x, z];
  if (view === 'side') return [y, z];
  if (view === 'top') return [x, y];
  return [x - 0.62 * y, z - 0.36 * y];
}

export const GeometryPreview: React.FC<GeometryPreviewProps> = ({ project: model, className, boundingBox, volumeCm3, featured = false, summary }) => {
  const [view, setView] = useState<View>('isometric');
  const rings = useMemo(() => {
    const { interface_a: a, interface_b: b, connection, manufacturing } = model;
    const outerA = ring(a, true, manufacturing.wall_thickness_mm, manufacturing.clearance_a_mm);
    const innerA = ring(a, false, manufacturing.wall_thickness_mm, manufacturing.clearance_a_mm);
    const outerB = ring(b, true, manufacturing.wall_thickness_mm, manufacturing.clearance_b_mm);
    const innerB = ring(b, false, manufacturing.wall_thickness_mm, manufacturing.clearance_b_mm);
    const angle = (connection.angle_deg * Math.PI) / 180;
    const transform = (p: [number, number], top: boolean): Point3 => { const [x, y] = p; return top ? [x + connection.offset_x_mm, y * Math.cos(angle) + connection.offset_y_mm, connection.length_mm + y * Math.sin(angle)] : [x, y, 0]; };
    return { outerA, innerA, outerB, innerB, points: [...outerA.map((p) => transform(p, false)), ...innerA.map((p) => transform(p, false)), ...outerB.map((p) => transform(p, true)), ...innerB.map((p) => transform(p, true))] };
  }, [model]);
  const projected = rings.points.map((point) => project(point, view));
  const minX = Math.min(...projected.map((p) => p[0])), maxX = Math.max(...projected.map((p) => p[0]));
  const minY = Math.min(...projected.map((p) => p[1])), maxY = Math.max(...projected.map((p) => p[1]));
  const scale = Math.min(340 / Math.max(maxX - minX, 1), 230 / Math.max(maxY - minY, 1));
  const map = (point: Point3) => { const [x, y] = project(point, view); return [200 + (x - (minX + maxX) / 2) * scale, 150 - (y - (minY + maxY) / 2) * scale] as const; };
  const n = rings.outerA.length;
  const path = (start: number) => Array.from({ length: n }, (_, i) => map(rings.points[start + i]).join(',')).join(' ');
  const buttons: View[] = ['front', 'side', 'top', 'isometric'];
  const controls = <div className="geometry-preview-controls" style={{ display: 'flex', gap: '0.35rem', marginBottom: '0.4rem' }}>{buttons.map((item) => <button className="geometry-preview-view-button" key={item} type="button" aria-pressed={view === item} onClick={() => setView(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>;
  const info = <div className="geometry-preview-info" style={{ color: '#8b949e', fontSize: '0.75rem', marginTop: '0.35rem' }}>{boundingBox ? 'Bounds: ' + boundingBox.x_mm + ' x ' + boundingBox.y_mm + ' x ' + boundingBox.z_mm + ' mm' : 'Length: ' + model.connection.length_mm.toFixed(1) + ' mm'}{volumeCm3 != null ? ' | Volume: ' + volumeCm3.toFixed(3) + ' cm3' : ''}</div>;
  const canvas = <svg viewBox="0 0 400 300" role="img" aria-label={'Isometric adapter preview using X, Y, and Z coordinates (' + view + ' view)'} style={{ width: '100%', height: 'auto', background: '#0d1117' }}>
    <polygon points={path(0)} fill="#238636" fillOpacity="0.18" stroke="#3fb950" />
    <polygon points={path(n)} fill="#0d1117" fillOpacity="0.7" stroke="#3fb950" strokeDasharray="3 3" />
    <polygon points={path(2 * n)} fill="#238636" fillOpacity="0.12" stroke="#3fb950" />
    <polygon points={path(3 * n)} fill="#0d1117" fillOpacity="0.7" stroke="#3fb950" strokeDasharray="3 3" />
    {Array.from({ length: n }, (_, i) => { const a = map(rings.points[i]), b = map(rings.points[2 * n + i]); return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#3fb950" strokeOpacity="0.65" />; })}
    <text x="12" y="18" fill="#3fb950" fontSize="11">CURRENT GEOMETRY - {view.toUpperCase()}</text>
    <text x="12" y="292" fill="#8b949e" fontSize="10">X/Y/Z isometric projection | L = {model.connection.length_mm.toFixed(1)} mm</text>
  </svg>;
  if (featured) {
    return <div className={className + ' geometry-preview-featured'} data-testid="shared-geometry-preview">
      <div className="geometry-preview-featured-sidebar">{controls}{info}{summary}</div>
      <div className="geometry-preview-featured-canvas">{canvas}</div>
    </div>;
  }
  return <div className={className} data-testid="shared-geometry-preview">{controls}{canvas}{info}</div>;};
