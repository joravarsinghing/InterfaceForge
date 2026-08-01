"""Canonical design schema and versioned models per ADR-001 and ADR-005."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def current_iso_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class WorkflowState(str, Enum):
    """Validated workflow state enumeration per S3 specification."""

    NEW = "new"
    INTERFACE_A_UPLOADED = "interface_a_uploaded"
    INTERFACE_A_REVIEW_REQUIRED = "interface_a_review_required"
    INTERFACE_A_APPROVED = "interface_a_approved"
    INTERFACE_B_UPLOADED = "interface_b_uploaded"
    INTERFACE_B_REVIEW_REQUIRED = "interface_b_review_required"
    INTERFACES_APPROVED = "interfaces_approved"
    CONNECTION_CONFIGURED = "connection_configured"
    GENERATION_IN_PROGRESS = "generation_in_progress"
    GENERATION_FAILED = "generation_failed"
    MODEL_CURRENT = "model_current"
    MODEL_STALE = "model_stale"
    REVISION_DRAFT = "revision_draft"
    EXPORT_IN_PROGRESS = "export_in_progress"
    EXPORT_READY = "export_ready"


class ProfileType(str, Enum):
    """Supported interface profile geometries per ADR-012."""

    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    TRACED_CLOSED = "traced_closed"
    CUSTOM_CLOSED = "custom_closed"


class ShapeResolutionStatus(str, Enum):
    """Authoritative contour-to-generation shape resolution state."""

    RESOLVED = "resolved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNSUPPORTED = "unsupported"


class DimensionProvenance(str, Enum):
    """Provenance tracking for dimension values."""

    USER_ENTERED = "user_entered"
    IMAGE_EXTRACTED = "image_extracted"
    SYSTEM_INFERRED = "system_inferred"
    UNRESOLVED = "unresolved"


class ConnectionMode(str, Enum):
    """Supported connection relationship modes per ADR-012."""

    COAXIAL = "coaxial"
    OFFSET = "offset"
    ANGLED = "angled"


class ManufacturingProcess(str, Enum):
    """Supported manufacturing processes."""

    FDM = "fdm"
    SLA = "sla"
    CNC = "cnc"


class ModelRevisionStatus(str, Enum):
    """Status lifecycle for model revisions."""

    DRAFT = "draft"
    GENERATING = "generating"
    CURRENT = "current"
    STALE = "stale"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ProviderMode(str, Enum):
    """Project-scoped provider mode for offline mock or live backend providers."""

    MOCK = "mock"
    LIVE = "live"


class FitMode(str, Enum):
    """Per-interface fit intent for interpreting the uploaded boundary."""

    FIT_OVER = "fit_over"
    FIT_INSIDE = "fit_inside"


class Point2D(BaseModel):
    """2D coordinate representation."""

    x: float = 0.0
    y: float = 0.0


class ScaleCalibration(BaseModel):
    """Scale calibration metadata mapping pixel dimensions to real mm units."""

    source: str = "inferred"  # 'drawing_dimension', 'user_calibration', 'inferred'
    method: str = "known_measurement"  # 'known_measurement', 'two_point_trace'
    reference_dimension: Optional[str] = "overall_width"
    point_a: Optional[Point2D] = None
    point_b: Optional[Point2D] = None
    pixel_distance: float = 0.0
    real_distance_mm: float = 40.0
    scale_factor: float = 0.0
    confidence: float = 1.0
    confirmed: bool = False


class Dimension(BaseModel):
    """Dimension parameter definition with provenance metadata."""

    id: str
    label: str
    value: float
    unit: str = "mm"
    provenance: DimensionProvenance = DimensionProvenance.USER_ENTERED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    critical: bool = True
    feature_ref: Optional[str] = None  # e.g. 'outer_contour', 'region_1', 'bore'
    source_annotation: Optional[str] = None  # e.g. '40', 'diameter16', 'R5'
    consistency_state: str = "valid"  # 'valid', 'conflict', 'unmapped', 'recalculated'


class ProfileValidation(BaseModel):
    """Geometry closure and self-intersection validation state."""

    is_closed: bool = True
    self_intersects: bool = False
    warnings: List[str] = Field(default_factory=list)


def default_circle_dimensions() -> List[Dimension]:
    """Default fallback dimensions for initial interface creation."""
    return [
        Dimension(
            id="outer_diameter",
            label="Outer Diameter",
            value=50.0,
            unit="mm",
            provenance=DimensionProvenance.SYSTEM_INFERRED,
            confidence=1.0,
            critical=True,
            feature_ref="outer_contour",
            source_annotation="50",
        ),
        Dimension(
            id="wall_thickness",
            label="Wall Thickness",
            value=5.0,
            unit="mm",
            provenance=DimensionProvenance.SYSTEM_INFERRED,
            confidence=1.0,
            critical=False,
            feature_ref="wall",
            source_annotation="5",
        ),
    ]


class TracedContour(BaseModel):
    """Ordered closed contour for traced_closed profile type."""

    id: str = "outer_contour"
    points: List[Point2D] = Field(default_factory=list)
    is_closed: bool = True
    classification: str = "hole"  # 'hole', 'cavity', 'slot', 'outer_contour', 'unknown'
    decision: str = "include"  # 'include', 'ignore', 'unsure'
    provenance: str = "analysis"  # 'analysis', 'user_edited'
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    point_count: int = 0

    def model_post_init(self, __context: object) -> None:
        self.point_count = len(self.points)

class LoftSection(BaseModel):
    """One authoritative, closed section consumed by preview, mock mesh, and KCL."""

    z_mm: float
    outer: List[Point2D]
    inner: List[Point2D]


class LoftPlan(BaseModel):
    """Persisted correspondence and section plan for an arbitrary-profile loft."""

    schema_revision: str = "loft-plan-v1"
    geometry_hash: str
    point_count: int
    winding: str = "ccw"
    seam_index: int = 0
    outer_a: List[Point2D]
    outer_b: List[Point2D]
    inner_a: List[Point2D]
    inner_b: List[Point2D]
    target_a: List[Point2D] = Field(default_factory=list)
    target_b: List[Point2D] = Field(default_factory=list)
    mating_a: List[Point2D] = Field(default_factory=list)
    mating_b: List[Point2D] = Field(default_factory=list)
    fit_mode_a: FitMode = FitMode.FIT_OVER
    fit_mode_b: FitMode = FitMode.FIT_OVER
    clearance_a_mm: float = 0.0
    clearance_b_mm: float = 0.0
    wall_thickness_mm: float = 2.0
    outer_shift: int = 0
    outer_reversed: bool = False
    inner_shift: int = 0
    inner_reversed: bool = False
    sections: List[LoftSection]


class CalibrationBoundary(BaseModel):
    """Backend-owned boundary shared by rendering, snapping, and calibration."""

    coordinate_space: str = "canonical_profile_v1"
    points: List[Point2D] = Field(default_factory=list)
    is_closed: bool = True
    fitted_width: Optional[float] = None
    fitted_height: Optional[float] = None
    fitted_diameter: Optional[float] = None
    fitted_corner_radius: Optional[float] = None

class Interface(BaseModel):
    """Canonical representation of an adapter interface definition."""

    id: str  # 'interface_a' or 'interface_b'
    source_image_ref: Optional[str] = None
    profile_type: ProfileType = ProfileType.CIRCLE
    trace_profile_type: Optional[ProfileType] = None
    resolved_profile_type: Optional[ProfileType] = None
    resolution_status: ShapeResolutionStatus = ShapeResolutionStatus.RESOLVED
    resolution_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    resolution_reason: Optional[str] = None
    resolved_dimensions: dict[str, float] = Field(default_factory=dict)
    resolution_repaired_at: Optional[str] = None
    resolution_repair_reason: Optional[str] = None
    profile_points: List[Point2D] = Field(default_factory=list)
    center: Point2D = Field(default_factory=Point2D)
    dimensions: List[Dimension] = Field(default_factory=default_circle_dimensions)
    fit_mode: FitMode = FitMode.FIT_OVER
    validation: ProfileValidation = Field(default_factory=ProfileValidation)
    approved: bool = False
    approved_at: Optional[str] = None
    # Traced profile extension (S10.3 & S10.4)
    is_complex: bool = False
    complex_reason: Optional[str] = None
    traced_outer_contour: Optional[TracedContour] = None
    traced_hole_contours: List[TracedContour] = Field(default_factory=list)
    calibration_boundary: Optional[CalibrationBoundary] = None
    scale_calibration: Optional[ScaleCalibration] = None
    # 'exact_trace_ready', 'trace_requires_correction', 'simplified_envelope_only'
    verification_status: str = "pending_review"
    primitive_fallback_active: bool = False
    primitive_fallback_label: Optional[str] = (
        None  # Detected primitive proposal or simplified fallback label for review.
    )
    primitive_promotion_confirmed: bool = False
    primitive_detection_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    primitive_detection_reason: Optional[str] = None
    analysis_provider_name: Optional[str] = None  # e.g. 'mock', 'gemini'
    generation_unsupported: bool = False  # True if downstream KCL cannot handle this profile yet
    generation_unsupported_reason: Optional[str] = None
    # S10.5A: OpenCV pixel tracing artifacts and metrics
    cleaned_image_ref: Optional[str] = None
    analysis_image_ref: Optional[str] = None
    analysis_image_width: Optional[int] = None
    analysis_image_height: Optional[int] = None
    trace_svg_ref: Optional[str] = None
    overlay_svg_ref: Optional[str] = None
    raw_outer_point_count: Optional[int] = None
    simplified_outer_point_count: Optional[int] = None
    inner_contour_count: Optional[int] = None


class Connection(BaseModel):
    """Connection relationship definition."""

    mode: ConnectionMode = ConnectionMode.COAXIAL
    length_mm: float = 0.0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    angle_deg: float = 0.0
    extension_a_mm: float = 0.0
    extension_b_mm: float = 0.0


class Manufacturing(BaseModel):
    """Manufacturing process and material parameters."""

    process: ManufacturingProcess = ManufacturingProcess.FDM
    material: str = "PETG"
    wall_thickness_mm: float = 2.4
    clearance_a_mm: float = 0.3
    clearance_b_mm: float = 0.1


class ExportReferences(BaseModel):
    """References to export artifacts."""

    stl: Optional[str] = None
    step: Optional[str] = None
    kcl: Optional[str] = None


class ModelRevision(BaseModel):
    """Model revision metadata per ADR-005."""

    model_revision: int
    schema_revision: int
    status: ModelRevisionStatus = ModelRevisionStatus.DRAFT
    kcl_artifact_ref: Optional[str] = None
    preview_artifact_ref: Optional[str] = None
    exports: ExportReferences = Field(default_factory=ExportReferences)
    volume_cm3: Optional[float] = None
    zoo_model_id: Optional[str] = None
    kcl_hash: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=current_iso_timestamp)


class Project(BaseModel):
    """Canonical project model and workflow state container (ADR-001, ADR-005)."""

    project_id: str
    project_token: str
    display_name: str = "Adapter"
    provider_mode: ProviderMode = ProviderMode.MOCK
    schema_version: str = "0.1"
    state: WorkflowState = WorkflowState.NEW
    created_at: str = Field(default_factory=current_iso_timestamp)
    updated_at: str = Field(default_factory=current_iso_timestamp)
    current_schema_revision: int = 1
    current_model_revision: Optional[int] = None
    last_known_good_model_revision: Optional[int] = None
    interface_a: Interface = Field(default_factory=lambda: Interface(id="interface_a"))
    interface_b: Interface = Field(default_factory=lambda: Interface(id="interface_b"))
    connection: Connection = Field(default_factory=Connection)
    manufacturing: Manufacturing = Field(default_factory=Manufacturing)
    loft_plan: Optional[LoftPlan] = None
    model_revisions: List[ModelRevision] = Field(default_factory=list)


# --- DTOs / Request & Response Payloads ---


class ProjectCreateRequest(BaseModel):
    """Optional request payload for creating a project with a provider mode."""

    provider_mode: ProviderMode = ProviderMode.MOCK


class ProjectCreateResponse(BaseModel):
    """Response payload returned when a project is created."""

    project_id: str
    project_token: str
    display_name: str
    provider_mode: ProviderMode
    schema_version: str
    state: WorkflowState


class ProviderModeUpdateRequest(BaseModel):
    """Request payload for changing a project's active provider mode."""

    provider_mode: ProviderMode


class ProviderModeStatus(BaseModel):
    """Truthful provider capability state safe for browser display."""

    selected_mode: ProviderMode
    effective_mode: ProviderMode
    live_available: bool
    engine_provider: str
    export_provider: str
    analysis_provider: str
    agent_provider: str
    message: str


class ProjectPatchRequest(BaseModel):
    """Structured patch request for updating a project."""

    state: Optional[WorkflowState] = None
    connection: Optional[Connection] = None
    manufacturing: Optional[Manufacturing] = None


class InterfacePatchRequest(BaseModel):
    """Structured patch request for updating an interface."""

    source_image_ref: Optional[str] = None
    profile_type: Optional[ProfileType] = None
    trace_profile_type: Optional[ProfileType] = None
    resolved_profile_type: Optional[ProfileType] = None
    resolution_status: Optional[ShapeResolutionStatus] = None
    resolution_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    resolution_reason: Optional[str] = None
    resolved_dimensions: Optional[dict[str, float]] = None
    is_complex: Optional[bool] = None
    complex_reason: Optional[str] = None
    profile_points: Optional[List[Point2D]] = None
    center: Optional[Point2D] = None
    dimensions: Optional[List[Dimension]] = None
    fit_mode: Optional[FitMode] = None
    validation: Optional[ProfileValidation] = None
    traced_outer_contour: Optional[TracedContour] = None
    traced_hole_contours: Optional[List[TracedContour]] = None
    scale_calibration: Optional[ScaleCalibration] = None
    verification_status: Optional[str] = None
    primitive_fallback_active: Optional[bool] = None
    primitive_fallback_label: Optional[str] = None
    primitive_promotion_confirmed: Optional[bool] = None
    primitive_detection_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    primitive_detection_reason: Optional[str] = None
    approved: Optional[bool] = None
    cleaned_image_ref: Optional[str] = None
    analysis_image_ref: Optional[str] = None
    analysis_image_width: Optional[int] = None
    analysis_image_height: Optional[int] = None
    trace_svg_ref: Optional[str] = None
    overlay_svg_ref: Optional[str] = None
    raw_outer_point_count: Optional[int] = None
    simplified_outer_point_count: Optional[int] = None
    inner_contour_count: Optional[int] = None


class ScaleSnapRequest(BaseModel):
    """Request payload for snapping a trace-space click to valid traced geometry."""

    point: Point2D


class ScaleSnapResponse(BaseModel):
    """Snapped trace-space point and nearest-geometry metadata."""

    point: Point2D
    distance_px: float
    feature_id: str


class TwoPointScaleCalibrationRequest(BaseModel):
    """Request payload for drafting or confirming manual two-point scale calibration."""

    point_a: Point2D
    point_b: Point2D
    real_distance_mm: float
    confirmed: bool = False


class ConnectionUpdateRequest(BaseModel):
    """Request payload for updating connection parameters."""

    mode: ConnectionMode
    length_mm: float
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0
    angle_deg: float = 0.0
    extension_a_mm: float = 0.0
    extension_b_mm: float = 0.0


class ManufacturingUpdateRequest(BaseModel):
    """Request payload for updating manufacturing parameters."""

    process: ManufacturingProcess
    material: str
    wall_thickness_mm: float
    clearance_a_mm: float
    clearance_b_mm: float


class ModelSucceedRequest(BaseModel):
    """Payload for completing model generation successfully."""

    model_revision: int
    kcl_artifact_ref: Optional[str] = None
    preview_artifact_ref: Optional[str] = None
    volume_cm3: Optional[float] = None
    zoo_model_id: Optional[str] = None
    kcl_hash: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class ModelFailRequest(BaseModel):
    """Payload for registering a model generation failure."""

    model_revision: int
    error_message: str
    warnings: List[str] = Field(default_factory=list)


class ExportCompleteRequest(BaseModel):
    """Payload for completing export generation."""

    stl_artifact_ref: Optional[str] = None
    step_artifact_ref: Optional[str] = None
    kcl_artifact_ref: Optional[str] = None


class ExportFormatStatus(str, Enum):
    """Status lifecycle for individual export formats per S8."""

    NOT_STARTED = "not_started"
    PREPARING = "preparing"
    READY = "ready"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class FormatExportDetail(BaseModel):
    """Detail container for individual export format status."""

    format: str
    status: ExportFormatStatus = ExportFormatStatus.NOT_STARTED
    artifact_ref: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    zoo_model_id: Optional[str] = None
    kcl_hash: Optional[str] = None
    error_id: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[str] = None


class ExportGenerateRequest(BaseModel):
    """Request payload for triggering format export generation."""

    formats: List[str] = Field(default_factory=lambda: ["stl", "step", "kcl"])
    mock_scenario: Optional[str] = None


class ExportStatusResponse(BaseModel):
    """Response payload for export status query."""

    project_id: str
    model_revision: int
    schema_revision: int
    units: str = "mm"
    model_status: str
    volume_cm3: Optional[float] = None
    formats: dict[str, FormatExportDetail] = Field(default_factory=dict)


class UploadResponseData(BaseModel):
    """Metadata response after image file upload."""

    artifact_ref: str
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: str


class AnalysisResult(BaseModel):
    """Structured profile extraction result from analysis provider."""

    input_type: str = "dimensioned_technical_drawing"
    profile_type: ProfileType
    trace_profile_type: Optional[ProfileType] = None
    resolved_profile_type: Optional[ProfileType] = None
    resolution_status: ShapeResolutionStatus = ShapeResolutionStatus.RESOLVED
    resolution_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    resolution_reason: Optional[str] = None
    resolved_dimensions: dict[str, float] = Field(default_factory=dict)
    candidate_points: List[Point2D] = Field(default_factory=list)
    candidate_dimensions: List[Dimension] = Field(default_factory=list)
    provenance: DimensionProvenance = DimensionProvenance.IMAGE_EXTRACTED
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    success: bool = True
    model_used: Optional[str] = None
    latency_seconds: Optional[float] = None
    fallback_triggered: bool = False
    usage_metadata: Optional[dict] = None
    # S10.3 & S10.4: provider provenance and complex trace fields
    analysis_provider_name: Optional[str] = None  # 'mock', 'gemini', etc.
    traced_outer_contour: Optional[TracedContour] = None
    traced_hole_contours: List[TracedContour] = Field(default_factory=list)
    calibration_boundary: Optional[CalibrationBoundary] = None
    scale_calibration: Optional[ScaleCalibration] = None
    is_complex: bool = False
    complex_reason: Optional[str] = None
    # S10.5A: OpenCV pixel tracing artifacts and metrics
    cleaned_image_ref: Optional[str] = None
    analysis_image_ref: Optional[str] = None
    analysis_image_width: Optional[int] = None
    analysis_image_height: Optional[int] = None
    trace_svg_ref: Optional[str] = None
    overlay_svg_ref: Optional[str] = None
    raw_outer_point_count: Optional[int] = None
    simplified_outer_point_count: Optional[int] = None
    inner_contour_count: Optional[int] = None
    # S10.5G.1: Temporary diagnostic fields
    provider_used: Optional[str] = None
    request_id: Optional[str] = None
    fallback_used: bool = False
    region_count: Optional[int] = None


class ValidationIssue(BaseModel):
    """Structured validation error or warning details with stable error ID."""

    id: str
    message: str
    field: Optional[str] = None
    recovery_steps: List[str] = Field(default_factory=list)


class ConnectionValidationResult(BaseModel):
    """Validation output for connection geometry and manufacturing rules."""

    is_valid: bool
    blocking_errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    recommended_values: dict[str, float] = Field(default_factory=dict)


class ConnectionConfigRequest(BaseModel):
    """Combined request payload for updating connection and manufacturing parameters."""

    connection: ConnectionUpdateRequest
    manufacturing: ManufacturingUpdateRequest


class ParameterChange(BaseModel):
    """Single parameter change proposal per Stage S9."""

    field: str
    current_value: float
    proposed_value: float
    unit: str = "mm"
    reason: str = ""


class RevisionProposeRequest(BaseModel):
    """Request payload for proposing natural language model revisions."""

    prompt: str
    provider: Optional[str] = None


class AgentProposalResult(BaseModel):
    """Structured proposal result returned by Zoo Agent API / AgentService."""

    changes: List[ParameterChange] = Field(default_factory=list)
    summary: str = ""
    is_valid: bool = True
    validation_errors: List[ValidationIssue] = Field(default_factory=list)
    validation_warnings: List[ValidationIssue] = Field(default_factory=list)
    raw_response: Optional[str] = None
    provider_used: Optional[str] = None


class RevisionConfirmRequest(BaseModel):
    """Request payload for confirming parameter changes."""

    changes: List[ParameterChange]


