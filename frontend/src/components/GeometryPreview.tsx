import React, { useMemo, useState } from 'react';
import type { LoftPoint, Project } from '../types/schema';

type View = 'front' | 'side' | 'top' | 'isometric';
type Point3 = [number, number, number];
interface GeometryPreviewProps { project: Project; className?: string; boundingBox?: { x_mm: number; y_mm: number; z_mm: number }; volumeCm3?: number | null; featured?: boolean; summary?: React.ReactNode; isLoading?: boolean; colorCodeInterfaces?: boolean; }
function projectPoint(point: Point3, view: View): [number, number] { const [x,y,z]=point; if(view==='front') return [x,z]; if(view==='side') return [y,z]; if(view==='top') return [x,y]; return [x-0.62*y,z-0.36*y]; }
export const GeometryPreview: React.FC<GeometryPreviewProps> = ({ project: model, className, boundingBox, volumeCm3, featured=false, summary, isLoading=false, colorCodeInterfaces=false }) => {
  const [view,setView]=useState<View>('isometric');
  const sections = model.loft_plan?.sections ?? [];
  const rings = useMemo(() => sections.map((section) => ({ outer: section.outer.map((p: LoftPoint): Point3 => [p.x,p.y,section.z_mm]), inner: section.inner.map((p: LoftPoint): Point3 => [p.x,p.y,section.z_mm]) })), [sections]);
  const points = rings.flatMap((r) => [...r.outer,...r.inner]);
  const projected = points.map((p) => projectPoint(p,view));
  const minX = projected.length ? Math.min(...projected.map(p=>p[0])) : -1, maxX = projected.length ? Math.max(...projected.map(p=>p[0])) : 1;
  const minY = projected.length ? Math.min(...projected.map(p=>p[1])) : -1, maxY = projected.length ? Math.max(...projected.map(p=>p[1])) : 1;
  const scale=Math.min(340/Math.max(maxX-minX,1),230/Math.max(maxY-minY,1));
  const map=(p:Point3)=>{const [x,y]=projectPoint(p,view);return [200+(x-(minX+maxX)/2)*scale,150-(y-(minY+maxY)/2)*scale] as const;};
  const path=(ring:Point3[])=>ring.map(p=>map(p).join(',')).join(' ');
  const interfaceAColor = '#ff00aa';
  const interfaceBColor = '#ff9100';
  const hasInterfaceAExtension = (model.connection?.extension_a_mm ?? 0) > 0;
  const hasInterfaceBExtension = (model.connection?.extension_b_mm ?? 0) > 0;
  const previewColor = (index: number) => colorCodeInterfaces && rings.length > 1
    ? index === 0 ? interfaceAColor : index === rings.length - 1 ? interfaceBColor : '#3fb950'
    : '#3fb950';
  const endpointLabelPosition = (index: number, yOffset: number) => {
    const endpoint = rings[index];
    if (!endpoint) return { x: 200, y: 150 + yOffset };
    const mapped = endpoint.outer.map(map);
    if (mapped.length === 0) return { x: 200, y: 150 + yOffset };
    return {
      x: mapped.reduce((sum, point) => sum + point[0], 0) / mapped.length,
      y: mapped.reduce((sum, point) => sum + point[1], 0) / mapped.length + yOffset,
    };
  };
  const interfaceAPosition = endpointLabelPosition(0, 18);
  const interfaceBPosition = endpointLabelPosition(Math.max(rings.length - 1, 0), -12);
  const controls=<div className="geometry-preview-controls" style={{display:'flex',gap:'0.35rem',marginBottom:'0.4rem'}}>{(['front','side','top','isometric'] as View[]).map(item=><button className="geometry-preview-view-button" key={item} type="button" aria-pressed={view===item} onClick={()=>setView(item)}>{item === 'side' ? 'Left' : item[0].toUpperCase()+item.slice(1)}</button>)}</div>;
  const progressBar = isLoading ? (
    <div
      className="preview-progress-bar-container"
      data-testid="preview-loading-bar"
      aria-label="Loading preview"
      role="progressbar"
      style={{
        width: '100%',
        height: '4px',
        background: 'rgba(255, 255, 255, 0.1)',
        borderRadius: '2px',
        overflow: 'hidden',
        marginBottom: '0.4rem',
        position: 'relative',
      }}
    >
      <div
        className="preview-progress-bar-fill"
        style={{
          height: '100%',
          width: '50%',
          background: 'linear-gradient(90deg, transparent, #3fb950, #58a6ff, transparent)',
          borderRadius: '2px',
          animation: 'progressBarSlide 1.2s infinite ease-in-out',
        }}
      />
    </div>
  ) : null;
  const info=<div className="geometry-preview-info" style={{color:'#8b949e',fontSize:'0.75rem',marginTop:'0.35rem'}}>{boundingBox ? `Bounds: ${boundingBox.x_mm} x ${boundingBox.y_mm} x ${boundingBox.z_mm} mm` : `Sections: ${sections.length || 0}`}{volumeCm3!=null ? ` | Volume: ${volumeCm3.toFixed(3)} cm3` : ''}</div>;
  const canvas=<svg viewBox="0 0 400 300" role="img" aria-label={'Persisted LoftPlan preview using X, Y, and Z coordinates ('+view+' view)'} style={{width:'100%',height:'auto',background:'#0d1117'}}>
    {rings.map((r,index)=><React.Fragment key={index}><polygon points={path(r.outer)} fill={previewColor(index)} fillOpacity={index === 0 || index === rings.length - 1 ? '0.16' : '0.12'} stroke={previewColor(index)}/><polygon points={path(r.inner)} fill="#0d1117" fillOpacity="0.7" stroke={previewColor(index)} strokeDasharray="3 3"/></React.Fragment>)}
    {rings.slice(0,-1).flatMap((r,index)=>r.outer.map((a,i)=>{const b=rings[index+1].outer[i]; const ap=map(a),bp=map(b); return <line key={`${index}-${i}`} x1={ap[0]} y1={ap[1]} x2={bp[0]} y2={bp[1]} stroke={colorCodeInterfaces && hasInterfaceAExtension && index === 0 ? interfaceAColor : colorCodeInterfaces && hasInterfaceBExtension && index === rings.length - 2 ? interfaceBColor : '#3fb950'} strokeOpacity="0.65"/>;}))}
    {colorCodeInterfaces && rings.length > 0 && <>
      <text data-testid="interface-a-preview-label" x={interfaceAPosition.x} y={interfaceAPosition.y} fill={interfaceAColor} fontSize="11" fontWeight="bold" textAnchor="middle">Interface A</text>
      <text data-testid="interface-b-preview-label" x={interfaceBPosition.x} y={interfaceBPosition.y} fill={interfaceBColor} fontSize="11" fontWeight="bold" textAnchor="middle">Interface B</text>
    </>}
    <text x="12" y="18" fill="#3fb950" fontSize="11">PERSISTED LOFT PLAN - {view.toUpperCase()}</text>
  </svg>;
  const body=<>{controls}{progressBar}{canvas}{info}</>;
  if(featured) return <div className={className+' geometry-preview-featured'} data-testid="shared-geometry-preview"><div className="geometry-preview-featured-sidebar">{controls}{progressBar}{info}{summary}</div><div className="geometry-preview-featured-canvas">{canvas}</div></div>;
  return <div className={className} data-testid="shared-geometry-preview">{body}</div>;
};
