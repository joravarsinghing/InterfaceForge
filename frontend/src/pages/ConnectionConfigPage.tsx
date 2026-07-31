import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { GeometryPreview } from '../components/GeometryPreview';
import { patchInterface, updateConnectionConfig, validateConnectionConfig } from '../services/api';
import type {
  Connection,
  ConnectionMode,
  ConnectionValidationResult,
  Manufacturing,
  ManufacturingProcess,
  FitMode,
  Project,
} from '../types/schema';

import fitInsideSvg from '../assets/fit_inside.svg';
import fitOverSvg from '../assets/fit_over.svg';

interface ConnectionConfigPageProps {
  project: Project | null;
  onProjectUpdate?: (project: Project) => void;
}

const FitIntentSvgPreview: React.FC<{ mode: FitMode }> = ({ mode }) => {
  const isInside = mode === 'fit_inside';
  const src = isInside ? fitInsideSvg : fitOverSvg;
  const alt = isInside ? 'Fit inside diagram' : 'Fit over diagram';

  return (
    <img
      src={src}
      alt={alt}
      style={{
        width: '100%',
        height: '100%',
        objectFit: 'contain',
        display: 'block',
      }}
    />
  );
};

export const ConnectionConfigPage: React.FC<ConnectionConfigPageProps> = ({
  project,
  onProjectUpdate,
}) => {
  const navigate = useNavigate();

  const [connection, setConnection] = useState<Connection>(
    project?.connection || {
      mode: 'coaxial',
      length_mm: 40.0,
      offset_x_mm: 0.0,
      offset_y_mm: 0.0,
      angle_deg: 0.0,
    }
  );

  const [manufacturing, setManufacturing] = useState<Manufacturing>(
    project?.manufacturing || {
      process: 'fdm',
      material: 'PETG',
      wall_thickness_mm: 2.4,
      clearance_a_mm: 0.3,
      clearance_b_mm: 0.1,
    }
  );

  const interfaceA = project?.interface_a;
  const interfaceB = project?.interface_b;

  const [fitModeA, setFitModeA] = useState<FitMode>(
    interfaceA?.fit_mode || 'fit_over'
  );
  const [fitModeB, setFitModeB] = useState<FitMode>(
    interfaceB?.fit_mode || 'fit_over'
  );

  const [validationResult, setValidationResult] = useState<ConnectionValidationResult>({
    is_valid: true,
    blocking_errors: [],
    warnings: [],
    recommended_values: {
      length_mm: 40.0,
      wall_thickness_mm: 2.4,
      clearance_a_mm: 0.3,
      clearance_b_mm: 0.1,
      offset_x_mm: 0.0,
      offset_y_mm: 0.0,
      angle_deg: 0.0,
    },
  });

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isGeometryLoading, setIsGeometryLoading] = useState(false);
  const prevGeoKeyRef = useRef<string | null>(null);

  // Client & Server Validation Effect
  const runValidation = useCallback(async () => {
    if (!project?.project_id) return;
    const currentGeoKey = `${connection.mode}_${connection.length_mm}_${connection.offset_x_mm}_${connection.offset_y_mm}_${connection.angle_deg}_${manufacturing.wall_thickness_mm}_${manufacturing.clearance_a_mm}_${manufacturing.clearance_b_mm}_${fitModeA}_${fitModeB}`;
    const geometryChanged = prevGeoKeyRef.current !== null && prevGeoKeyRef.current !== currentGeoKey;
    prevGeoKeyRef.current = currentGeoKey;

    if (geometryChanged) {
      setIsGeometryLoading(true);
    }
    setIsValidating(true);
    try {
      const res = await validateConnectionConfig(
        project.project_id,
        connection,
        manufacturing,
        project.project_token
      );
      setValidationResult(res);
    } catch {
      // Local fallback client validation if backend endpoint unavailable
      const localErrors = [];
      if (connection.length_mm <= 0) {
        localErrors.push({
          id: 'IF-CONN-003',
          message: 'Transition length must be a positive number greater than 0 mm.',
          field: 'length_mm',
          recovery_steps: ['Set transition length > 0.'],
        });
      }
      if (manufacturing.wall_thickness_mm <= 0) {
        localErrors.push({
          id: 'IF-MFG-001',
          message: 'Wall thickness must be a positive number greater than 0 mm.',
          field: 'wall_thickness_mm',
          recovery_steps: ['Set wall thickness > 0.'],
        });
      }
      setValidationResult({
        is_valid: localErrors.length === 0,
        blocking_errors: localErrors,
        warnings: [],
        recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
      });
    } finally {
      setIsValidating(false);
      setIsGeometryLoading(false);
    }
  }, [project, connection, manufacturing, fitModeA, fitModeB]);

  useEffect(() => {
    runValidation();
  }, [runValidation]);

  // Mode Selection Handler
  const handleModeSelect = (mode: ConnectionMode) => {
    setConnection((prev) => {
      const updated = { ...prev, mode };
      if (mode === 'coaxial') {
        updated.offset_x_mm = 0.0;
        updated.offset_y_mm = 0.0;
        updated.angle_deg = 0.0;
      } else if (mode === 'offset') {
        updated.angle_deg = 0.0;
      }
      return updated;
    });
  };

  // Form Field Change Handlers
  const handleConnectionChange = (field: keyof Connection, value: number) => {
    setConnection((prev) => ({ ...prev, [field]: value }));
  };

  const handleManufacturingChange = (
    field: keyof Manufacturing,
    value: number | string
  ) => {
    setManufacturing((prev) => ({ ...prev, [field]: value }));
  };

  // Apply Recommended Values
  const handleApplyRecommended = () => {
    const rec = validationResult.recommended_values;
    setConnection((prev) => ({
      ...prev,
      length_mm: rec.length_mm ?? 40.0,
      offset_x_mm: rec.offset_x_mm ?? 0.0,
      offset_y_mm: rec.offset_y_mm ?? 0.0,
      angle_deg: rec.angle_deg ?? 0.0,
    }));
    setManufacturing((prev) => ({
      ...prev,
      wall_thickness_mm: rec.wall_thickness_mm ?? 2.4,
      clearance_a_mm: rec.clearance_a_mm ?? 0.3,
      clearance_b_mm: rec.clearance_b_mm ?? 0.1,
    }));
  };

  // Save & Proceed
  const handleSaveAndProceed = async () => {
    if (!project?.project_id) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      if (project.interface_a.fit_mode !== fitModeA) {
        await patchInterface(project.project_id, 'interface_a', { fit_mode: fitModeA }, project.project_token);
      }
      if (project.interface_b.fit_mode !== fitModeB) {
        await patchInterface(project.project_id, 'interface_b', { fit_mode: fitModeB }, project.project_token);
      }
      const updatedProject = await updateConnectionConfig(
        project.project_id,
        connection,
        manufacturing,
        project.project_token
      );
      if (onProjectUpdate) {
        onProjectUpdate(updatedProject);
      }
      navigate('/step4');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save connection configuration.';
      setSaveError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const fieldErrorMap: Record<string, string> = {};
  if (connection.length_mm <= 0) {
    fieldErrorMap['length_mm'] = 'Transition length must be a positive number greater than 0 mm.';
  }
  if (manufacturing.wall_thickness_mm <= 0) {
    fieldErrorMap['wall_thickness_mm'] = 'Wall thickness must be a positive number greater than 0 mm.';
  }
  validationResult.blocking_errors.forEach((err) => {
    if (err.field) {
      fieldErrorMap[err.field] = err.message;
    }
  });

  const isFormValid =
    validationResult.is_valid &&
    validationResult.blocking_errors.length === 0 &&
    connection.length_mm > 0 &&
    manufacturing.wall_thickness_mm > 0;

  const canProceed = isFormValid && !isValidating && !isSaving;

  const summaryBlockingErrors = validationResult.blocking_errors.filter(
    (err) => err.id !== 'IF-CONN-003'
  );

  return (
    <div className="connection-config-page container" style={{ padding: '2rem 1rem' }}>
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h2>Step 3 - Guided Connection &amp; Manufacturing Configuration</h2>
        <p style={{ color: '#8b949e' }}>
          Configure transition geometry, lateral offsets, inclination angle, wall thickness, and print clearances.
        </p>
      </header>

      {/* Interface Summary Bar */}
      <section
        className="interface-summary-bar card"
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
          <div>
            <strong style={{ color: '#3fb950' }}>APPROVED Interface A:</strong>{' '}
            <span style={{ color: '#e6edf3' }}>
              {interfaceA?.profile_type?.toUpperCase() || 'CIRCLE'}
            </span>
          </div>
          <div>
            <strong style={{ color: '#a371f7' }}>APPROVED Interface B:</strong>{' '}
            <span style={{ color: '#e6edf3' }}>
              {interfaceB?.profile_type?.toUpperCase() || 'CIRCLE'}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate('/step2/analysis')}
          style={{ cursor: 'pointer' }}
        >
            Back to Profile Review
        </button>
      </section>

      <section className="fit-intent-panel card" style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem' }}>
        <h3 style={{ marginTop: 0, color: '#f0f6fc', marginBottom: '0.75rem' }}>Fit Intent</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.25rem' }}>
          <div>
            <label
              htmlFor="fit_intent_mode_a"
              style={{ display: 'block', color: '#f0f6fc', fontWeight: 'bold', marginBottom: '0.35rem' }}
            >
              Interface A
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                id="fit_intent_mode_a"
                value={fitModeA}
                onChange={(event) => setFitModeA(event.target.value as FitMode)}
                style={{
                  flex: 1,
                  height: '42px',
                  padding: '0 0.75rem',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  color: '#f0f6fc',
                  borderRadius: '4px',
                  fontSize: '0.9rem',
                }}
              >
                <option value="fit_over">Fit over the outside</option>
                <option value="fit_inside">Fit inside the opening</option>
              </select>
              <div
                className="fit-intent-preview-box"
                data-testid="fit-intent-preview-a"
                style={{
                  width: '64px',
                  height: '42px',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '4px',
                  padding: '3px',
                  boxSizing: 'border-box',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <FitIntentSvgPreview mode={fitModeA} />
              </div>
            </div>
          </div>

          <div>
            <label
              htmlFor="fit_intent_mode_b"
              style={{ display: 'block', color: '#f0f6fc', fontWeight: 'bold', marginBottom: '0.35rem' }}
            >
              Interface B
            </label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                id="fit_intent_mode_b"
                value={fitModeB}
                onChange={(event) => setFitModeB(event.target.value as FitMode)}
                style={{
                  flex: 1,
                  height: '42px',
                  padding: '0 0.75rem',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  color: '#f0f6fc',
                  borderRadius: '4px',
                  fontSize: '0.9rem',
                }}
              >
                <option value="fit_over">Fit over the outside</option>
                <option value="fit_inside">Fit inside the opening</option>
              </select>
              <div
                className="fit-intent-preview-box"
                data-testid="fit-intent-preview-b"
                style={{
                  width: '64px',
                  height: '42px',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '4px',
                  padding: '3px',
                  boxSizing: 'border-box',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <FitIntentSvgPreview mode={fitModeB} />
              </div>
            </div>
          </div>
        </div>
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        {/* Left Column: Form & Mode Cards */}
        <div>
          {/* Connection Mode Selection Cards */}
          <fieldset style={{ border: 'none', padding: 0, margin: 0, marginBottom: '1.5rem' }}>
            <legend style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: '#f0f6fc' }}>
              Connection Alignment Mode
            </legend>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
              {[
                {
                  id: 'coaxial' as ConnectionMode,
                  title: 'Coaxial',
                  icon: '',
                  desc: 'Straight axial connection sharing a common center axis.',
                },
                {
                  id: 'offset' as ConnectionMode,
                  title: 'Parallel Offset',
                  icon: '',
                  desc: 'Parallel alignment with lateral X/Y offsets.',
                },
                {
                  id: 'angled' as ConnectionMode,
                  title: 'Limited Angle',
                  icon: '',
                  desc: 'Inclined transition angle (up to 45 deg) with optional offsets.',
                },
              ].map((modeCard) => {
                const isSelected = connection.mode === modeCard.id;
                return (
                  <button
                    key={modeCard.id}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => handleModeSelect(modeCard.id)}
                    style={{
                      background: isSelected ? '#1f6feb22' : '#161b22',
                      border: isSelected ? '2px solid #58a6ff' : '1px solid #30363d',
                      borderRadius: '8px',
                      padding: '0.75rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      color: '#f0f6fc',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.25rem',
                    }}
                  >
                    <div style={{ fontWeight: 'bold', fontSize: '0.95rem' }}>
                      {modeCard.icon} {modeCard.title} {isSelected ? '' : ''}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#8b949e' }}>{modeCard.desc}</div>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Parameter Inputs Form */}
          <div
            className="card"
            style={{
              background: '#161b22',
              border: '1px solid #30363d',
              borderRadius: '8px',
              padding: '1.25rem',
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: '1rem', color: '#f0f6fc' }}>
              Geometric &amp; Manufacturing Parameters
            </h3>

            {/* Transition Length */}
            <div style={{ marginBottom: '1rem' }}>
              <label
                htmlFor="length_mm"
                style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
              >
                Transition Length (mm):
              </label>
              <input
                id="length_mm"
                type="number"
                step="0.5"
                min="1"
                max="300"
                value={connection.length_mm}
                onChange={(e) => handleConnectionChange('length_mm', parseFloat(e.target.value) || 0)}
                aria-invalid={!!fieldErrorMap['length_mm']}
                aria-describedby={fieldErrorMap['length_mm'] ? 'length_mm-error' : undefined}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  background: '#0d1117',
                  border: fieldErrorMap['length_mm'] ? '2px solid #f85149' : '1px solid #30363d',
                  color: '#f0f6fc',
                  borderRadius: '4px',
                }}
              />
              {fieldErrorMap['length_mm'] && (
                <span id="length_mm-error" style={{ color: '#f85149', fontSize: '0.85rem' }}>
                    {fieldErrorMap['length_mm']}
                </span>
              )}
            </div>

            {/* X Offset (Offset & Angled modes) */}
            {connection.mode !== 'coaxial' && (
              <div style={{ marginBottom: '1rem' }}>
                <label
                  htmlFor="offset_x_mm"
                  style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
                >
                  X Offset (mm):
                </label>
                <input
                  id="offset_x_mm"
                  type="number"
                  step="0.5"
                  value={connection.offset_x_mm}
                  onChange={(e) => handleConnectionChange('offset_x_mm', parseFloat(e.target.value) || 0)}
                  aria-invalid={!!fieldErrorMap['offset_x_mm']}
                  aria-describedby={fieldErrorMap['offset_x_mm'] ? 'offset_x_mm-error' : undefined}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#0d1117',
                    border: fieldErrorMap['offset_x_mm'] ? '2px solid #f85149' : '1px solid #30363d',
                    color: '#f0f6fc',
                    borderRadius: '4px',
                  }}
                />
                {fieldErrorMap['offset_x_mm'] && (
                  <span id="offset_x_mm-error" style={{ color: '#f85149', fontSize: '0.85rem' }}>
                      {fieldErrorMap['offset_x_mm']}
                  </span>
                )}
              </div>
            )}

            {/* Y Offset (Offset & Angled modes) */}
            {connection.mode !== 'coaxial' && (
              <div style={{ marginBottom: '1rem' }}>
                <label
                  htmlFor="offset_y_mm"
                  style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
                >
                  Y Offset (mm):
                </label>
                <input
                  id="offset_y_mm"
                  type="number"
                  step="0.5"
                  value={connection.offset_y_mm}
                  onChange={(e) => handleConnectionChange('offset_y_mm', parseFloat(e.target.value) || 0)}
                  aria-invalid={!!fieldErrorMap['offset_y_mm']}
                  aria-describedby={fieldErrorMap['offset_y_mm'] ? 'offset_y_mm-error' : undefined}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#0d1117',
                    border: fieldErrorMap['offset_y_mm'] ? '2px solid #f85149' : '1px solid #30363d',
                    color: '#f0f6fc',
                    borderRadius: '4px',
                  }}
                />
                {fieldErrorMap['offset_y_mm'] && (
                  <span id="offset_y_mm-error" style={{ color: '#f85149', fontSize: '0.85rem' }}>
                      {fieldErrorMap['offset_y_mm']}
                  </span>
                )}
              </div>
            )}

            {/* Angle (Angled mode) */}
            {connection.mode === 'angled' && (
              <div style={{ marginBottom: '1rem' }}>
                <label
                  htmlFor="angle_deg"
                  style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
                >
                  Transition Angle (deg):
                </label>
                <input
                  id="angle_deg"
                  type="number"
                  step="1"
                  min="0"
                  max="45"
                  value={connection.angle_deg}
                  onChange={(e) => handleConnectionChange('angle_deg', parseFloat(e.target.value) || 0)}
                  aria-invalid={!!fieldErrorMap['angle_deg']}
                  aria-describedby={fieldErrorMap['angle_deg'] ? 'angle_deg-error' : undefined}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#0d1117',
                    border: fieldErrorMap['angle_deg'] ? '2px solid #f85149' : '1px solid #30363d',
                    color: '#f0f6fc',
                    borderRadius: '4px',
                  }}
                />
                {fieldErrorMap['angle_deg'] && (
                  <span id="angle_deg-error" style={{ color: '#f85149', fontSize: '0.85rem' }}>
                      {fieldErrorMap['angle_deg']}
                  </span>
                )}
              </div>
            )}

            {/* Wall Thickness */}
            <div style={{ marginBottom: '1rem' }}>
              <label
                htmlFor="wall_thickness_mm"
                style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
              >
                Wall Thickness (mm):
              </label>
              <input
                id="wall_thickness_mm"
                type="number"
                step="0.2"
                min="0.4"
                max="20"
                value={manufacturing.wall_thickness_mm}
                onChange={(e) =>
                  handleManufacturingChange('wall_thickness_mm', parseFloat(e.target.value) || 0)
                }
                aria-invalid={!!fieldErrorMap['wall_thickness_mm']}
                aria-describedby={fieldErrorMap['wall_thickness_mm'] ? 'wall_thickness_mm-error' : undefined}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  background: '#0d1117',
                  border: fieldErrorMap['wall_thickness_mm'] ? '2px solid #f85149' : '1px solid #30363d',
                  color: '#f0f6fc',
                  borderRadius: '4px',
                }}
              />
              {fieldErrorMap['wall_thickness_mm'] && (
                <span id="wall_thickness_mm-error" style={{ color: '#f85149', fontSize: '0.85rem' }}>
                    {fieldErrorMap['wall_thickness_mm']}
                </span>
              )}
            </div>

            {/* Clearance A & Clearance B */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
              <div>
                <label
                  htmlFor="clearance_a_mm"
                  style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
                >
                  Clearance A (mm):
                </label>
                <input
                  id="clearance_a_mm"
                  type="number"
                  step="0.05"
                  min="0"
                  max="5"
                  value={manufacturing.clearance_a_mm}
                  onChange={(e) =>
                    handleManufacturingChange('clearance_a_mm', parseFloat(e.target.value) || 0)
                  }
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    color: '#f0f6fc',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="clearance_b_mm"
                  style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
                >
                  Clearance B (mm):
                </label>
                <input
                  id="clearance_b_mm"
                  type="number"
                  step="0.05"
                  min="0"
                  max="5"
                  value={manufacturing.clearance_b_mm}
                  onChange={(e) =>
                    handleManufacturingChange('clearance_b_mm', parseFloat(e.target.value) || 0)
                  }
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    color: '#f0f6fc',
                    borderRadius: '4px',
                  }}
                />
              </div>
            </div>

            {/* Manufacturing Process Selector */}
            <div>
              <label
                htmlFor="mfg_process"
                style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem' }}
              >
                Manufacturing Process:
              </label>
              <select
                id="mfg_process"
                value={manufacturing.process}
                onChange={(e) =>
                  handleManufacturingChange('process', e.target.value as ManufacturingProcess)
                }
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  color: '#f0f6fc',
                  borderRadius: '4px',
                }}
              >
                <option value="fdm">3D print - FDM</option>
                <option value="sla">3D print - SLA/DLP</option>
                <option value="cnc">CNC Milling</option>
              </select>
            </div>
          </div>
        </div>

        {/* Right Column: Live 2D Visual Guide & Validation Summaries */}
        <div>
          <h3 style={{ marginTop: 0, marginBottom: '0.5rem', color: '#f0f6fc' }}>
            Live 2D Transition Schematic
          </h3>
          <GeometryPreview
            project={{
              ...project!,
              connection,
              manufacturing,
              loft_plan: isFormValid ? (validationResult.loft_plan ?? project!.loft_plan) : undefined,
              interface_a: { ...project!.interface_a, fit_mode: fitModeA },
              interface_b: { ...project!.interface_b, fit_mode: fitModeB },
            }}
            isLoading={isGeometryLoading}
          />

          {/* Validation Status Panel */}
          <div
            className="validation-status-panel card"
            style={{
              background: '#161b22',
              border: '1px solid #30363d',
              borderRadius: '8px',
              padding: '1rem',
              marginTop: '1.25rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: 0, color: '#f0f6fc' }}>Validation Summary</h4>
              <span
                style={{
                  padding: '0.25rem 0.5rem',
                  borderRadius: '4px',
                  fontWeight: 'bold',
                  fontSize: '0.85rem',
                  background: !isFormValid
                    ? 'rgba(248, 81, 73, 0.2)'
                    : validationResult.warnings.length > 0
                    ? 'rgba(210, 153, 34, 0.2)'
                    : 'rgba(63, 185, 80, 0.2)',
                  color: !isFormValid
                    ? '#f85149'
                    : validationResult.warnings.length > 0
                    ? '#d29922'
                    : '#3fb950',
                  border: !isFormValid
                    ? '1px solid #f85149'
                    : validationResult.warnings.length > 0
                    ? '1px solid #d29922'
                    : '1px solid #3fb950',
                }}
              >
                {!isFormValid
                  ? ' ERRORS DETECTED'
                  : validationResult.warnings.length > 0
                  ? ' VALID WITH WARNINGS'
                  : ' VALID CONFIGURATION'}
              </span>
            </div>

            {/* Blocking Errors Summary */}
            {summaryBlockingErrors.length > 0 && (
              <div
                style={{
                  marginTop: '0.75rem',
                  padding: '0.75rem',
                  background: 'rgba(248, 81, 73, 0.1)',
                  borderLeft: '4px solid #f85149',
                  borderRadius: '4px',
                }}
              >
                <strong style={{ color: '#f85149' }}>Blocking Errors ({summaryBlockingErrors.length}):</strong>
                <ul style={{ margin: '0.5rem 0 0 1.25rem', padding: 0, color: '#f0f6fc', fontSize: '0.9rem' }}>
                  {summaryBlockingErrors.map((err) => (
                    <li key={err.id}>
                      <strong>[{err.id}]</strong> {err.message}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="btn btn-sm btn-outline"
                  onClick={handleApplyRecommended}
                  style={{ marginTop: '0.5rem', cursor: 'pointer' }}
                >
                    Apply Recommended Values
                </button>
              </div>
            )}

            {/* Non-Blocking Warnings Summary */}
            {validationResult.warnings.length > 0 && (
              <div
                style={{
                  marginTop: '0.75rem',
                  padding: '0.75rem',
                  background: 'rgba(210, 153, 34, 0.1)',
                  borderLeft: '4px solid #d29922',
                  borderRadius: '4px',
                }}
              >
                <strong style={{ color: '#d29922' }}>Manufacturing Warnings ({validationResult.warnings.length}):</strong>
                <ul style={{ margin: '0.5rem 0 0 1.25rem', padding: 0, color: '#f0f6fc', fontSize: '0.9rem' }}>
                  {validationResult.warnings.map((warn) => (
                    <li key={warn.id}>
                      {warn.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {saveError && (
              <div style={{ marginTop: '0.75rem', color: '#f85149', fontSize: '0.9rem' }}>
                  {saveError}
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ marginTop: '1.25rem', display: 'flex', gap: '1rem' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSaveAndProceed}
                disabled={!canProceed}
                style={{
                  flex: 1,
                  padding: '0.75rem',
                  fontWeight: 'bold',
                  cursor: canProceed ? 'pointer' : 'not-allowed',
                  background: canProceed ? undefined : '#0d1117',
                  color: canProceed ? undefined : '#3fb950',
                  border: canProceed ? undefined : '1px solid #3fb950',
                  boxShadow: canProceed ? undefined : 'none',
                  opacity: 1,
                }}
              >
                {isSaving ? 'Saving...' : 'Save Connection & Continue to Model Generation'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

