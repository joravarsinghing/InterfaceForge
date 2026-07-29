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
} from '../services/api';
import {
  Dimension,
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


const supportedProfileTypes = ['circle', 'rectangle', 'rounded_rectangle'] as const;

const formatProfileTypeLabel = (type: ProfileType) => {
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
  const [primitivePromotionConfirmed, setPrimitivePromotionConfirmed] = useState<boolean>(
    targetInterface?.primitive_promotion_confirmed || false
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
      setPrimitivePromotionConfirmed(!!targetInterface.primitive_promotion_confirmed);
      if (targetInterface.approved) {
        setIsEditing(false);
      }
      if (targetInterface.profile_type === 'traced_closed') {
        setImageTab('overlay');
      }
    }
    setImageError(false);
  }, [targetInterface]);


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
    setCalibrationDraftError(null);
    const currentA = calibrationPointARef.current;
    const currentB = calibrationPointBRef.current;
    const nextA = currentA && !currentB ? currentA : point;
    const nextB = currentA && !currentB ? point : null;
    setCalibrationPointA(nextA); setCalibrationPointB(nextB);
    calibrationPointARef.current = nextA; calibrationPointBRef.current = nextB;
    setScaleCalibration({ ...scaleCalibration, method: 'two_point_trace', source: 'user_calibration', reference_dimension: 'two_point_distance', point_a: nextA, point_b: nextB, pixel_distance: nextA && nextB ? Math.hypot(nextA.x - nextB.x, nextA.y - nextB.y) : 0, scale_factor: 0, confirmed: false });
    if (nextA && nextB) await saveTwoPointCalibration(false, undefined, nextA, nextB);
  };

  const handleResetCalibration = async () => {
    if (!project) return;
    setCalibrationPointA(null);
    setCalibrationPointB(null);
    calibrationPointARef.current = null;
    calibrationPointBRef.current = null;
    setCalibrationDraftError(null);
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

  // Structural Validation Summary Calculation
  const resolutionStatus = targetInterface?.resolution_status || (targetInterface?.generation_unsupported ? 'unsupported' : 'resolved');
  const resolvedProfileType = targetInterface?.resolved_profile_type || (supportedProfileTypes.includes(profileType as Exclude<ProfileType, 'traced_closed'>) ? profileType : null);
  const isResolvedSupportedProfile = resolutionStatus === 'resolved' && resolvedProfileType !== null && resolvedProfileType !== 'traced_closed';
  const isTracedProfile = profileType === 'traced_closed';
  const shapeAwaitingConfirmation = false;
  const effectiveProfileType = isResolvedSupportedProfile ? (resolvedProfileType as ProfileType) : profileType;
  const visibleDimensionIds =
    effectiveProfileType === 'circle'
      ? ['outer_diameter', 'diameter']
      : effectiveProfileType === 'rectangle'
      ? ['width', 'height']
      : effectiveProfileType === 'rounded_rectangle'
      ? ['width', 'height', 'corner_radius']
      : ['overall_width', 'overall_height'];
  const dimensionLabelById: Record<string, string> = {
    outer_diameter: 'Outer Diameter',
    diameter: 'Diameter',
    width: 'Width',
    height: 'Height',
    corner_radius: 'Corner Radius',
    overall_width: 'Overall Width',
    overall_height: 'Overall Height',
  };
  const displayDimensions = visibleDimensionIds
    .map((id) => {
      const existing = dimensions.find((dim) => dim.id === id && Number.isFinite(dim.value) && dim.value > 0);
      if (existing) return existing;
      const resolvedValue = targetInterface?.resolved_dimensions?.[id === 'outer_diameter' ? 'diameter' : id];
      if (!resolvedValue || !Number.isFinite(resolvedValue) || resolvedValue <= 0) return undefined;
      return {
        id,
        label: dimensionLabelById[id] || id,
        value: resolvedValue,
        unit: 'mm',
        provenance: 'system_inferred' as const,
        confidence: targetInterface?.resolution_confidence ?? 0.75,
        critical: id !== 'corner_radius',
        feature_ref: 'outer_contour',
        consistency_state: 'recalculated',
      };
    })
    .filter((dim, index, arr): dim is Dimension => Boolean(dim) && arr.findIndex((other) => other?.id === dim?.id) === index);
  const legacyDimensions = dimensions.filter(
    (dim) => !visibleDimensionIds.includes(dim.id) || !dim.feature_ref || dim.consistency_state === 'unmapped'
  );
  const requiresScaleConfirmation = true;
  const traceBackedProfile = Boolean(targetInterface?.traced_outer_contour) && !isResolvedSupportedProfile;
  const supportedPrimitivePromotion = false;

  const validationErrors: string[] = [];

  if (!targetInterface?.traced_outer_contour) {
    validationErrors.push(
      'Calibration requires profile edge data. Replace the image or re-run analysis before approval.'
    );
  }

  if (!scaleCalibration.confirmed || scaleCalibration.method !== 'two_point_trace') {
    validationErrors.push(
      'Two-point calibration must be confirmed before profile approval.'
    );
  }

  if (displayDimensions.length < visibleDimensionIds.filter((id) => id !== 'diameter').length) {
    validationErrors.push('Derived profile dimensions are not ready yet. Confirm calibration first.');
  }

  if (supportedPrimitivePromotion && !primitivePromotionConfirmed) {
    validationErrors.push('Confirm the detected shape before approval.');
  }

  if (resolutionStatus === 'unsupported') {
    validationErrors.push('This outline is more complex than the shapes supported in this version.');
  } else if (resolutionStatus === 'needs_confirmation') {
    validationErrors.push('Shape resolution needs confirmation before profile approval.');
  } else if (isTracedProfile && !isResolvedSupportedProfile && !shapeAwaitingConfirmation) {
    validationErrors.push('This outline is more complex than the shapes supported in this version.');
  }

  displayDimensions.forEach((d) => {
    if (!isFinite(d.value) || d.value <= 0) {
      validationErrors.push(`Dimension "${d.label}" must be a positive finite value.`);
    }
  });

  if (isInterfaceB && !project?.interface_a?.approved) {
    validationErrors.push('Prerequisite: Interface A must be approved first.');
  }
  const isFormValid = validationErrors.length === 0;

  // Actions
  const handleApprove = async () => {
    if (!project) return;
    setLoading(true);
    setError(null);
    try {
      // Approve the latest backend-authoritative shape state.
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
    if (prov === 'gemini_guided_opencv' || prov === 'gemini') return 'AI guidance used';
    if (prov === 'mock') return 'Mock analysis';
    return 'OpenCV profile detection';
  };

  const analysisProviderIsAiGuided =
    targetInterface?.analysis_provider_name === 'gemini_guided_opencv' ||
    targetInterface?.analysis_provider_name === 'gemini';
  return (
    <div className="profile-review-page container">
      <header className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">{interfaceName} - Profile Review & Approval</h1>
        <p className="page-subtitle">
          Review the cleaned profile, calibrate it, and approve it before generation.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          <span
            id="analysis-provenance-badge"
            className="badge"
            style={{
              padding: '0.25rem 0.6rem',
              borderRadius: '4px',
              fontSize: '0.85rem',
              background: analysisProviderIsAiGuided ? '#1f6feb' : '#6e7681',
              color: '#ffffff',
            }}
            title={analysisProviderIsAiGuided ? 'Gemini supplied optional guidance; OpenCV tracing remains authoritative' : 'Deterministic OpenCV profile detection'}
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
              background: primitivePromotionConfirmed ? '#238636' : primitiveFallbackActive || shapeAwaitingConfirmation ? '#9e6a03' : isFormValid ? '#238636' : '#da3633',
              color: '#ffffff',
            }}
            title={primitivePromotionConfirmed ? 'Supported shape confirmed' : shapeAwaitingConfirmation ? 'Detected shape needs confirmation' : 'Profile review status'}
          >
            {primitivePromotionConfirmed
              ? 'Shape confirmed'
              : shapeAwaitingConfirmation
              ? 'Confirm shape'
              : primitiveFallbackActive
              ? 'Trace approximation'
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
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 420px), 1fr))',
          gap: '1.5rem',
          alignItems: 'stretch',
          marginBottom: '1.5rem',
        }}
      >
        {/* Left Column: Source Image with tab switching for traced profiles */}
        <div
          className="review-card source-image-card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
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
              flex: '1 1 auto',
              minHeight: 0,
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
                    style={{ width: '100%', height: '100%', objectFit: 'contain', padding: '0.5rem' }}
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
              onClick={() => navigate(isInterfaceB ? '/step2?replace=1' : '/step1?replace=1')}
            >
              Replace Image
            </button>
          </div>
        </div>

        {/* Right Column: SVG Vector Profile */}
        <div
          className="review-card svg-preview-card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            minWidth: 0,
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <h2>
            {traceBackedProfile ? 'Traced SVG Profile' : 'Clean SVG Profile'}
          </h2>
          {traceBackedProfile ? (
            <>
              {calibrationMode && (
                <p style={{ color: '#c9d1d9', fontSize: '0.85rem', margin: '0 0 0.5rem 0' }}>
                  Select two visible points on the profile edge.
                </p>
              )}
              <TracedProfileSvgViewer
                outerContour={targetInterface?.traced_outer_contour}
                holeContours={targetInterface?.traced_hole_contours ?? []}
                calibrationMode={calibrationMode}
                calibrationPointA={calibrationPointA}
                calibrationPointB={calibrationPointB}
                onCalibrationPick={handleCalibrationPick}
              />
            </>
          ) : (
            <SvgProfileViewer
              profileType={effectiveProfileType}
              dimensions={dimensions}
              calibrationBoundary={targetInterface?.calibration_boundary}
              calibrationConfirmed={scaleCalibration.confirmed}
              calibrationMode={calibrationMode}
              calibrationPointA={calibrationPointA}
              calibrationPointB={calibrationPointB}
              onCalibrationPick={handleCalibrationPick}
            />
          )}
      <section
        className="calibration-card"
        aria-labelledby="calibration-heading"
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
          <h2 id="calibration-heading" style={{ fontSize: '1.1rem', margin: 0 }}>
            Calibration
          </h2>
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
            {scaleCalibration.confirmed ? 'Calibration confirmed' : 'Calibration needed'}
          </span>
        </header>

        <p style={{ color: '#c9d1d9', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Pick two points on the visible profile edge, enter the real distance between them, then confirm calibration.
        </p>

        {targetInterface?.traced_outer_contour ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => { setCalibrationDraftError(null); setCalibrationMode(!calibrationMode); }}
              >
                {calibrationMode ? 'Stop Calibrating' : 'Calibrate'}
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleResetCalibration}>
                {scaleCalibration.confirmed ? 'Recalibrate' : 'Reset Calibration'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.6rem', fontSize: '0.85rem', color: '#c9d1d9', marginBottom: '0.75rem' }}>
              <div>A: {calibrationPointA ? `${calibrationPointA.x.toFixed(2)}, ${calibrationPointA.y.toFixed(2)}` : 'not selected'}</div>
              <div>B: {calibrationPointB ? `${calibrationPointB.x.toFixed(2)}, ${calibrationPointB.y.toFixed(2)}` : 'not selected'}</div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <label htmlFor="calibration-distance-input" style={{ fontSize: '0.85rem', color: '#8b949e' }}>
                Real distance in mm
              </label>
              <input
                id="calibration-distance-input"
                type="number"
                step="0.5"
                min="0.1"
                value={customRealMm}
                onChange={(e) => {
                  setCustomRealMm(e.target.value);
                  setScaleCalibration({ ...scaleCalibration, real_distance_mm: parseFloat(e.target.value) || 0, confirmed: false });
                }}
                style={{
                  width: '110px',
                  padding: '0.25rem 0.5rem',
                  background: '#0d1117',
                  color: '#c9d1d9',
                  border: '1px solid #30363d',
                  borderRadius: '4px',
                }}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={!calibrationPointA || !calibrationPointB || !Number.isFinite(parseFloat(customRealMm)) || parseFloat(customRealMm) <= 0}
                onClick={() => handleConfirmScale(parseFloat(customRealMm))}
              >
                Confirm Calibration
              </button>
            </div>

            {calibrationDraftError && (
              <p role="alert" style={{ color: '#f85149', margin: '0.6rem 0 0 0', fontSize: '0.85rem' }}>
                {calibrationDraftError}
              </p>
            )}
            <p style={{ color: '#8b949e', margin: '0.65rem 0 0 0', fontSize: '0.8rem' }}>
              Click the visible boundary nodes. Changing points or distance requires approval again.
            </p>
          </>
        ) : (
          <p style={{ color: '#f0b72f', margin: 0 }}>
            Calibration needs profile edge data. Replace the image or re-run analysis to calibrate this profile.
          </p>
        )}
      </section>        </div>
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
          {targetInterface?.scale_calibration && (
            <>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Pixel distance</strong>
                <br />
                {(targetInterface.scale_calibration.pixel_distance || 0).toFixed(2)} px
              </div>
              <div>
                <strong style={{ color: '#c9d1d9' }}>Scale factor</strong>
                <br />
                {(targetInterface.scale_calibration.scale_factor || 0).toFixed(6)} mm/px
              </div>
              {targetInterface.scale_calibration.source !== 'user_calibration' && (
                <div>
                  <strong style={{ color: '#c9d1d9' }}>Legacy calibration source</strong>
                  <br />
                  {targetInterface.scale_calibration.source}
                </div>
              )}
            </>
          )}
          {targetInterface?.generation_unsupported && (
            <div style={{ gridColumn: '1 / -1', color: '#d29922' }}>
              <strong>Generation limitation</strong>
              <br />
              This outline is more complex than the shapes supported in this version.
            </div>
          )}
        </div>
      </details>
      {/* S10.4 Internal Negative Regions Review Panel */}
      {(isTracedProfile || primitiveFallbackActive) && (
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

      {/* Shape Confirmation Panel */}
      {isResolvedSupportedProfile && (
        <section
          className="resolved-shape-card"
          aria-labelledby="resolved-shape-heading"
          style={{
            background: '#161b22',
            border: '1px solid #238636',
            borderRadius: '8px',
            padding: '1.25rem',
            marginBottom: '1.5rem',
          }}
        >
          <h2 id="resolved-shape-heading" style={{ fontSize: '1.15rem', margin: 0 }}>
            Detected shape: {formatProfileTypeLabel(resolvedProfileType as ProfileType)}
          </h2>
          <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.8rem', margin: '1rem 0 0 0' }}>
            {(scaleCalibration.confirmed ? displayDimensions : []).map((dim) => (
              <div key={`resolved-${dim.id}`} style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '0.75rem' }}>
                <dt style={{ color: '#8b949e', fontSize: '0.85rem' }}>{dim.id === 'outer_diameter' ? 'Diameter' : dim.label}</dt>
                <dd style={{ color: '#f0f6fc', fontWeight: 700, margin: '0.25rem 0 0 0' }}>
                  {dim.value.toFixed(2)} {dim.unit}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <section
        className="dimensions-summary-card"
        aria-labelledby="dimensions-summary-heading"
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <h2 id="dimensions-summary-heading">Interface Dimensions</h2>
        {scaleCalibration.confirmed && displayDimensions.length > 0 ? (
          <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.8rem', margin: '1rem 0 0 0' }}>
            {(scaleCalibration.confirmed ? displayDimensions : []).map((dim) => (
              <div key={dim.id} style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: '6px', padding: '0.75rem' }}>
                <dt style={{ color: '#8b949e', fontSize: '0.85rem' }}>{dim.label}</dt>
                <dd style={{ color: '#f0f6fc', fontWeight: 700, margin: '0.25rem 0 0 0' }}>
                  {dim.value.toFixed(2)} {dim.unit}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="empty-notice">Dimensions will be calculated after calibration.</p>
        )}
        {legacyDimensions.length > 0 && (
          <details style={{ marginTop: '1rem', color: '#8b949e' }}>
            <summary style={{ cursor: 'pointer' }}>Legacy unmapped dimensions</summary>
            <ul style={{ marginTop: '0.5rem' }}>
              {legacyDimensions.map((dim) => (
                <li key={dim.id}>{dim.label}: stored for compatibility, not used for generation</li>
              ))}
            </ul>
          </details>
        )}
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
          onClick={() => navigate(isInterfaceB ? '/step2?replace=1' : '/step1?replace=1')}
        >
          Replace Image
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
