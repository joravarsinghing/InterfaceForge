import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { SvgProfileViewer } from '../components/SvgProfileViewer';
import { approveInterface, patchInterface } from '../services/api';
import {
  Dimension,
  DimensionProvenance,
  InterfaceDefinition,
  ProfileType,
  Project,
} from '../types/schema';

interface ProfileReviewPageProps {
  interfaceId: 'interface_a' | 'interface_b';
  project: Project | null;
  onProjectUpdate?: (project: Project) => void;
}

export const ProfileReviewPage: React.FC<ProfileReviewPageProps> = ({
  interfaceId,
  project,
  onProjectUpdate,
}) => {
  const navigate = useNavigate();
  const isInterfaceB = interfaceId === 'interface_b';
  const interfaceName = isInterfaceB ? 'Interface B' : 'Interface A';
  const targetInterface: InterfaceDefinition | undefined = isInterfaceB
    ? project?.interface_b
    : project?.interface_a;

  // Local state for interactive form fields
  const [profileType, setProfileType] = useState<ProfileType>(
    targetInterface?.profile_type || 'circle'
  );
  const [dimensions, setDimensions] = useState<Dimension[]>(
    targetInterface?.dimensions || []
  );
  const [isEditing, setIsEditing] = useState<boolean>(!targetInterface?.approved);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Sync state when project updates
  useEffect(() => {
    if (targetInterface) {
      setProfileType(targetInterface.profile_type || 'circle');
      setDimensions(targetInterface.dimensions || []);
      if (targetInterface.approved) {
        setIsEditing(false);
      }
    }
  }, [targetInterface]);

  // Handle profile type changes & supply standard default dimensions per shape
  const handleProfileTypeChange = (newType: ProfileType) => {
    setProfileType(newType);
    if (newType === 'circle') {
      setDimensions([
        {
          id: 'outer_diameter',
          label: 'Outer Diameter',
          value: 50.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: true,
        },
        {
          id: 'wall_thickness',
          label: 'Wall Thickness',
          value: 5.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: false,
        },
      ]);
    } else if (newType === 'rectangle') {
      setDimensions([
        {
          id: 'width',
          label: 'Width',
          value: 60.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: true,
        },
        {
          id: 'height',
          label: 'Height',
          value: 40.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: true,
        },
      ]);
    } else if (newType === 'rounded_rectangle') {
      setDimensions([
        {
          id: 'width',
          label: 'Width',
          value: 80.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: true,
        },
        {
          id: 'height',
          label: 'Height',
          value: 50.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: true,
        },
        {
          id: 'corner_radius',
          label: 'Corner Radius',
          value: 5.0,
          unit: 'mm',
          provenance: 'user_entered',
          confidence: 1.0,
          critical: false,
        },
      ]);
    }
  };

  // Dimension editing handlers
  const handleDimensionValueChange = (index: number, valStr: string) => {
    const val = parseFloat(valStr);
    const updated = [...dimensions];
    updated[index] = {
      ...updated[index],
      value: isNaN(val) ? 0 : val,
    };
    setDimensions(updated);
  };

  const handleProvenanceChange = (
    index: number,
    prov: DimensionProvenance
  ) => {
    const updated = [...dimensions];
    updated[index] = {
      ...updated[index],
      provenance: prov,
    };
    setDimensions(updated);
  };

  const handleConfidenceChange = (index: number, confStr: string) => {
    const conf = parseFloat(confStr);
    const updated = [...dimensions];
    updated[index] = {
      ...updated[index],
      confidence: isNaN(conf) ? 0 : Math.max(0, Math.min(1, conf)),
    };
    setDimensions(updated);
  };

  const handleCriticalToggle = (index: number, isCritical: boolean) => {
    const updated = [...dimensions];
    updated[index] = {
      ...updated[index],
      critical: isCritical,
    };
    setDimensions(updated);
  };

  const handleAddDimension = () => {
    const newDim: Dimension = {
      id: `custom_dim_${dimensions.length + 1}`,
      label: `Custom Dimension ${dimensions.length + 1}`,
      value: 10.0,
      unit: 'mm',
      provenance: 'user_entered',
      confidence: 1.0,
      critical: false,
    };
    setDimensions([...dimensions, newDim]);
  };

  const handleRemoveDimension = (index: number) => {
    setDimensions(dimensions.filter((_, idx) => idx !== index));
  };

  // Structural Validation Summary Calculation
  const knownCount = dimensions.filter(
    (d) => d.provenance !== 'unresolved' && d.value > 0 && isFinite(d.value)
  ).length;

  const validationErrors: string[] = [];
  if (knownCount < 2) {
    validationErrors.push(
      `At least two known dimensions are required (found ${knownCount}).`
    );
  }

  dimensions.forEach((d) => {
    if (!isFinite(d.value) || d.value <= 0) {
      validationErrors.push(`Dimension "${d.label}" must be a positive finite value.`);
    }
    if (!isFinite(d.confidence) || d.confidence < 0 || d.confidence > 1) {
      validationErrors.push(`Dimension "${d.label}" confidence must be between 0.0 and 1.0.`);
    }
    if (d.critical && d.provenance === 'unresolved') {
      validationErrors.push(`Critical dimension "${d.label}" is unresolved.`);
    }
  });

  if (isInterfaceB && !project?.interface_a.approved) {
    validationErrors.push('Prerequisite: Interface A must be approved first.');
  }

  const isFormValid = validationErrors.length === 0;

  // Actions
  const handleUpdateProfile = async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      const updatedProject = await patchInterface(
        project.project_id,
        interfaceId,
        {
          profile_type: profileType,
          dimensions,
        },
        project.project_token
      );
      setLoading(false);
      if (onProjectUpdate) {
        onProjectUpdate(updatedProject);
      }
    } catch (err: unknown) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to update profile');
    }
  };

  const handleApprove = async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      // First update profile if needed
      await patchInterface(
        project.project_id,
        interfaceId,
        {
          profile_type: profileType,
          dimensions,
        },
        project.project_token
      );

      // Approve interface
      const approvedProject = await approveInterface(
        project.project_id,
        interfaceId,
        project.project_token
      );

      setLoading(false);
      if (onProjectUpdate) {
        onProjectUpdate(approvedProject);
      }

      // Navigation: A approved -> step2, B approved -> step3
      navigate(isInterfaceB ? '/step3' : '/step2');
    } catch (err: unknown) {
      setLoading(false);
      setError(err instanceof Error ? err.message : 'Failed to approve interface');
    }
  };

  const getProvenanceBadge = (provenance: DimensionProvenance) => {
    switch (provenance) {
      case 'user_entered':
        return { text: 'User Entered', icon: '👤', className: 'badge-user' };
      case 'image_extracted':
        return { text: 'Image Extracted', icon: '📷', className: 'badge-extracted' };
      case 'system_inferred':
        return { text: 'System Inferred', icon: '⚙️', className: 'badge-inferred' };
      case 'unresolved':
      default:
        return { text: 'Unresolved', icon: '❓', className: 'badge-unresolved' };
    }
  };

  return (
    <div className="profile-review-page container">
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">{interfaceName} — Profile Review & Approval</h1>
        <p className="page-subtitle">
          Review extracted SVG profile, edit parameters, and confirm approval.
        </p>
        {targetInterface?.approved && !isEditing && (
          <div
            className="status-banner approved"
            style={{
              padding: '0.75rem 1rem',
              background: '#0d381e',
              border: '1px solid #238636',
              borderRadius: '6px',
              color: '#3fb950',
              marginTop: '0.5rem',
            }}
          >
            <strong>✓ Status: Approved</strong> — Interface is approved and ready.
          </div>
        )}
      </header>

      {error && (
        <div className="error-banner" role="alert" style={{ marginBottom: '1rem' }}>
          <p>{error}</p>
        </div>
      )}

      {/* Side-by-Side Review Section */}
      <div
        className="side-by-side-review"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Left Column: Source Image */}
        <div
          className="review-card source-image-card"
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <h2>Source Image</h2>
          <div
            className="image-container"
            style={{
              textAlign: 'center',
              minHeight: '220px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#0d1117',
              borderRadius: '6px',
              border: '1px solid #21262d',
              padding: '0.5rem',
            }}
          >
            {targetInterface?.source_image_ref ? (
              <img
                src={`${import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'}/${targetInterface.source_image_ref}`}
                alt={`Source file for ${interfaceName}`}
                style={{ maxHeight: '200px', maxWidth: '100%', objectFit: 'contain' }}
              />
            ) : (
              <p style={{ color: '#8b949e' }}>No source image artifact available</p>
            )}
          </div>
          <div style={{ marginTop: '1rem', textAlign: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(isInterfaceB ? '/step2' : '/step1')}
            >
              Upload Better Image
            </button>
          </div>
        </div>

        {/* Right Column: SVG Vector Profile */}
        <div
          className="review-card svg-preview-card"
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <h2>Clean SVG Profile</h2>
          <SvgProfileViewer
            profileType={profileType}
            dimensions={dimensions}
            points={targetInterface?.profile_points}
          />
        </div>
      </div>

      {/* Profile Selector & Controls */}
      <section
        className="profile-controls-card"
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <div
          className="form-group"
          style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}
        >
          <label htmlFor="profile-type-select" style={{ fontWeight: 'bold' }}>
            Detected Profile Type:
          </label>
          <select
            id="profile-type-select"
            className="form-control"
            value={profileType}
            disabled={targetInterface?.approved && !isEditing}
            onChange={(e) => handleProfileTypeChange(e.target.value as ProfileType)}
            style={{
              padding: '0.5rem',
              background: '#0d1117',
              color: '#c9d1d9',
              border: '1px solid #30363d',
              borderRadius: '6px',
            }}
          >
            <option value="circle">Circle</option>
            <option value="rectangle">Rectangle</option>
            <option value="rounded_rectangle">Rounded Rectangle</option>
          </select>
        </div>
      </section>

      {/* Dimension Editing Table */}
      <section
        className="dimensions-editor-card"
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <header
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1rem',
          }}
        >
          <h2>Interface Dimensions</h2>
          {(!targetInterface?.approved || isEditing) && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleAddDimension}
            >
              + Add Dimension Parameter
            </button>
          )}
        </header>

        {dimensions.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table
              className="dimensions-table"
              style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e' }}>
                  <th style={{ padding: '0.5rem' }}>Parameter</th>
                  <th style={{ padding: '0.5rem' }}>Value</th>
                  <th style={{ padding: '0.5rem' }}>Unit</th>
                  <th style={{ padding: '0.5rem' }}>Provenance</th>
                  <th style={{ padding: '0.5rem' }}>Confidence</th>
                  <th style={{ padding: '0.5rem' }}>Critical</th>
                  {(!targetInterface?.approved || isEditing) && (
                    <th style={{ padding: '0.5rem' }}>Action</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {dimensions.map((dim, idx) => {
                  const badge = getProvenanceBadge(dim.provenance);
                  return (
                    <tr
                      key={dim.id || idx}
                      style={{ borderBottom: '1px solid #21262d' }}
                    >
                      <td style={{ padding: '0.5rem' }}>
                        <strong>{dim.label}</strong>
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <input
                          type="number"
                          step="0.1"
                          aria-label={`Value for ${dim.label}`}
                          value={dim.value}
                          disabled={targetInterface?.approved && !isEditing}
                          onChange={(e) =>
                            handleDimensionValueChange(idx, e.target.value)
                          }
                          style={{
                            width: '90px',
                            padding: '0.25rem 0.5rem',
                            background: '#0d1117',
                            color: '#c9d1d9',
                            border: '1px solid #30363d',
                            borderRadius: '4px',
                          }}
                        />
                      </td>
                      <td style={{ padding: '0.5rem' }}>{dim.unit}</td>
                      <td style={{ padding: '0.5rem' }}>
                        {(!targetInterface?.approved || isEditing) ? (
                          <select
                            aria-label={`Provenance for ${dim.label}`}
                            value={dim.provenance}
                            onChange={(e) =>
                              handleProvenanceChange(
                                idx,
                                e.target.value as DimensionProvenance
                              )
                            }
                            style={{
                              padding: '0.25rem 0.5rem',
                              background: '#0d1117',
                              color: '#c9d1d9',
                              border: '1px solid #30363d',
                              borderRadius: '4px',
                            }}
                          >
                            <option value="user_entered">User Entered</option>
                            <option value="image_extracted">Image Extracted</option>
                            <option value="system_inferred">System Inferred</option>
                            <option value="unresolved">Unresolved</option>
                          </select>
                        ) : (
                          <span className={`provenance-badge ${badge.className}`}>
                            <span aria-hidden="true">{badge.icon}</span>{' '}
                            <span>{badge.text}</span>
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.05"
                          aria-label={`Confidence for ${dim.label}`}
                          value={dim.confidence}
                          disabled={targetInterface?.approved && !isEditing}
                          onChange={(e) =>
                            handleConfidenceChange(idx, e.target.value)
                          }
                          style={{
                            width: '70px',
                            padding: '0.25rem 0.5rem',
                            background: '#0d1117',
                            color: '#c9d1d9',
                            border: '1px solid #30363d',
                            borderRadius: '4px',
                          }}
                        />
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <input
                          type="checkbox"
                          aria-label={`Critical flag for ${dim.label}`}
                          checked={dim.critical}
                          disabled={targetInterface?.approved && !isEditing}
                          onChange={(e) =>
                            handleCriticalToggle(idx, e.target.checked)
                          }
                        />
                      </td>
                      {(!targetInterface?.approved || isEditing) && (
                        <td style={{ padding: '0.5rem' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            style={{ color: '#f85149' }}
                            onClick={() => handleRemoveDimension(idx)}
                          >
                            Remove
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-notice">No dimension parameters defined.</p>
        )}

        {/* Accessibility Provenance Legend */}
        <div
          className="provenance-legend"
          style={{
            marginTop: '1rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid #21262d',
            fontSize: '0.85rem',
            color: '#8b949e',
            display: 'flex',
            gap: '1.5rem',
            flexWrap: 'wrap',
          }}
        >
          <span>
            <strong>Legend:</strong>
          </span>
          <span>👤 User Entered</span>
          <span>📷 Image Extracted</span>
          <span>⚙️ System Inferred</span>
          <span>❓ Unresolved</span>
        </div>
      </section>

      {/* Validation Summary Panel */}
      <section
        className="validation-summary-card"
        style={{
          background: '#161b22',
          border: `1px solid ${isFormValid ? '#238636' : '#da3633'}`,
          borderRadius: '8px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          Validation Summary
          <span
            className={`badge ${isFormValid ? 'badge-success' : 'badge-error'}`}
            style={{
              padding: '0.2rem 0.6rem',
              borderRadius: '12px',
              fontSize: '0.8rem',
              background: isFormValid ? '#238636' : '#da3633',
              color: '#ffffff',
            }}
          >
            {isFormValid ? 'Valid' : 'Validation Error'}
          </span>
        </h2>

        {validationErrors.length > 0 ? (
          <ul
            className="validation-errors-list"
            style={{ color: '#f85149', marginTop: '0.5rem', paddingLeft: '1.2rem' }}
          >
            {validationErrors.map((err, idx) => (
              <li key={idx}>⚠️ {err}</li>
            ))}
          </ul>
        ) : (
          <p style={{ color: '#3fb950', marginTop: '0.5rem' }}>
            ✓ All structural validation rules passed. Profile is ready for approval.
          </p>
        )}
      </section>

      {/* Footer Action Buttons */}
      <footer
        className="review-actions"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate(isInterfaceB ? '/step2' : '/step1')}
        >
          Re-upload Image
        </button>

        <div style={{ display: 'flex', gap: '1rem' }}>
          {targetInterface?.approved && !isEditing ? (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsEditing(true)}
              >
                Edit Profile Again
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate(isInterfaceB ? '/step3' : '/step2')}
              >
                {isInterfaceB ? 'Continue to Connection' : 'Continue to Interface B'}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={loading}
                onClick={handleUpdateProfile}
              >
                Update Profile
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={loading || !isFormValid}
                onClick={handleApprove}
              >
                {loading ? 'Approving...' : `Approve ${interfaceName}`}
              </button>
            </>
          )}
        </div>
      </footer>
    </div>
  );
};

export default ProfileReviewPage;
