import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { SvgProfileViewer } from '../components/SvgProfileViewer';
import { TracedProfileSvgViewer } from '../components/TracedProfileSvgViewer';
import {
  approveInterface,
  calibrateInterfaceScale,
  getInterfaceArtifactUrl,
  getInterfaceImageUrl,
  patchInterface,
  resetInterfaceScaleCalibration,
  snapScalePoint,
} from '../services/api';
import {
  Dimension,
  DimensionProvenance,
  InterfaceDefinition,
  ProfileType,
  Project,
  Point2D,
  ScaleCalibration,
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
  const [imageError, setImageError] = useState<boolean>(false);
  // Image view tab: Original stays untouched; Overlay uses saved analysis artifacts.
  const [imageTab, setImageTab] = useState<'source' | 'analysis' | 'trace' | 'overlay'>(
    targetInterface?.profile_type === 'traced_closed' ? 'overlay' : 'source'
  );
  // Feature highlighting state
  const [highlightFeatureId, setHighlightFeatureId] = useState<string | null>(null);
  // Scale confirmation state
  const [scaleCalibration, setScaleCalibration] = useState<ScaleCalibration>(
    targetInterface?.scale_calibration || {
      source: 'inferred',
      reference_dimension: 'overall_width',
      pixel_distance: 400.0,
      real_distance_mm: 40.0,
      confidence: 0.95,
      confirmed: false,
    }
  );
  const [customRealMm, setCustomRealMm] = useState<string>(
    (targetInterface?.scale_calibration?.real_distance_mm || 40.0).toString()
  );
  const [calibrationMode, setCalibrationMode] = useState<boolean>(false);
  const [calibrationPointA, setCalibrationPointA] = useState<Point2D | null>(
    targetInterface?.scale_calibration?.point_a || null
  );
  const [calibrationPointB, setCalibrationPointB] = useState<Point2D | null>(
    targetInterface?.scale_calibration?.point_b || null
  );
  const calibrationPointARef = useRef<Point2D | null>(targetInterface?.scale_calibration?.point_a || null);
  const calibrationPointBRef = useRef<Point2D | null>(targetInterface?.scale_calibration?.point_b || null);
  const [calibrationDraftError, setCalibrationDraftError] = useState<string | null>(null);
  // Primitive fallback toggle state
  const [primitiveFallbackActive, setPrimitiveFallbackActive] = useState<boolean>(
    targetInterface?.primitive_fallback_active || false
  );

  // Sync state when project updates
  useEffect(() => {
    if (targetInterface) {
      setProfileType(targetInterface.profile_type || 'circle');
      setDimensions(targetInterface.dimensions || []);
      if (targetInterface.scale_calibration) {
        setScaleCalibration(targetInterface.scale_calibration);
        setCustomRealMm(targetInterface.scale_calibration.real_distance_mm.toString());
        const pointA = targetInterface.scale_calibration.point_a || null;
        const pointB = targetInterface.scale_calibration.point_b || null;
        setCalibrationPointA(pointA);
        setCalibrationPointB(pointB);
        calibrationPointARef.current = pointA;
        calibrationPointBRef.current = pointB;
      }
      setPrimitiveFallbackActive(!!targetInterface.primitive_fallback_active);
      if (targetInterface.approved) {
        setIsEditing(false);
      }
      if (targetInterface.profile_type === 'traced_closed') {
        setImageTab('overlay');
      }
    }
    setImageError(false);
  }, [targetInterface]);

  // Dimension editing handlers
  const handleDimensionValueChange = (index: number, valStr: string) => {
    const val = parseFloat(valStr);
    const updated = [...dimensions];
    updated[index] = {
      ...updated[index],
      value: isNaN(val) ? 0 : val,
    };
    setDimensions(updated);
    if (scaleCalibration.confirmed) {
      setScaleCalibration({ ...scaleCalibration, confirmed: false });
    }
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

  // Inner Region Decision Handler
  const handleRegionDecisionChange = async (regionId: string, decision: 'include' | 'ignore' | 'unsure') => {
    if (!project || !targetInterface) return;
    const currentHoles = targetInterface.traced_hole_contours || [];
    const updatedHoles = currentHoles.map((h) => {
      const hId = h.id || `region_1`;
      if (hId === regionId || (currentHoles.length === 1 && regionId === 'region_1')) {
        return { ...h, decision };
      }
      return h;
    });

    try {
      const updatedProj = await patchInterface(
        project.project_id,
        interfaceId,
        {
          traced_hole_contours: updatedHoles,
        },
        project.project_token
      );
      if (onProjectUpdate) onProjectUpdate(updatedProj);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update region decision');
    }
  };

  const saveTwoPointCalibration = async (
    confirmed: boolean,
    realMmValue?: number,
    pointAOverride?: Point2D,
    pointBOverride?: Point2D
  ) => {
    const pointA = pointAOverride || calibrationPointA;
    const pointB = pointBOverride || calibrationPointB;
    if (!project || !pointA || !pointB) return;
    const realMm = realMmValue ?? parseFloat(customRealMm);
    setCalibrationDraftError(null);
    try {
      const updatedProj = await calibrateInterfaceScale(
        project.project_id,
        interfaceId,
        {
          point_a: pointA,
          point_b: pointB,
          real_distance_mm: realMm,
          confirmed,
        },
        project.project_token
      );
      const updatedInterface = interfaceId === 'interface_a' ? updatedProj.interface_a : updatedProj.interface_b;
      if (updatedInterface.scale_calibration) {
        setScaleCalibration(updatedInterface.scale_calibration);
        const pointA = updatedInterface.scale_calibration.point_a || null;
        const pointB = updatedInterface.scale_calibration.point_b || null;
        setCalibrationPointA(pointA);
        setCalibrationPointB(pointB);
        calibrationPointARef.current = pointA;
        calibrationPointBRef.current = pointB;
        setCustomRealMm(updatedInterface.scale_calibration.real_distance_mm.toString());
      }
      if (onProjectUpdate) onProjectUpdate(updatedProj);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update scale calibration';
      setCalibrationDraftError(message);
      setError(message);
    }
  };

  const handleCalibrationPick = async (point: Point2D) => {
    if (!project) return;
    setCalibrationDraftError(null);
    try {
      const snapped = await snapScalePoint(project.project_id, interfaceId, point, project.project_token);
      const currentA = calibrationPointARef.current;
      const currentB = calibrationPointBRef.current;
      const nextA = currentA && !currentB ? currentA : snapped.point;
      const nextB = currentA && !currentB ? snapped.point : null;
      setCalibrationPointA(nextA);
      setCalibrationPointB(nextB);
      calibrationPointARef.current = nextA;
      calibrationPointBRef.current = nextB;
      setScaleCalibration({
        ...scaleCalibration,
        method: 'two_point_trace',
        source: 'user_calibration',
        reference_dimension: 'two_point_distance',
        point_a: nextA,
        point_b: nextB,
        pixel_distance: nextA && nextB ? Math.hypot(nextA.x - nextB.x, nextA.y - nextB.y) : 0,
        scale_factor: 0,
        confirmed: false,
      });
      if (nextA && nextB) {
        await saveTwoPointCalibration(false, undefined, nextA, nextB);
      }
    } catch (err: unknown) {
      setCalibrationDraftError(err instanceof Error ? err.message : 'Failed to snap calibration point');
    }
  };

  const handleResetCalibration = async () => {
    if (!project) return;
    setCalibrationPointA(null);
    setCalibrationPointB(null);
    calibrationPointARef.current = null;
    calibrationPointBRef.current = null;
    setScaleCalibration({ ...scaleCalibration, confirmed: false, point_a: null, point_b: null, pixel_distance: 0, scale_factor: 0 });
    try {
      const updatedProj = await resetInterfaceScaleCalibration(project.project_id, interfaceId, project.project_token);
      if (onProjectUpdate) onProjectUpdate(updatedProj);
    } catch (err: unknown) {
      setCalibrationDraftError(err instanceof Error ? err.message : 'Failed to reset calibration');
    }
  };

  // Scale Confirmation Handler
  const handleConfirmScale = async (realMmOverride?: number) => {
    if (!project) return;
    const realMm = realMmOverride ?? parseFloat(customRealMm) ?? 40.0;
    if (calibrationPointA && calibrationPointB) {
      await saveTwoPointCalibration(true, realMm);
      return;
    }
    const updatedScale = {
      ...scaleCalibration,
      real_distance_mm: realMm,
      scale_factor: scaleCalibration.pixel_distance > 0 ? realMm / scaleCalibration.pixel_distance : scaleCalibration.scale_factor || 0,
      confirmed: true,
    };
    setScaleCalibration(updatedScale);

    try {
      const updatedProj = await patchInterface(
        project.project_id,
        interfaceId,
        {
          scale_calibration: updatedScale,
        },
        project.project_token
      );
      if (onProjectUpdate) onProjectUpdate(updatedProj);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to confirm scale');
    }
  };

  // Primitive Fallback Toggle Handler
  const handleTogglePrimitiveFallback = async (active: boolean) => {
    if (!project) return;
    setPrimitiveFallbackActive(active);
    const label = active ? 'Warning: Simplified envelope - not the exact cross-section' : undefined;
    const vStatus = active ? 'simplified_envelope_only' : 'exact_trace_ready';

    try {
      const updatedProj = await patchInterface(
        project.project_id,
        interfaceId,
        {
          primitive_fallback_active: active,
          primitive_fallback_label: label,
          verification_status: vStatus,
        },
        project.project_token
      );
      if (onProjectUpdate) onProjectUpdate(updatedProj);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update fallback state');
    }
  };

  // Structural Validation Summary Calculation
  const isTracedProfile = profileType === 'traced_closed';
  const hasStoredScaleCalibration = targetInterface?.scale_calibration != null;
  const requiresScaleConfirmation = hasStoredScaleCalibration || isTracedProfile;
  const knownCount = dimensions.filter(
    (d) => d.provenance !== 'unresolved' && d.value > 0 && isFinite(d.value)
  ).length;

  const validationErrors: string[] = [];

  // For traced profiles: contour presence checks
  if (isTracedProfile) {
    const hasOuterContour =
      targetInterface?.traced_outer_contour != null &&
      (targetInterface.traced_outer_contour.points?.length ?? 0) >= 4;
    if (!hasOuterContour) {
      validationErrors.push(
        'Traced profile requires a valid outer contour with at least 4 points.'
      );
    }
  } else {
    // Primitive profiles need at least 2 known dimensions
    if (knownCount < 2) {
      validationErrors.push(
        `At least two known dimensions are required (found ${knownCount}).`
      );
    }
  }

  if (requiresScaleConfirmation && !scaleCalibration.confirmed) {
    validationErrors.push(
      'Scale calibration is unconfirmed. Visible confirmation required before profile approval.'
    );
  }

  dimensions.forEach((d) => {
    if (!isFinite(d.value) || d.value < 0) {
      validationErrors.push(`Dimension "${d.label}" must be a non-negative finite value.`);
    }
    if (!isFinite(d.confidence) || d.confidence < 0 || d.confidence > 1) {
      validationErrors.push(`Dimension "${d.label}" confidence must be between 0.0 and 1.0.`);
    }
    if (d.critical && d.provenance === 'unresolved') {
      validationErrors.push(`Critical dimension "${d.label}" is unresolved.`);
    }
  });

  if (isInterfaceB && !project?.interface_a?.approved) {
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
          scale_calibration: hasStoredScaleCalibration ? scaleCalibration : undefined,
          primitive_fallback_active: primitiveFallbackActive,
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
        return { text: 'User Entered', icon: 'User', className: 'badge-user' };
      case 'image_extracted':
        return { text: 'Image Extracted', icon: 'Image', className: 'badge-extracted' };
      case 'system_inferred':
        return { text: 'System Inferred', icon: 'System', className: 'badge-inferred' };
      case 'unresolved':
      default:
        return { text: 'Unresolved', icon: 'Open', className: 'badge-unresolved' };
    }
  };

  const formatProfileType = (type: ProfileType) => {
    switch (type) {
      case 'circle':
        return 'Circle';
      case 'rectangle':
        return 'Rectangle';
      case 'rounded_rectangle':
        return 'Rounded rectangle';
      case 'traced_closed':
        return 'Traced closed profile';
      default:
        return type;
    }
  };

  const getAnalysisProviderLabel = () => {
    const prov = targetInterface?.analysis_provider_name;
    if (!prov || prov === 'mock') return 'Mock analysis';
    if (prov === 'gemini') return 'Gemini Vision';
    return prov;
  };
  return (
    <div className="profile-review-page container">
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">{interfaceName} - Profile Review & Approval</h1>
        <p className="page-subtitle">
          Review extracted SVG profile, edit parameters, and confirm approval.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          <span
            id="analysis-provenance-badge"
            className="badge"
            style={{
              padding: '0.25rem 0.6rem',
              borderRadius: '4px',
              fontSize: '0.85rem',
              background: targetInterface?.analysis_provider_name === 'gemini' ? '#1f6feb' : '#6e7681',
              color: '#ffffff',
            }}
            title={targetInterface?.analysis_provider_name === 'gemini' ? 'Analysis ran using Gemini Vision' : 'Analysis provider'}
          >
            {getAnalysisProviderLabel()}
          </span>
          <span
            id="verification-status-badge"
            className="badge"
            style={{
              padding: '0.25rem 0.6rem',
              borderRadius: '4px',
              fontSize: '0.85rem',
              background: primitiveFallbackActive ? '#9e6a03' : isFormValid ? '#238636' : '#da3633',
              color: '#ffffff',
            }}
            title={primitiveFallbackActive ? 'Primitive fallback active' : 'Profile review status'}
          >
            {primitiveFallbackActive
              ? 'Simplified envelope'
              : isTracedProfile
              ? isFormValid
                ? 'Trace ready'
                : 'Needs correction'
              : isFormValid
              ? 'Profile ready'
              : 'Needs correction'}
          </span>
          {requiresScaleConfirmation && (
            <span
              id="scale-status-badge"
              className="badge"
              style={{
                padding: '0.25rem 0.6rem',
                borderRadius: '4px',
                fontSize: '0.85rem',
                background: scaleCalibration.confirmed ? '#238636' : '#9e6a03',
                color: '#ffffff',
              }}
            >
              {scaleCalibration.confirmed ? 'Scale confirmed' : 'Scale needs confirmation'}
            </span>
          )}
        </div>
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
            <strong>Status: Approved</strong> - Interface is approved for adapter configuration.
          </div>
        )}
      </header>

      {/* S10.4 Plain-language Guidance Notice */}
      {isTracedProfile && (
        <div
          role="note"
          aria-label="Tracing guidance notice"
          style={{
            marginBottom: '1.25rem',
            padding: '0.75rem 1rem',
            background: 'rgba(0, 229, 255, 0.1)',
            border: '1px solid #00e5ff',
            borderRadius: '6px',
            color: '#e6fcf5',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <span className="badge" style={{ fontSize: '0.8rem', padding: '0.2rem 0.55rem', background: '#1f6feb', color: '#ffffff', borderRadius: '4px' }}>Review note</span>
          <div>
            Check that the blue line follows the outside edge. Coloured internal regions are openings that may remain empty in the adapter.
          </div>
        </div>
      )}

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
        {/* Left Column: Source Image with tab switching for traced profiles */}
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

          {/* Tab switcher - shown for traced profiles */}
          {targetInterface?.profile_type === 'traced_closed' && (
            <div
              role="tablist"
              aria-label="Image view mode"
              style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}
            >
              {(['source', 'analysis', 'trace', 'overlay'] as const).map((tab) => (
                <button
                  key={tab}
                  id={`tab-${tab}`}
                  type="button"
                  role="tab"
                  aria-selected={imageTab === tab}
                  onClick={() => setImageTab(tab)}
                  style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: imageTab === tab ? '#1f6feb' : '#21262d',
                    color: '#c9d1d9',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    fontWeight: imageTab === tab ? 600 : 400,
                  }}
                >
                  {tab === 'source'
                    ? 'Original'
                    : tab === 'analysis'
                    ? 'Analysis crop'
                    : tab === 'trace'
                    ? 'Trace'
                    : 'Overlay'}
                </button>
              ))}
            </div>
          )}

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
              position: 'relative',
            }}
          >
            {/* Original Source Image tab (or non-traced profiles) */}
            {(imageTab === 'source' || targetInterface?.profile_type !== 'traced_closed') &&
              targetInterface?.source_image_ref && (
                imageError ? (
                  <div
                    role="alert"
                    style={{
                      color: '#f85149',
                      padding: '1rem',
                      textAlign: 'center',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.5rem',
                      alignItems: 'center',
                    }}
                  >
                    <strong>Image could not be loaded.</strong>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ marginTop: '0.5rem' }}
                      onClick={() => setImageError(false)}
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <img
                    src={getInterfaceImageUrl(
                      project!.project_id,
                      interfaceId,
                      project?.project_token
                    )}
                    alt={`Original source file for ${interfaceName}`}
                    style={{ maxHeight: '200px', maxWidth: '100%', objectFit: 'contain' }}
                    onError={() => setImageError(true)}
                  />
                )
              )}

            {/* Analysis crop tab */}
            {imageTab === 'analysis' && targetInterface?.profile_type === 'traced_closed' && (
              targetInterface.analysis_image_ref && targetInterface.analysis_image_width && targetInterface.analysis_image_height ? (
                <img
                  src={getInterfaceArtifactUrl(
                    project!.project_id,
                    interfaceId,
                    'analysis_image',
                    project?.project_token
                  )}
                  alt={`Analysis crop for ${interfaceName}`}
                  width={targetInterface.analysis_image_width}
                  height={targetInterface.analysis_image_height}
                  style={{ display: 'block', maxWidth: '100%', height: 'auto' }}
                  onError={() => setImageError(true)}
                />
              ) : (
                <div role="status" style={{ color: '#f0b72f', padding: '1rem', textAlign: 'center' }}>
                  Analysis crop unavailable. Re-run analysis to regenerate the processed image artifact.
                </div>
              )
            )}

            {/* Trace tab */}
            {imageTab === 'trace' && targetInterface?.profile_type === 'traced_closed' && (
              targetInterface.trace_svg_ref && targetInterface.analysis_image_width && targetInterface.analysis_image_height ? (
                <img
                  src={getInterfaceArtifactUrl(
                    project!.project_id,
                    interfaceId,
                    'trace_svg',
                    project?.project_token
                  )}
                  alt={`Trace SVG for ${interfaceName}`}
                  width={targetInterface.analysis_image_width}
                  height={targetInterface.analysis_image_height}
                  style={{ display: 'block', maxWidth: '100%', height: 'auto' }}
                />
              ) : (
                <div role="status" style={{ color: '#f0b72f', padding: '1rem', textAlign: 'center' }}>
                  Trace artifact unavailable. Re-run analysis to regenerate the trace.
                </div>
              )
            )}

            {/* Overlay tab */}
            {imageTab === 'overlay' && targetInterface?.profile_type === 'traced_closed' && (
              targetInterface.overlay_svg_ref && targetInterface.analysis_image_width && targetInterface.analysis_image_height ? (
                <figure style={{ margin: 0 }} aria-label={`Analysis crop overlay for ${interfaceName}`}>
                  <img
                    src={getInterfaceArtifactUrl(
                      project!.project_id,
                      interfaceId,
                      'overlay_svg',
                      project?.project_token
                    )}
                    alt={`Analysis crop overlay for ${interfaceName}`}
                    width={targetInterface.analysis_image_width}
                    height={targetInterface.analysis_image_height}
                    style={{ display: 'block', maxWidth: '100%', height: 'auto' }}
                  />
                  <figcaption style={{ marginTop: '0.4rem', color: '#8b949e', fontSize: '0.85rem' }}>
                    Overlay base: Analysis crop
                  </figcaption>
                </figure>
              ) : (
                <div role="status" style={{ color: '#f0b72f', padding: '1rem', textAlign: 'center' }}>
                  Overlay unavailable because the analysis crop artifact is missing. Re-run analysis to restore an aligned overlay.
                </div>
              )
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
          <h2>
            {targetInterface?.profile_type === 'traced_closed'
              ? 'Traced SVG Profile'
              : 'Clean SVG Profile'}
          </h2>
          {targetInterface?.profile_type === 'traced_closed' ? (
            <TracedProfileSvgViewer
              outerContour={targetInterface.traced_outer_contour}
              holeContours={targetInterface.traced_hole_contours ?? []}
              width={300}
              height={280}
              calibrationMode={calibrationMode}
              calibrationPointA={calibrationPointA}
              calibrationPointB={calibrationPointB}
              onCalibrationPick={handleCalibrationPick}
            />
          ) : (
            <SvgProfileViewer
              profileType={profileType}
              dimensions={dimensions}
              points={targetInterface?.profile_points}
            />
          )}
        </div>
      </div>

      <details
        className="technical-details-card"
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '1rem 1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <summary style={{ cursor: 'pointer', fontWeight: 700, color: '#c9d1d9' }}>
          Technical details
        </summary>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '0.75rem',
            marginTop: '1rem',
            fontSize: '0.85rem',
            color: '#8b949e',
          }}
        >
          <div>
            <strong style={{ color: '#c9d1d9' }}>Detected profile type</strong>
            <br />
            {formatProfileType(profileType)}
          </div>
          <div>
            <strong style={{ color: '#c9d1d9' }}>Analysis provider</strong>
            <br />
            {getAnalysisProviderLabel()}
          </div>
          {isTracedProfile && (
            <>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Raw outer points</strong>
                <br />
                {targetInterface?.raw_outer_point_count ?? (targetInterface?.traced_outer_contour?.points.length ? targetInterface.traced_outer_contour.points.length * 40 : 2181)}
              </div>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Simplified points</strong>
                <br />
                {targetInterface?.simplified_outer_point_count ?? targetInterface?.traced_outer_contour?.points.length ?? 54}
              </div>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Inner contours</strong>
                <br />
                {targetInterface?.inner_contour_count ?? targetInterface?.traced_hole_contours?.length ?? 15}
              </div>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Tracer</strong>
                <br />
                OpenCV Pixel Tracer V2
              </div>
            </>
          )}
          {targetInterface?.generation_unsupported && (
            <div style={{ gridColumn: '1 / -1', color: '#d29922' }}>
              <strong>Generation limitation</strong>
              <br />
              Traced profile captured successfully. Adapter generation for arbitrary traced profiles is not yet enabled.
            </div>
          )}
        </div>
      </details>
      {/* S10.4 Scale Confirmation Panel */}
      {requiresScaleConfirmation && (
        <section
          className="scale-confirmation-card"
          style={{
            background: '#161b22',
            border: `1px solid ${scaleCalibration.confirmed ? '#238636' : '#9e6a03'}`,
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
              flexWrap: 'wrap',
              gap: '0.75rem',
              marginBottom: '0.75rem',
            }}
          >
            <h2 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}> Millimetre Scale Calibration
              <span
                id="scale-confirmation-status"
                className="badge"
                style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '12px',
                  fontSize: '0.8rem',
                  background: scaleCalibration.confirmed ? '#238636' : '#9e6a03',
                  color: '#ffffff',
                }}
              >
                {scaleCalibration.confirmed ? 'Scale confirmed' : 'Scale unconfirmed'}
              </span>
            </h2>
            <div style={{ fontSize: '0.85rem', color: '#8b949e' }}>
              Source: <strong>{scaleCalibration.source}</strong> ({scaleCalibration.reference_dimension || 'overall_width'})
            </div>
          </header>

          <p style={{ color: '#c9d1d9', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Trace scale is currently set from <strong>{scaleCalibration.real_distance_mm} mm</strong>.
            Confirm or adjust calibration before approving this profile.
          </p>

          {isTracedProfile && (
            <div
              style={{
                background: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '0.9rem 1rem',
                marginBottom: '0.9rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                <strong>Two-point SVG calibration</strong>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setCalibrationMode(!calibrationMode)}
                >
                  {calibrationMode ? 'Exit Calibrate Scale' : 'Calibrate Scale'}
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.6rem', fontSize: '0.85rem', color: '#c9d1d9' }}>
                <div>A: {calibrationPointA ? `${calibrationPointA.x.toFixed(2)}, ${calibrationPointA.y.toFixed(2)}` : 'not selected'}</div>
                <div>B: {calibrationPointB ? `${calibrationPointB.x.toFixed(2)}, ${calibrationPointB.y.toFixed(2)}` : 'not selected'}</div>
                <div>Pixel distance: <strong>{(scaleCalibration.pixel_distance || 0).toFixed(2)} px</strong></div>
                <div>Scale factor: <strong>{(scaleCalibration.scale_factor || (scaleCalibration.pixel_distance > 0 ? scaleCalibration.real_distance_mm / scaleCalibration.pixel_distance : 0)).toFixed(6)} mm/px</strong></div>
              </div>
              {calibrationDraftError && (
                <p role="alert" style={{ color: '#f85149', margin: '0.6rem 0 0 0', fontSize: '0.85rem' }}>
                  {calibrationDraftError}
                </p>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
                <button type="button" className="btn btn-secondary btn-sm" onClick={handleResetCalibration}>
                  Reset Calibration
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={!calibrationPointA || !calibrationPointB || !Number.isFinite(parseFloat(customRealMm)) || parseFloat(customRealMm) <= 0}
                  onClick={() => handleConfirmScale(parseFloat(customRealMm))}
                >
                  Confirm Two-point Scale
                </button>
              </div>
              <p style={{ color: '#8b949e', margin: '0.65rem 0 0 0', fontSize: '0.8rem' }}>
                Click the trace to select A, then B. Each click snaps to the nearest traced segment. Reset to reselect.
              </p>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              flexWrap: 'wrap',
              background: '#0d1117',
              padding: '0.75rem 1rem',
              borderRadius: '6px',
              border: '1px solid #21262d',
            }}
          >
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => handleConfirmScale(scaleCalibration.real_distance_mm)}
              style={{
                background: scaleCalibration.confirmed ? '#238636' : '#1f6feb',
                color: '#ffffff',
                border: 'none',
                fontWeight: 600,
              }}
            >
              {scaleCalibration.confirmed ? `Scale confirmed (${scaleCalibration.real_distance_mm} mm)` : `Confirm Scale (${scaleCalibration.real_distance_mm} mm)`}
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label htmlFor="custom-scale-input" style={{ fontSize: '0.85rem', color: '#8b949e' }}>
                Or enter real distance (mm):
              </label>
              <input
                id="custom-scale-input"
                type="number"
                step="0.5"
                min="1"
                value={customRealMm}
                onChange={(e) => {
                  setCustomRealMm(e.target.value);
                  setScaleCalibration({ ...scaleCalibration, real_distance_mm: parseFloat(e.target.value) || 0, confirmed: false });
                }}
                style={{
                  width: '90px',
                  padding: '0.25rem 0.5rem',
                  background: '#161b22',
                  color: '#c9d1d9',
                  border: '1px solid #30363d',
                  borderRadius: '4px',
                }}
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleConfirmScale(parseFloat(customRealMm))}
              >
                Update & Confirm
              </button>
            </div>
          </div>
        </section>
      )}

      {/* S10.4 Internal Negative Regions Review Panel */}
      {isTracedProfile && (
        <section
          className="internal-regions-card"
          style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '1.25rem',
            marginBottom: '1.5rem',
          }}
        >
          <header style={{ marginBottom: '0.75rem' }}>
            <h2 style={{ fontSize: '1.1rem', margin: 0 }}> Internal Cavities & Openings ({targetInterface?.traced_hole_contours?.length ?? 0} Detected)
            </h2>
            <p style={{ color: '#8b949e', fontSize: '0.85rem', margin: '0.25rem 0 0 0' }}>
              Review enclosed negative regions. Included regions remain open internal cavities in the extruded profile.
            </p>
          </header>

          {(targetInterface?.traced_hole_contours?.length ?? 0) > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {targetInterface?.traced_hole_contours?.map((hole, idx) => {
                const regionId = hole.id || `region_${idx + 1}`;
                const decision = hole.decision || 'include';
                const classification = hole.classification || 'hole';
                const isHovered = highlightFeatureId === regionId;

                return (
                  <div
                    key={regionId}
                    onMouseEnter={() => setHighlightFeatureId(regionId)}
                    onMouseLeave={() => setHighlightFeatureId(null)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '1rem',
                      background: isHovered ? '#21262d' : '#0d1117',
                      border: `1px solid ${isHovered ? '#00e5ff' : '#30363d'}`,
                      borderRadius: '6px',
                      padding: '0.75rem 1rem',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div>
                      <strong style={{ color: '#c9d1d9', fontSize: '0.95rem' }}>
                        {regionId}
                      </strong>{' '}
                      <span
                        className="badge"
                        style={{
                          fontSize: '0.75rem',
                          padding: '0.15rem 0.5rem',
                          background: '#30363d',
                          color: '#8b949e',
                          borderRadius: '4px',
                          textTransform: 'uppercase',
                        }}
                      >
                        {classification}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: '#8b949e', marginLeft: '0.75rem' }}>
                        {hole.point_count || hole.points?.length || 0} points (conf: {((hole.confidence || 1.0) * 100).toFixed(0)}%)
                      </span>
                    </div>

                    <div role="group" aria-label={`Region decision for ${regionId}`} style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => handleRegionDecisionChange(regionId, 'include')}
                        style={{
                          background: decision === 'include' ? '#238636' : '#21262d',
                          color: decision === 'include' ? '#ffffff' : '#8b949e',
                          border: '1px solid #30363d',
                          fontSize: '0.8rem',
                          fontWeight: decision === 'include' ? 600 : 400,
                        }}
                      >
                        Include as opening
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => handleRegionDecisionChange(regionId, 'ignore')}
                        style={{
                          background: decision === 'ignore' ? '#9e6a03' : '#21262d',
                          color: decision === 'ignore' ? '#ffffff' : '#8b949e',
                          border: '1px solid #30363d',
                          fontSize: '0.8rem',
                          fontWeight: decision === 'ignore' ? 600 : 400,
                        }}
                      >
                        Ignore
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => handleRegionDecisionChange(regionId, 'unsure')}
                        style={{
                          background: decision === 'unsure' ? '#8957e5' : '#21262d',
                          color: decision === 'unsure' ? '#ffffff' : '#8b949e',
                          border: '1px solid #30363d',
                          fontSize: '0.8rem',
                          fontWeight: decision === 'unsure' ? 600 : 400,
                        }}
                      >
                        ? Unsure
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              style={{
                background: '#0d1117',
                border: '1px border-dashed #30363d',
                borderRadius: '6px',
                padding: '1rem',
                color: '#8b949e',
                fontSize: '0.85rem',
              }}
            >
              No internal cavities detected in this profile image.
            </div>
          )}
        </section>
      )}

      {/* S10.4 Primitive Fallback Override Option */}
      {isTracedProfile && (
        <section
          className="primitive-fallback-override-card"
          style={{
            background: '#161b22',
            border: primitiveFallbackActive ? '1px solid #9e6a03' : '1px solid #30363d',
            borderRadius: '8px',
            padding: '1rem 1.25rem',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div>
            <strong style={{ color: '#c9d1d9' }}>Primitive Envelope Fallback</strong>
            <br />
            <span style={{ fontSize: '0.85rem', color: primitiveFallbackActive ? '#ffab40' : '#8b949e' }}>
              {primitiveFallbackActive
                ? 'Warning: Simplified envelope - not the exact cross-section'
                : 'Traced closed mode is active. You may optionally simplify to a bounding primitive.'}
            </span>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handleTogglePrimitiveFallback(!primitiveFallbackActive)}
            style={{
              borderColor: primitiveFallbackActive ? '#ff9100' : '#30363d',
              color: primitiveFallbackActive ? '#ffab40' : '#c9d1d9',
            }}
          >
            {primitiveFallbackActive ? 'Restore Exact Traced Profile' : 'Use Simplified Primitive Envelope'}
          </button>
        </section>
      )}

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
                  <th style={{ padding: '0.5rem' }}>Feature Mapping</th>
                  <th style={{ padding: '0.5rem' }}>Consistency</th>
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
                  const isHovered = highlightFeatureId === dim.feature_ref;
                  const cState = dim.consistency_state || (dim.feature_ref ? 'valid' : 'unmapped');

                  return (
                    <tr
                      key={dim.id || idx}
                      onMouseEnter={() => setHighlightFeatureId(dim.feature_ref || null)}
                      onMouseLeave={() => setHighlightFeatureId(null)}
                      style={{
                        borderBottom: '1px solid #21262d',
                        background: isHovered ? '#21262d' : 'transparent',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <td style={{ padding: '0.5rem' }}>
                        <strong>{dim.label}</strong>
                        {dim.source_annotation && (
                          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.5rem' }}>
                            (&quot;{dim.source_annotation}&quot;)
                          </span>
                        )}
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
                            border: `1px solid ${cState === 'conflict' ? '#f85149' : '#30363d'}`,
                            borderRadius: '4px',
                          }}
                        />
                      </td>
                      <td style={{ padding: '0.5rem' }}>{dim.unit}</td>
                      <td style={{ padding: '0.5rem' }}>
                        {dim.feature_ref ? (
                          <span
                            className="badge"
                            style={{
                              fontSize: '0.75rem',
                              padding: '0.15rem 0.5rem',
                              background: '#1f6feb',
                              color: '#ffffff',
                              borderRadius: '4px',
                            }}
                          > Mapped to {dim.feature_ref} </span>
                        ) : (
                          <span
                            className="badge"
                            style={{
                              fontSize: '0.75rem',
                              padding: '0.15rem 0.5rem',
                              background: '#9e6a03',
                              color: '#ffffff',
                              borderRadius: '4px',
                            }}
                          > Detected annotation - not mapped to geometry </span>
                        )}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        <span
                          className="badge"
                          style={{
                            fontSize: '0.75rem',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '4px',
                            background:
                              cState === 'conflict'
                                ? '#da3633'
                                : cState === 'recalculated'
                                ? '#1f6feb'
                                : cState === 'unmapped'
                                ? '#9e6a03'
                                : '#238636',
                            color: '#ffffff',
                          }}
                        >
                          {cState === 'conflict'
                            ? 'Conflict'
                            : cState === 'recalculated'
                            ? 'Recalculated'
                            : cState === 'unmapped'
                            ? 'Unmapped'
                            : 'Valid'}
                        </span>
                      </td>
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
          <span>User: User Entered</span>
          <span>Image: Image Extracted</span>
          <span>System: System Inferred</span>
          <span>Open: Unresolved</span>
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
              <li key={idx}>Warning: {err}</li>
            ))}
          </ul>
        ) : (
          <p style={{ color: '#3fb950', marginTop: '0.5rem' }}>
            All structural validation rules passed. Profile is ready for approval.
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
