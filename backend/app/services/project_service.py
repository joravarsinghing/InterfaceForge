"""Project service layer managing domain workflow state transitions and schema invariants."""

import io
import logging
import math
import os
import secrets
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image

from app.core.config import settings
from app.core.exceptions import (
    ExportArtifactNotFoundError,
    InvalidConnectionConfigError,
    InvalidFileUploadError,
    InvalidInterfaceApprovalError,
    InvalidProjectTokenError,
    MissingPrerequisiteError,
    ProjectNotFoundError,
    SchemaVersionMismatchError,
    StaleModelOperationError,
    UnsupportedExportFormatError,
)
from app.core.path_safety import resolve_path_within
from app.models.schema import (
    AnalysisResult,
    CalibrationBoundary,
    Connection,
    ConnectionUpdateRequest,
    ConnectionValidationResult,
    Dimension,
    DimensionProvenance,
    ExportCompleteRequest,
    ExportFormatStatus,
    ExportStatusResponse,
    FormatExportDetail,
    Interface,
    InterfacePatchRequest,
    LoftPlan,
    Manufacturing,
    ManufacturingUpdateRequest,
    ModelFailRequest,
    ModelRevision,
    ModelRevisionStatus,
    ModelSucceedRequest,
    Point2D,
    ProfileType,
    ProfileValidation,
    Project,
    ProjectPatchRequest,
    ProviderMode,
    ProviderModeStatus,
    ScaleCalibration,
    ScaleSnapResponse,
    ShapeResolutionStatus,
    TwoPointScaleCalibrationRequest,
    UploadResponseData,
    WorkflowState,
    current_iso_timestamp,
)
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.analysis_provider import (
    AnalysisProvider,
    get_analysis_provider,
)
from app.services.connection_validation import validate_connection_and_manufacturing
from app.services.export_provider import (
    ExportProvider,
    get_export_provider,
    validate_artifact_content,
)
from app.services.kcl_compiler import KCLCompileResult, compile_project_to_kcl
from app.services.loft_plan import ensure_loft_plan
from app.services.profile_geometry import (
    bbox,
    classify_primitive_candidate,
    primitive_boundary_contour,
    set_calibrated_primitive_dimensions,
)
from app.services.profile_validation import validate_interface_profile

logger = logging.getLogger(__name__)


SUPPORTED_MEASUREMENT_TYPES = {
    "overall_width": "Overall Width",
    "overall_height": "Overall Height",
    "hole_diameter": "Hole Diameter",
    "reference_distance": "Reference Distance",
}


def _profile_geometry_fingerprint(interface: Interface) -> tuple:
    outer = interface.traced_outer_contour
    holes = interface.traced_hole_contours or []

    def pts_key(points: list[Point2D]) -> tuple[tuple[float, float], ...]:
        return tuple((round(p.x, 6), round(p.y, 6)) for p in points)

    return (
        str(interface.profile_type),
        pts_key(interface.profile_points or []),
        pts_key(outer.points) if outer else None,
        tuple((h.id, h.decision, pts_key(h.points)) for h in holes),
    )


def _measurement_fingerprint(interface: Interface) -> tuple:
    scale = interface.scale_calibration
    dims = tuple(
        (d.id, round(float(d.value), 6), d.unit, str(d.provenance), d.feature_ref)
        for d in interface.dimensions
    )
    return (
        dims,
        (
            scale.reference_dimension,
            scale.method,
            (round(float(scale.point_a.x), 6), round(float(scale.point_a.y), 6))
            if scale.point_a
            else None,
            (round(float(scale.point_b.x), 6), round(float(scale.point_b.y), 6))
            if scale.point_b
            else None,
            round(float(scale.pixel_distance), 6),
            round(float(scale.real_distance_mm), 6),
            round(float(scale.scale_factor), 9),
            getattr(scale, "unit", "mm"),
        )
        if scale
        else None,
    )


def _apply_known_measurement(
    interface: Interface, measurement_type: str, value: float, unit: str
) -> None:
    if measurement_type not in SUPPORTED_MEASUREMENT_TYPES:
        raise InvalidFileUploadError(
            f"Unsupported known measurement type '{measurement_type}'.",
            recovery_steps=[
                "Use overall_width, overall_height, hole_diameter, or reference_distance."
            ],
        )
    if unit != "mm":
        raise InvalidFileUploadError(
            f"Unsupported known measurement unit '{unit}'.",
            recovery_steps=["Use millimetres (mm) for this submission-critical flow."],
        )
    if value <= 0:
        raise InvalidFileUploadError(
            "Known measurement value must be positive.",
            recovery_steps=["Enter a positive millimetre value or leave measurement blank."],
        )

    label = SUPPORTED_MEASUREMENT_TYPES[measurement_type]
    existing = {d.id: d for d in interface.dimensions}
    existing[measurement_type] = Dimension(
        id=measurement_type,
        label=label,
        value=value,
        unit=unit,
        provenance=DimensionProvenance.USER_ENTERED,
        confidence=1.0,
        critical=True,
        feature_ref="outer_contour"
        if measurement_type in {"overall_width", "overall_height"}
        else None,
        source_annotation=None,
        consistency_state="valid",
    )
    interface.dimensions = list(existing.values())
    pixel_distance = 0.0
    if (
        interface.scale_calibration
        and interface.scale_calibration.reference_dimension == measurement_type
    ):
        pixel_distance = interface.scale_calibration.pixel_distance
    interface.scale_calibration = ScaleCalibration(
        source="user_calibration",
        method="known_measurement",
        reference_dimension=measurement_type,
        pixel_distance=pixel_distance,
        real_distance_mm=value,
        scale_factor=value / pixel_distance if pixel_distance > 0 else 0.0,
        confidence=1.0,
        confirmed=False,
    )


def _merge_upload_measurement_after_analysis(interface: Interface, previous: Interface) -> None:
    previous_scale = previous.scale_calibration
    if not previous_scale or previous_scale.source != "user_calibration":
        return
    measurement_type = previous_scale.reference_dimension or "overall_width"
    if measurement_type not in SUPPORTED_MEASUREMENT_TYPES:
        return
    value = previous_scale.real_distance_mm
    unit = "mm"
    result_pixel_distance = 0.0
    if interface.scale_calibration:
        result_pixel_distance = interface.scale_calibration.pixel_distance
    _apply_known_measurement(interface, measurement_type, value, unit)
    if interface.scale_calibration:
        interface.scale_calibration.pixel_distance = result_pixel_distance
        interface.scale_calibration.confirmed = False


def _finite_point(point: Point2D) -> bool:
    return math.isfinite(point.x) and math.isfinite(point.y)


def _trace_geometry_segments(interface: Interface) -> list[tuple[Point2D, Point2D, str]]:
    contours = []
    if interface.traced_outer_contour is not None:
        contours.append(interface.traced_outer_contour)
    contours.extend(
        contour
        for contour in (interface.traced_hole_contours or [])
        if getattr(contour, "decision", "include") == "include"
    )
    segments: list[tuple[Point2D, Point2D, str]] = []
    for contour in contours:
        points = contour.points or []
        if len(points) < 2:
            continue
        count = len(points)
        edge_count = count if contour.is_closed else count - 1
        for idx in range(edge_count):
            a = points[idx]
            b = points[(idx + 1) % count]
            if _finite_point(a) and _finite_point(b) and (a.x != b.x or a.y != b.y):
                segments.append((a, b, contour.id or "trace_geometry"))
    return segments


def _trace_bbox(interface: Interface) -> tuple[float, float, float, float] | None:
    points = []
    if interface.traced_outer_contour is not None:
        points.extend(interface.traced_outer_contour.points or [])
    for hole in interface.traced_hole_contours or []:
        points.extend(hole.points or [])
    points = [p for p in points if _finite_point(p)]
    if not points:
        return None
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def _ensure_point_within_trace_bounds(interface: Interface, point: Point2D) -> None:
    if not _finite_point(point):
        raise InvalidInterfaceApprovalError(
            "Calibration point must use finite trace-space coordinates.",
            recovery_steps=["Select a point inside the traced SVG viewport."],
        )
    bbox = _calibration_bbox(interface)
    if bbox is None:
        raise InvalidInterfaceApprovalError(
            "Cannot calibrate scale: traced geometry is missing.",
            recovery_steps=["Re-run analysis or upload a cleaner interface image."],
        )
    min_x, max_x, min_y, max_y = bbox
    pad = max(max_x - min_x, max_y - min_y, 1.0) * 0.05
    if not (min_x - pad <= point.x <= max_x + pad and min_y - pad <= point.y <= max_y + pad):
        raise InvalidInterfaceApprovalError(
            "Calibration point is outside the traced profile bounds.",
            recovery_steps=["Select points on the visible traced contour."],
        )


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _canonical_primitive_trace_points(interface: Interface) -> list[Point2D] | None:
    if _uses_trace_calibration(interface) or interface.profile_type not in SUPPORTED_GENERATION_PROFILE_TYPES:
        return None
    outer = interface.traced_outer_contour
    if outer is None or len(outer.points) < 4:
        return None
    bbox = _trace_bbox(interface)
    if bbox is None:
        return None
    min_x, max_x, min_y, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    if interface.profile_type == ProfileType.CIRCLE:
        radius = (width + height) / 4.0
        return [
            Point2D(
                x=round(cx + radius * math.cos(2.0 * math.pi * idx / 64), 4),
                y=round(cy + radius * math.sin(2.0 * math.pi * idx / 64), 4),
            )
            for idx in range(64)
        ]

    if interface.profile_type == ProfileType.RECTANGLE:
        return [
            Point2D(x=min_x, y=min_y),
            Point2D(x=max_x, y=min_y),
            Point2D(x=max_x, y=max_y),
            Point2D(x=min_x, y=max_y),
        ]

    classification = classify_primitive_candidate(outer.points)
    radius_candidate = classification.corner_radius_px if classification else None
    if radius_candidate is None or not math.isfinite(radius_candidate) or radius_candidate <= 0:
        radius_dimension = next(
            (
                d.value
                for d in interface.dimensions
                if d.id == "corner_radius" and math.isfinite(d.value) and d.value > 0
            ),
            0.0,
        )
        radius = float(radius_dimension)
    else:
        radius = float(radius_candidate)
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    if radius <= 0:
        return [
            Point2D(x=min_x, y=min_y),
            Point2D(x=max_x, y=min_y),
            Point2D(x=max_x, y=max_y),
            Point2D(x=min_x, y=max_y),
        ]

    points: list[Point2D] = []
    centers = [
        (max_x - radius, max_y - radius, 0.0, math.pi / 2.0),
        (min_x + radius, max_y - radius, math.pi / 2.0, math.pi),
        (min_x + radius, min_y + radius, math.pi, 3.0 * math.pi / 2.0),
        (max_x - radius, min_y + radius, 3.0 * math.pi / 2.0, 2.0 * math.pi),
    ]
    for corner_x, corner_y, start, end in centers:
        for idx in range(9):
            angle = start + (end - start) * idx / 8.0
            points.append(
                Point2D(
                    x=round(corner_x + radius * math.cos(angle), 4),
                    y=round(corner_y + radius * math.sin(angle), 4),
                )
            )
    return points


def _uses_trace_calibration(interface: Interface) -> bool:
    """Image traces are always the calibration boundary."""
    return bool(
        interface.traced_outer_contour
        and (
            interface.profile_type == ProfileType.CUSTOM_CLOSED
            or interface.source_image_ref is not None
            or interface.scale_calibration is not None
        )
    )


def _ensure_calibration_boundary(interface: Interface) -> None:
    """Create the one canonical primitive boundary and retain it on the interface."""
    if _uses_trace_calibration(interface) or interface.profile_type not in SUPPORTED_GENERATION_PROFILE_TYPES:
        return
    if interface.calibration_boundary and len(interface.calibration_boundary.points) >= 4:
        return
    points = _canonical_primitive_trace_points(interface)
    if not points:
        return
    box = bbox(points)
    if box is None:
        return
    min_x, max_x, min_y, max_y = box
    fitted_width = max_x - min_x
    fitted_height = max_y - min_y
    fitted_diameter = (
        (fitted_width + fitted_height) / 2.0
        if interface.profile_type == ProfileType.CIRCLE
        else None
    )
    fitted_radius = None
    if interface.profile_type == ProfileType.ROUNDED_RECTANGLE:
        candidate = (
            classify_primitive_candidate(interface.traced_outer_contour.points)
            if interface.traced_outer_contour
            else None
        )
        if candidate and candidate.corner_radius_px and math.isfinite(candidate.corner_radius_px):
            fitted_radius = min(candidate.corner_radius_px, fitted_width / 2.0, fitted_height / 2.0)
        else:
            dim = next(
                (d.value for d in interface.dimensions if d.id == "corner_radius" and d.value > 0),
                None,
            )
            fitted_radius = min(dim, fitted_width / 2.0, fitted_height / 2.0) if dim else 0.0
    interface.calibration_boundary = CalibrationBoundary(
        points=points,
        is_closed=True,
        fitted_width=round(fitted_width, 4),
        fitted_height=round(fitted_height, 4),
        fitted_diameter=round(fitted_diameter, 4) if fitted_diameter is not None else None,
        fitted_corner_radius=round(fitted_radius, 4) if fitted_radius is not None else None,
    )


def _calibration_geometry_segments(interface: Interface) -> list[tuple[Point2D, Point2D, str]]:
    if _uses_trace_calibration(interface):
        return [
            (a, b, "canonical_primitive_boundary")
            for a, b, _feature_id in _trace_geometry_segments(interface)
        ]
    _ensure_calibration_boundary(interface)
    canonical = (
        interface.calibration_boundary.points
        if interface.calibration_boundary
        else _canonical_primitive_trace_points(interface)
    )
    if canonical and len(canonical) >= 4:
        return [
            (canonical[idx], canonical[(idx + 1) % len(canonical)], "canonical_primitive_boundary")
            for idx in range(len(canonical))
        ]
    return _trace_geometry_segments(interface)


def _calibration_bbox(interface: Interface) -> tuple[float, float, float, float] | None:
    if _uses_trace_calibration(interface):
        return _trace_bbox(interface)
        _ensure_calibration_boundary(interface)
    canonical = (
        interface.calibration_boundary.points
        if interface.calibration_boundary
        else _canonical_primitive_trace_points(interface)
    )
    if canonical and len(canonical) >= 4:
        return (
            min(point.x for point in canonical),
            max(point.x for point in canonical),
            min(point.y for point in canonical),
            max(point.y for point in canonical),
        )
    return _trace_bbox(interface)


def _canonical_boundary_node(interface: Interface, point: Point2D) -> Point2D:
    if (
        interface.profile_type == ProfileType.TRACED_CLOSED
        or interface.resolved_profile_type is None
        or not interface.primitive_fallback_active
    ):
        return _snap_point_to_trace(interface, point).point
    _ensure_calibration_boundary(interface)
    boundary = interface.calibration_boundary
    if boundary and boundary.points:
        nearest = min(boundary.points, key=lambda candidate: _distance(candidate, point))
        if _distance(nearest, point) <= 1e-6:
            return nearest
        raise InvalidInterfaceApprovalError(
            "Calibration point is not a canonical profile boundary node.",
            recovery_steps=["Select one of the visible boundary nodes."],
        )
    return _snap_point_to_trace(interface, point).point


def _snap_point_to_trace(interface: Interface, point: Point2D) -> ScaleSnapResponse:
    _ensure_point_within_trace_bounds(interface, point)
    segments = _calibration_geometry_segments(interface)
    if not segments:
        raise InvalidInterfaceApprovalError(
            "Cannot calibrate scale: no valid trace segments are available.",
            recovery_steps=["Re-run analysis or upload a cleaner interface image."],
        )

    bbox = _calibration_bbox(interface)
    max_dim = 1.0
    if bbox is not None:
        min_x, max_x, min_y, max_y = bbox
        max_dim = max(max_x - min_x, max_y - min_y, 1.0)
    node_tolerance = max(3.0, max_dim * 0.035)
    edge_tolerance = max(4.0, max_dim * 0.08)

    best_node: tuple[float, Point2D, str] | None = None
    _ensure_calibration_boundary(interface)
    canonical_nodes = (
        interface.calibration_boundary.points
        if interface.calibration_boundary
        else _canonical_primitive_trace_points(interface)
    )
    if canonical_nodes:
        for vertex in canonical_nodes:
            if not _finite_point(vertex):
                continue
            dist = _distance(point, vertex)
            if best_node is None or dist < best_node[0]:
                best_node = (dist, vertex, "canonical_primitive_boundary")
    else:
        contours = [interface.traced_outer_contour] if interface.traced_outer_contour else []
        contours.extend(interface.traced_hole_contours or [])
        for contour in contours:
            if getattr(contour, "decision", "include") != "include":
                continue
            for idx, vertex in enumerate(contour.points or []):
                if not _finite_point(vertex):
                    continue
                dist = _distance(point, vertex)
                if best_node is None or dist < best_node[0]:
                    best_node = (dist, vertex, "canonical_primitive_boundary")
    if best_node is not None and best_node[0] <= node_tolerance:
        return ScaleSnapResponse(
            point=best_node[1], distance_px=best_node[0], feature_id=best_node[2]
        )

    best: tuple[float, Point2D, str] | None = None
    for a, b, feature_id in segments:
        dx = b.x - a.x
        dy = b.y - a.y
        denom = dx * dx + dy * dy
        if denom <= 0:
            continue
        t = ((point.x - a.x) * dx + (point.y - a.y) * dy) / denom
        t = max(0.0, min(1.0, t))
        snapped = Point2D(x=a.x + t * dx, y=a.y + t * dy)
        dist = _distance(point, snapped)
        if best is None or dist < best[0]:
            best = (dist, snapped, feature_id)
    if best is None:
        raise InvalidInterfaceApprovalError(
            "Cannot calibrate scale: trace segments are degenerate.",
            recovery_steps=["Re-run analysis or upload a cleaner interface image."],
        )
    if best[0] > edge_tolerance:
        raise InvalidInterfaceApprovalError(
            "Calibration point is too far from the visible profile boundary.",
            recovery_steps=["Select a point on or near the visible profile edge."],
        )
    return ScaleSnapResponse(point=best[1], distance_px=best[0], feature_id=best[2])


def _confirmed_primitive_promotion_type(interface: Interface) -> ProfileType | None:
    if not interface.primitive_promotion_confirmed or interface.traced_outer_contour is None:
        return None
    if interface.profile_type in (
        ProfileType.CIRCLE,
        ProfileType.RECTANGLE,
        ProfileType.ROUNDED_RECTANGLE,
    ):
        return interface.profile_type
    candidate = classify_primitive_candidate(interface.traced_outer_contour.points)
    if candidate is None:
        return None
    return candidate.profile_type


def _supported_primitive_candidate_type(interface: Interface) -> ProfileType | None:
    if interface.profile_type in (
        ProfileType.CIRCLE,
        ProfileType.RECTANGLE,
        ProfileType.ROUNDED_RECTANGLE,
    ):
        return interface.profile_type
    if interface.traced_outer_contour is None:
        return None
    candidate = classify_primitive_candidate(interface.traced_outer_contour.points)
    if candidate is None:
        return None
    return candidate.profile_type


def _normalize_confirmed_primitive_promotion(interface: Interface) -> bool:
    promoted_type = _confirmed_primitive_promotion_type(interface)
    if promoted_type is None:
        return False
    changed = interface.profile_type != promoted_type or interface.generation_unsupported
    interface.profile_type = promoted_type
    interface.primitive_fallback_active = True
    interface.verification_status = "primitive_promotion_confirmed"
    interface.generation_unsupported = False
    interface.generation_unsupported_reason = None
    if interface.scale_calibration and interface.scale_calibration.confirmed:
        before = _measurement_fingerprint(interface)
        set_calibrated_primitive_dimensions(interface, interface.scale_calibration.scale_factor)
        changed = changed or before != _measurement_fingerprint(interface)
    return changed


def _upsert_scaled_dimension(
    interface: Interface, dim_id: str, label: str, value: float, feature_ref: str
) -> None:
    existing = {d.id: d for d in interface.dimensions}
    prev = existing.get(dim_id)
    existing[dim_id] = Dimension(
        id=dim_id,
        label=label,
        value=round(value, 4),
        unit="mm",
        provenance=DimensionProvenance.USER_ENTERED
        if prev and prev.provenance == DimensionProvenance.USER_ENTERED
        else DimensionProvenance.SYSTEM_INFERRED,
        confidence=1.0,
        critical=True,
        feature_ref=feature_ref,
        consistency_state="recalculated",
    )
    interface.dimensions = list(existing.values())


def _update_derived_dimensions_from_scale(interface: Interface, scale_factor: float) -> None:
    bbox = _trace_bbox(interface)
    if bbox is None:
        return
    min_x, max_x, min_y, max_y = bbox
    _upsert_scaled_dimension(
        interface, "overall_width", "Overall Width", (max_x - min_x) * scale_factor, "outer_contour"
    )
    _upsert_scaled_dimension(
        interface,
        "overall_height",
        "Overall Height",
        (max_y - min_y) * scale_factor,
        "outer_contour",
    )


SUPPORTED_GENERATION_PROFILE_TYPES = {
    ProfileType.CIRCLE,
    ProfileType.RECTANGLE,
    ProfileType.ROUNDED_RECTANGLE,
}

AUTO_RESOLUTION_THRESHOLDS = {
    ProfileType.CIRCLE: 0.90,
    ProfileType.RECTANGLE: 0.90,
    ProfileType.ROUNDED_RECTANGLE: 0.70,
}


def _resolved_dimension_map(interface: Interface) -> dict[str, float]:
    values: dict[str, float] = {}
    for dim in interface.dimensions:
        if dim.id in {"outer_diameter", "diameter", "width", "height", "corner_radius"}:
            if math.isfinite(dim.value) and dim.value > 0:
                key = "diameter" if dim.id in {"outer_diameter", "diameter"} else dim.id
                values[key] = round(float(dim.value), 4)
    return values


def _apply_authoritative_shape_resolution(interface: Interface, *, repair_reason: str | None = None) -> bool:
    """Normalize traced projects without classifying or rebuilding their contour."""
    before = interface.model_dump()
    outer = interface.traced_outer_contour
    has_trace = bool(outer and len(outer.points) >= 4 and outer.is_closed)
    original = interface.profile_type
    if has_trace:
        interface.profile_type = ProfileType.CUSTOM_CLOSED
        interface.trace_profile_type = ProfileType.CUSTOM_CLOSED
        interface.resolved_profile_type = ProfileType.CUSTOM_CLOSED
        interface.resolution_status = ShapeResolutionStatus.RESOLVED
        interface.resolution_confidence = 1.0
        interface.resolution_reason = "Approved traced contour is authoritative custom geometry."
        interface.primitive_fallback_active = False
        interface.primitive_fallback_label = None
        interface.primitive_promotion_confirmed = False
        interface.primitive_detection_confidence = None
        interface.primitive_detection_reason = None
        interface.verification_status = "trace_ready"
        interface.generation_unsupported = False
        interface.generation_unsupported_reason = None
    elif original in SUPPORTED_GENERATION_PROFILE_TYPES:
        interface.trace_profile_type = original
        interface.resolved_profile_type = original
        interface.resolution_status = ShapeResolutionStatus.RESOLVED
        interface.generation_unsupported = False
        interface.generation_unsupported_reason = None
    else:
        interface.profile_type = ProfileType.CUSTOM_CLOSED
        interface.trace_profile_type = ProfileType.CUSTOM_CLOSED
        interface.resolved_profile_type = ProfileType.CUSTOM_CLOSED
        interface.resolution_status = ShapeResolutionStatus.UNSUPPORTED
        interface.generation_unsupported = True
        interface.generation_unsupported_reason = "A valid closed contour is required."
    interface.resolved_dimensions = _resolved_dimension_map(interface)
    _ensure_calibration_boundary(interface)
    if repair_reason and before != interface.model_dump():
        interface.resolution_repaired_at = current_iso_timestamp()
        interface.resolution_repair_reason = repair_reason
    return before != interface.model_dump()


class ProjectService:
    """Service layer enforcing canonical schema revision rules and workflow state invariants."""

    SUPPORTED_SCHEMA_VERSION = "0.1"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, repository: Optional[SQLiteProjectRepository] = None) -> None:
        self.repository = repository or SQLiteProjectRepository()

    def _verify_project_and_token(
        self, project_id: str, project_token: Optional[str] = None
    ) -> Project:
        """Fetch project by ID and verify optional authorization token and schema version."""
        project = self.repository.get(project_id)
        if not project:
            raise ProjectNotFoundError(project_id)

        if project.schema_version != self.SUPPORTED_SCHEMA_VERSION:
            raise SchemaVersionMismatchError(
                provided_version=project.schema_version,
                expected_version=self.SUPPORTED_SCHEMA_VERSION,
            )

        if project_token is not None and project_token != project.project_token:
            raise InvalidProjectTokenError()

        repaired = False
        for interface in (project.interface_a, project.interface_b):
            repaired = (
                _apply_authoritative_shape_resolution(
                    interface, repair_reason="loaded_project_shape_resolution_normalization"
                )
                or repaired
            )
        if repaired:
            project.current_schema_revision += 1
            self._mark_current_model_stale_if_exists(project)
            project.updated_at = current_iso_timestamp()
            project = self.repository.save(project)

        return project

    def _mark_current_model_stale_if_exists(self, project: Project) -> None:
        """Mark current model revision as stale and invalidate derived loft geometry."""
        project.loft_plan = None
        if project.current_model_revision is not None:
            for rev in project.model_revisions:
                if (
                    rev.model_revision == project.current_model_revision
                    and rev.status == ModelRevisionStatus.CURRENT
                ):
                    rev.status = ModelRevisionStatus.STALE

    def create_project(self, provider_mode: ProviderMode = ProviderMode.MOCK) -> Project:
        """Create a new project with initialized canonical schema and unguessable token."""
        project_id = str(uuid.uuid4())
        project_token = f"tok_{secrets.token_urlsafe(24)}"
        now = current_iso_timestamp()

        project_count = len(self.repository.list_all()) + 1

        project = Project(
            project_id=project_id,
            project_token=project_token,
            display_name=f"Adapter {project_count}",
            provider_mode=provider_mode,
            schema_version=self.SUPPORTED_SCHEMA_VERSION,
            state=WorkflowState.NEW,
            created_at=now,
            updated_at=now,
            current_schema_revision=1,
            current_model_revision=None,
            last_known_good_model_revision=None,
            interface_a=Interface(id="interface_a"),
            interface_b=Interface(id="interface_b"),
        )
        return self.repository.save(project)

    def get_provider_mode_status_for_selection(
        self,
        selected: ProviderMode,
    ) -> ProviderModeStatus:
        """Return provider state for a requested mode without exposing credentials."""
        live_available = bool(settings.zoo_api_token)
        effective = (
            ProviderMode.LIVE
            if selected == ProviderMode.LIVE and live_available
            else ProviderMode.MOCK
        )
        analysis_provider = "opencv"
        if effective == ProviderMode.LIVE:
            message = (
                "Live Zoo providers are active for future generation, export, "
                "and Agent requests; clean-profile analysis uses OpenCV by default."
            )
        elif selected == ProviderMode.LIVE:
            message = (
                "Live mode is unavailable because required backend credentials are not configured."
            )
        else:
            message = "Mock / offline providers are active for this project."
        return ProviderModeStatus(
            selected_mode=selected,
            effective_mode=effective,
            live_available=live_available,
            engine_provider="zoo" if effective == ProviderMode.LIVE else "mock",
            export_provider="zoo" if effective == ProviderMode.LIVE else "mock",
            analysis_provider=analysis_provider,
            agent_provider="zoo" if effective == ProviderMode.LIVE else "mock",
            message=message,
        )

    def get_provider_mode_status(
        self,
        project: Project,
        requested_mode: Optional[ProviderMode] = None,
    ) -> ProviderModeStatus:
        """Return provider state without exposing credentials."""
        selected = requested_mode or project.provider_mode
        return self.get_provider_mode_status_for_selection(selected)

    def set_provider_mode(
        self,
        project_id: str,
        provider_mode: ProviderMode,
        project_token: Optional[str] = None,
    ) -> tuple[Project, ProviderModeStatus]:
        """Set the project provider mode when the requested mode is actually available."""
        project = self._verify_project_and_token(project_id, project_token)
        status = self.get_provider_mode_status(project, requested_mode=provider_mode)
        if provider_mode == ProviderMode.LIVE and status.effective_mode != ProviderMode.LIVE:
            return project, status
        project.provider_mode = provider_mode
        project.updated_at = current_iso_timestamp()
        saved = self.repository.save(project)
        return saved, self.get_provider_mode_status(saved)

    def get_project(self, project_id: str, project_token: Optional[str] = None) -> Project:
        """Retrieve project by ID."""
        return self._verify_project_and_token(project_id, project_token)

    def update_project_patch(
        self, project_id: str, patch: ProjectPatchRequest, project_token: Optional[str] = None
    ) -> Project:
        """Apply patch to top-level project properties."""
        project = self._verify_project_and_token(project_id, project_token)

        if patch.state is not None:
            project.state = patch.state

        if patch.connection is not None:
            project.connection = patch.connection
            project.current_schema_revision += 1
            self._mark_current_model_stale_if_exists(project)

        if patch.manufacturing is not None:
            project.manufacturing = patch.manufacturing
            project.current_schema_revision += 1
            self._mark_current_model_stale_if_exists(project)

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def mark_interface_uploaded(
        self,
        project_id: str,
        interface_id: str,
        source_image_ref: str,
        project_token: Optional[str] = None,
    ) -> Project:
        """Mark an interface as uploaded with a source image reference."""
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        target_interface.source_image_ref = source_image_ref
        target_interface.approved = False
        target_interface.approved_at = None

        if interface_id == "interface_a":
            project.interface_a = target_interface
        else:
            project.interface_b = target_interface

        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if interface_id == "interface_a":
            project.state = WorkflowState.INTERFACE_A_UPLOADED
        else:
            project.state = WorkflowState.INTERFACE_B_UPLOADED

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def upload_interface_image(
        self,
        project_id: str,
        interface_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        project_token: Optional[str] = None,
        known_measurement_type: Optional[str] = None,
        known_measurement_value: Optional[float] = None,
        known_measurement_unit: str = "mm",
    ) -> UploadResponseData:
        """Securely validate, save, and record an uploaded interface image."""
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )

        # Enforce prerequisite: Interface B upload requires Interface A approval
        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be uploaded.",
                recovery_steps=["Approve Interface A first."],
            )

        # 1. Size check
        if len(file_bytes) > self.MAX_FILE_SIZE:
            raise InvalidFileUploadError(
                f"File size ({len(file_bytes)} bytes) exceeds the 10MB limit."
            )

        # 2. Path traversal sanitization
        raw_filename = os.path.basename(filename)
        ext = os.path.splitext(raw_filename)[1].lower()
        if not ext:
            ext = ".png"

        # 3. Format validation
        if (
            content_type.lower() not in self.ALLOWED_MIME_TYPES
            and ext not in self.ALLOWED_EXTENSIONS
        ):
            msg = f"Unsupported image format '{content_type}'. Allowed: PNG, JPEG, WEBP."
            raise InvalidFileUploadError(msg)

        # 4. Corrupt image detection via Pillow
        try:
            image = Image.open(io.BytesIO(file_bytes))
            image.verify()
            image = Image.open(io.BytesIO(file_bytes))
            image.load()
        except Exception as exc:
            raise InvalidFileUploadError(f"Corrupt or unreadable image file: {str(exc)}")

        # 5. Safe file persistence in artifacts/uploads/
        upload_dir = os.path.join("artifacts", "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        clean_base = os.path.splitext(raw_filename)[0]
        clean_base = "".join(c for c in clean_base if c.isalnum() or c in ("_", "-"))
        safe_filename = (
            f"upload_{project_id}_{interface_id}_{clean_base}_{uuid.uuid4().hex[:8]}{ext}"
        )
        try:
            target_path = resolve_path_within(upload_dir, Path(upload_dir) / safe_filename)
        except ValueError:
            raise InvalidFileUploadError("Malicious filename or path traversal detected.")

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        artifact_ref = f"artifacts/uploads/{safe_filename}"
        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        target_interface.source_image_ref = artifact_ref
        target_interface.approved = False
        target_interface.approved_at = None
        if known_measurement_type is not None and known_measurement_value is not None:
            _apply_known_measurement(
                target_interface,
                known_measurement_type,
                float(known_measurement_value),
                known_measurement_unit,
            )

        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if interface_id == "interface_a":
            project.state = WorkflowState.INTERFACE_A_UPLOADED
        else:
            project.state = WorkflowState.INTERFACE_B_UPLOADED

        project.updated_at = current_iso_timestamp()
        self.repository.save(project)

        return UploadResponseData(
            artifact_ref=artifact_ref,
            original_filename=raw_filename,
            stored_filename=safe_filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
            uploaded_at=current_iso_timestamp(),
        )

    def get_interface_image_bytes(
        self,
        project_id: str,
        interface_id: str,
        project_token: Optional[str] = None,
    ) -> tuple[bytes, str]:
        """Read and return the bytes and content-type for a stored interface image.

        Returns:
            (file_bytes, content_type)

        Raises:
            MissingPrerequisiteError: If no image is uploaded.
            ExportArtifactNotFoundError: If the artifact file is missing from disk.
        """
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(f"Invalid interface ID '{interface_id}'.")

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )

        if not target_interface.source_image_ref:
            raise MissingPrerequisiteError(
                f"No image uploaded for {interface_id}.",
                recovery_steps=["Upload an image first."],
            )

        image_path = target_interface.source_image_ref
        if not os.path.exists(image_path):
            raise ExportArtifactNotFoundError(f"Image artifact '{image_path}' not found on disk.")

        ext = os.path.splitext(image_path)[1].lower()
        content_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        content_type = content_type_map.get(ext, "image/png")

        with open(image_path, "rb") as f:
            file_bytes = f.read()

        return file_bytes, content_type

    def get_interface_artifact_bytes(
        self,
        project_id: str,
        interface_id: str,
        artifact_type: str,  # 'cleaned_image', 'trace_svg', 'overlay_svg'
        project_token: Optional[str] = None,
    ) -> tuple[bytes, str]:
        """Read and return bytes and content-type for a stored interface tracing artifact."""
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(f"Invalid interface ID '{interface_id}'.")

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )

        artifact_ref = None
        if artifact_type in ("cleaned_image", "analysis_image"):
            artifact_ref = target_interface.analysis_image_ref or target_interface.cleaned_image_ref
            content_type = "image/png"
        elif artifact_type == "trace_svg":
            artifact_ref = target_interface.trace_svg_ref
            content_type = "image/svg+xml"
        elif artifact_type == "overlay_svg":
            artifact_ref = target_interface.overlay_svg_ref
            content_type = "image/svg+xml"
        else:
            raise MissingPrerequisiteError(f"Invalid artifact type '{artifact_type}'.")

        if not artifact_ref or not os.path.exists(artifact_ref):
            raise ExportArtifactNotFoundError(
                f"Artifact '{artifact_type}' not found for {interface_id}."
            )

        with open(artifact_ref, "rb") as f:
            file_bytes = f.read()

        return file_bytes, content_type

    def analyze_interface_image(
        self,
        project_id: str,
        interface_id: str,
        provider: Optional[AnalysisProvider] = None,
        project_token: Optional[str] = None,
    ) -> AnalysisResult:
        """Run analysis on an uploaded interface image using configured provider interface."""
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        previous_interface = target_interface.model_copy(deep=True)

        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be analyzed.",
                recovery_steps=["Approve Interface A first."],
            )

        if not target_interface.source_image_ref:
            raise MissingPrerequisiteError(
                f"No image uploaded for {interface_id}. Upload an image before starting analysis."
            )

        image_bytes = b""
        filename = os.path.basename(target_interface.source_image_ref)
        if os.path.exists(target_interface.source_image_ref):
            with open(target_interface.source_image_ref, "rb") as f:
                image_bytes = f.read()

        active_provider = provider or get_analysis_provider("opencv")
        result = active_provider.analyze(image_bytes, filename)

        target_interface.profile_type = result.profile_type
        target_interface.profile_points = result.candidate_points
        target_interface.dimensions = result.candidate_dimensions
        # S10.3 & S10.4: Persist provider provenance, scale calibration, and traced contour data
        target_interface.analysis_provider_name = result.analysis_provider_name
        target_interface.scale_calibration = result.scale_calibration
        target_interface.cleaned_image_ref = result.cleaned_image_ref
        target_interface.analysis_image_ref = result.analysis_image_ref or result.cleaned_image_ref
        target_interface.analysis_image_width = result.analysis_image_width
        target_interface.analysis_image_height = result.analysis_image_height
        target_interface.trace_svg_ref = result.trace_svg_ref
        target_interface.overlay_svg_ref = result.overlay_svg_ref
        target_interface.raw_outer_point_count = result.raw_outer_point_count
        target_interface.simplified_outer_point_count = result.simplified_outer_point_count
        target_interface.inner_contour_count = result.inner_contour_count
        if result.traced_outer_contour is not None:
            target_interface.traced_outer_contour = result.traced_outer_contour
            target_interface.traced_hole_contours = result.traced_hole_contours
        else:
            primitive_contour = primitive_boundary_contour(
                result.profile_type, result.candidate_dimensions, result.candidate_points
            )
            target_interface.traced_outer_contour = primitive_contour
            target_interface.traced_hole_contours = []

        _merge_upload_measurement_after_analysis(target_interface, previous_interface)
        _apply_authoritative_shape_resolution(target_interface)
        result.trace_profile_type = target_interface.trace_profile_type
        result.resolved_profile_type = target_interface.resolved_profile_type
        result.resolution_status = target_interface.resolution_status
        result.resolution_confidence = target_interface.resolution_confidence
        result.resolution_reason = target_interface.resolution_reason
        result.resolved_dimensions = target_interface.resolved_dimensions
        result.calibration_boundary = target_interface.calibration_boundary
        result.profile_type = target_interface.profile_type
        result.candidate_dimensions = target_interface.dimensions

        is_valid, errors, warnings = validate_interface_profile(target_interface)
        target_interface.validation = ProfileValidation(
            is_closed=is_valid,
            self_intersects=False,
            warnings=errors + warnings + result.warnings,
        )
        target_interface.approved = False
        target_interface.approved_at = None

        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if interface_id == "interface_a":
            project.state = WorkflowState.INTERFACE_A_REVIEW_REQUIRED
        else:
            project.state = WorkflowState.INTERFACE_B_REVIEW_REQUIRED

        project.updated_at = current_iso_timestamp()
        self.repository.save(project)

        return result

    def patch_interface(
        self,
        project_id: str,
        interface_id: str,
        patch: InterfacePatchRequest,
        project_token: Optional[str] = None,
    ) -> Project:
        """Edit interface properties, run validation, increment revision, and mark model stale."""
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )

        original_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        original_geometry_fingerprint = _profile_geometry_fingerprint(original_interface)
        original_measurement_fingerprint = _measurement_fingerprint(original_interface)
        target_interface = original_interface.model_copy(deep=True)
        fit_mode_only_update = (
            patch.fit_mode is not None
            and patch.source_image_ref is None
            and patch.profile_type is None
            and patch.is_complex is None
            and patch.complex_reason is None
            and patch.profile_points is None
            and patch.center is None
            and patch.dimensions is None
            and patch.validation is None
            and patch.traced_outer_contour is None
            and patch.traced_hole_contours is None
            and patch.scale_calibration is None
            and patch.verification_status is None
            and patch.primitive_fallback_active is None
            and patch.primitive_fallback_label is None
            and patch.primitive_promotion_confirmed is None
            and patch.primitive_detection_confidence is None
            and patch.primitive_detection_reason is None
            and patch.approved is None
        )

        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be modified.",
                recovery_steps=["Approve Interface A first."],
            )

        if patch.approved is True:
            raise InvalidInterfaceApprovalError(
                "Interface approval must use the approval endpoint so backend validation "
                "cannot be bypassed.",
                recovery_steps=[
                    "Call POST /interfaces/{interface_id}/approve after validation passes."
                ],
            )

        if patch.source_image_ref is not None:
            target_interface.source_image_ref = patch.source_image_ref
        if patch.profile_type is not None:
            target_interface.profile_type = patch.profile_type
        if patch.is_complex is not None:
            target_interface.is_complex = patch.is_complex
        if patch.complex_reason is not None:
            target_interface.complex_reason = patch.complex_reason
        if patch.profile_points is not None:
            target_interface.profile_points = patch.profile_points
        if patch.center is not None:
            target_interface.center = patch.center
        if patch.dimensions is not None:
            from app.services.geometry_editing import apply_dimension_edits_to_geometry

            _, edit_warnings = apply_dimension_edits_to_geometry(target_interface, patch.dimensions)
            # Regenerate SVG artifacts if traced profile geometry changed
            if (
                target_interface.traced_outer_contour is not None
                and target_interface.traced_outer_contour
                and (target_interface.analysis_image_ref or target_interface.cleaned_image_ref)
                and os.path.exists(
                    target_interface.analysis_image_ref or target_interface.cleaned_image_ref or ""
                )
            ):
                try:
                    analysis_ref = (
                        target_interface.analysis_image_ref or target_interface.cleaned_image_ref
                    )
                    if not analysis_ref:
                        raise FileNotFoundError("Analysis crop artifact is missing")
                    with open(analysis_ref, "rb") as f:
                        img_bytes = f.read()
                    from app.services.opencv_tracer import generate_svg_trace_and_overlay

                    trace_svg, overlay_svg, _ = generate_svg_trace_and_overlay(
                        target_interface.traced_outer_contour,
                        target_interface.traced_hole_contours or [],
                        img_bytes,
                        img_bytes,
                        target_interface.analysis_image_width or 400,
                        target_interface.analysis_image_height or 400,
                    )
                    if target_interface.trace_svg_ref:
                        with open(target_interface.trace_svg_ref, "w", encoding="utf-8") as f:
                            f.write(trace_svg)
                    if target_interface.overlay_svg_ref:
                        with open(target_interface.overlay_svg_ref, "w", encoding="utf-8") as f:
                            f.write(overlay_svg)
                except Exception as exc:
                    logger.warning("Failed to regenerate SVG trace artifacts after edit: %s", exc)

        if patch.traced_outer_contour is not None:
            target_interface.traced_outer_contour = patch.traced_outer_contour
            target_interface.calibration_boundary = None
        if patch.traced_hole_contours is not None:
            target_interface.traced_hole_contours = patch.traced_hole_contours
        if patch.scale_calibration is not None:
            if (
                patch.scale_calibration.method == "two_point_trace"
                and patch.scale_calibration.confirmed
            ):
                raise InvalidInterfaceApprovalError(
                    "Confirmed two-point calibration must use the calibration endpoint.",
                    recovery_steps=["Use POST /interfaces/{interface_id}/scale/calibrate."],
                )
            target_interface.scale_calibration = patch.scale_calibration
            if target_interface.scale_calibration.confirmed:
                if (
                    target_interface.scale_calibration.scale_factor <= 0
                    and target_interface.scale_calibration.pixel_distance > 0
                ):
                    target_interface.scale_calibration.scale_factor = (
                        target_interface.scale_calibration.real_distance_mm
                        / target_interface.scale_calibration.pixel_distance
                    )
                if target_interface.traced_outer_contour is not None:
                    _update_derived_dimensions_from_scale(
                        target_interface, target_interface.scale_calibration.scale_factor
                    )
                else:
                    set_calibrated_primitive_dimensions(
                        target_interface, target_interface.scale_calibration.scale_factor
                    )
        if patch.verification_status is not None:
            target_interface.verification_status = patch.verification_status
        if patch.primitive_fallback_active is not None:
            target_interface.primitive_fallback_active = patch.primitive_fallback_active
        if patch.primitive_fallback_label is not None:
            target_interface.primitive_fallback_label = patch.primitive_fallback_label
        if patch.primitive_promotion_confirmed is not None:
            target_interface.primitive_promotion_confirmed = patch.primitive_promotion_confirmed
        if patch.primitive_detection_confidence is not None:
            target_interface.primitive_detection_confidence = patch.primitive_detection_confidence
        if patch.primitive_detection_reason is not None:
            target_interface.primitive_detection_reason = patch.primitive_detection_reason
        if patch.fit_mode is not None:
            target_interface.fit_mode = patch.fit_mode

        # Deprecated primitive-promotion fields are ignored for live traced projects.
        _apply_authoritative_shape_resolution(target_interface)

        # Run structural validation
        is_valid, errors, warnings = validate_interface_profile(target_interface)
        if patch.validation is not None:
            target_interface.validation = patch.validation
            target_interface.validation.warnings = list(
                dict.fromkeys(errors + warnings + patch.validation.warnings)
            )
        else:
            target_interface.validation = ProfileValidation(
                is_closed=is_valid,
                self_intersects=False,
                warnings=errors + warnings,
            )

        geometry_changed = (
            _profile_geometry_fingerprint(target_interface) != original_geometry_fingerprint
        )
        measurement_changed = (
            _measurement_fingerprint(target_interface) != original_measurement_fingerprint
        )
        explicit_scale_confirmation = (
            patch.scale_calibration is not None and patch.scale_calibration.confirmed
        )
        promotion_confirmation_update = patch.primitive_promotion_confirmed is True
        if (
            (geometry_changed or patch.dimensions is not None or measurement_changed)
            and target_interface.scale_calibration
            and not explicit_scale_confirmation
            and not promotion_confirmation_update
        ):
            target_interface.scale_calibration.confirmed = False

        severe_update_errors = [
            err
            for err in errors
            if any(
                marker in err.lower()
                for marker in (
                    "contour",
                    "intersects",
                    "complexity",
                    "non-finite",
                    "unresolved",
                    "conflict",
                )
            )
        ]
        if original_interface.approved and severe_update_errors:
            raise InvalidInterfaceApprovalError(
                "Invalid update rejected; last approved profile was preserved "
                f"({severe_update_errors[0]}).",
                recovery_steps=["Correct the profile locally, then submit a valid update."],
            )

        if patch.approved is False:
            target_interface.approved = False
            target_interface.approved_at = None

        # Upstream modification rule: clears approval and increments schema revision
        if patch.approved is None and not fit_mode_only_update:
            target_interface.approved = False
            target_interface.approved_at = None

        if interface_id == "interface_a":
            project.interface_a = target_interface
        else:
            project.interface_b = target_interface

        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if interface_id == "interface_a":
            if not target_interface.approved:
                project.state = WorkflowState.INTERFACE_A_REVIEW_REQUIRED
        else:
            if not target_interface.approved:
                project.state = WorkflowState.INTERFACE_B_REVIEW_REQUIRED

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def snap_scale_point(
        self,
        project_id: str,
        interface_id: str,
        point: Point2D,
        project_token: Optional[str] = None,
    ) -> ScaleSnapResponse:
        """Snap a trace-space point to the nearest valid traced segment."""
        project = self._verify_project_and_token(project_id, project_token)
        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )
        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be modified.",
                recovery_steps=["Approve Interface A first."],
            )
        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        if target_interface.traced_outer_contour is None:
            raise InvalidInterfaceApprovalError(
                "Two-point scale calibration requires traced profile geometry.",
                recovery_steps=["Run trace analysis before calibrating scale."],
            )
        return _snap_point_to_trace(target_interface, point)

    def calibrate_interface_scale(
        self,
        project_id: str,
        interface_id: str,
        req: TwoPointScaleCalibrationRequest,
        project_token: Optional[str] = None,
    ) -> Project:
        """Persist two-point trace calibration and confirm uniform scale only when requested."""
        project = self._verify_project_and_token(project_id, project_token)
        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )
        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be modified.",
                recovery_steps=["Approve Interface A first."],
            )

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        ).model_copy(deep=True)
        if target_interface.traced_outer_contour is None:
            raise InvalidInterfaceApprovalError(
                "Two-point scale calibration requires traced profile geometry.",
                recovery_steps=["Run trace analysis before calibrating scale."],
            )
        if not math.isfinite(req.real_distance_mm) or req.real_distance_mm <= 0:
            raise InvalidInterfaceApprovalError(
                "Real calibration distance must be a positive millimetre value.",
                recovery_steps=["Enter the measured real-world distance in millimetres."],
            )

        point_a = _canonical_boundary_node(target_interface, req.point_a)
        point_b = _canonical_boundary_node(target_interface, req.point_b)
        pixel_distance = _distance(point_a, point_b)
        if pixel_distance < 1.0:
            raise InvalidInterfaceApprovalError(
                "Calibration points are identical or too close together to determine scale.",
                recovery_steps=["Select two separated points on the traced contour."],
            )
        scale_factor = req.real_distance_mm / pixel_distance
        if not math.isfinite(scale_factor) or scale_factor <= 0:
            raise InvalidInterfaceApprovalError(
                "Calculated scale factor is invalid.",
                recovery_steps=["Check the selected points and real-world distance."],
            )

        target_interface.scale_calibration = ScaleCalibration(
            source="user_calibration",
            method="two_point_trace",
            reference_dimension="two_point_distance",
            point_a=point_a,
            point_b=point_b,
            pixel_distance=pixel_distance,
            real_distance_mm=req.real_distance_mm,
            scale_factor=scale_factor,
            confidence=1.0,
            confirmed=req.confirmed,
        )
        if req.confirmed:
            if target_interface.traced_outer_contour is not None:
                _update_derived_dimensions_from_scale(target_interface, scale_factor)
            else:
                set_calibrated_primitive_dimensions(target_interface, scale_factor)
            _apply_authoritative_shape_resolution(target_interface)

        target_interface.approved = False
        target_interface.approved_at = None
        if interface_id == "interface_a":
            project.interface_a = target_interface
            project.state = WorkflowState.INTERFACE_A_REVIEW_REQUIRED
        else:
            project.interface_b = target_interface
            project.state = WorkflowState.INTERFACE_B_REVIEW_REQUIRED

        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def reset_interface_scale_calibration(
        self,
        project_id: str,
        interface_id: str,
        project_token: Optional[str] = None,
    ) -> Project:
        """Clear saved calibration and invalidate profile approval."""
        project = self._verify_project_and_token(project_id, project_token)
        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )
        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        target_interface.scale_calibration = None
        target_interface.approved = False
        target_interface.approved_at = None
        if interface_id == "interface_a":
            project.interface_a = target_interface
            project.state = WorkflowState.INTERFACE_A_REVIEW_REQUIRED
        else:
            project.interface_b = target_interface
            project.state = WorkflowState.INTERFACE_B_REVIEW_REQUIRED
        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def approve_interface(
        self, project_id: str, interface_id: str, project_token: Optional[str] = None
    ) -> Project:
        """Approve interface.

        Enforces Interface B prerequisite, scale confirmation, and structural validation.
        """
        project = self._verify_project_and_token(project_id, project_token)

        if interface_id not in ("interface_a", "interface_b"):
            raise MissingPrerequisiteError(
                f"Invalid interface ID '{interface_id}'. Must be 'interface_a' or 'interface_b'."
            )

        if interface_id == "interface_b" and not project.interface_a.approved:
            raise InvalidInterfaceApprovalError(
                "Interface A must be approved before Interface B can be approved."
            )

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )
        promotion_changed = _apply_authoritative_shape_resolution(target_interface)
        if promotion_changed:
            project.current_schema_revision += 1
            self._mark_current_model_stale_if_exists(project)
        if (
            target_interface.traced_outer_contour is not None
            and target_interface.scale_calibration is None
        ):
            raise InvalidInterfaceApprovalError(
                "Cannot approve interface: Scale calibration must be confirmed.",
                recovery_steps=["Select two trace points and confirm the real-world distance."],
            )

        if (
            target_interface.scale_calibration is not None
            and not target_interface.scale_calibration.confirmed
        ):
            raise InvalidInterfaceApprovalError(
                "Cannot approve interface: Scale calibration must be confirmed.",
                recovery_steps=["Confirm the scale calibration in the review panel."],
            )

        if target_interface.traced_outer_contour is not None and (
            target_interface.traced_outer_contour is None
            or len(target_interface.traced_outer_contour.points) < 4
        ):
            raise InvalidInterfaceApprovalError(
                "Cannot approve interface: missing traced profile data.",
                recovery_steps=["Re-run analysis or upload a cleaner interface image."],
            )

        is_valid, errors, warnings = validate_interface_profile(target_interface)
        if not is_valid or errors:
            raise InvalidInterfaceApprovalError(
                f"Cannot approve {interface_id}: profile has structural validation errors "
                f"({errors[0]})."
            )
        now = current_iso_timestamp()
        if interface_id == "interface_a":
            project.interface_a.approved = True
            project.interface_a.approved_at = now
            if project.interface_b.approved:
                project.state = WorkflowState.INTERFACES_APPROVED
            else:
                project.state = WorkflowState.INTERFACE_A_APPROVED
        else:
            project.interface_b.approved = True
            project.interface_b.approved_at = now
            project.state = WorkflowState.INTERFACES_APPROVED

        project.updated_at = now
        return self.repository.save(project)

    def validate_connection_config(
        self,
        project_id: str,
        connection: Optional[Connection] = None,
        manufacturing: Optional[Manufacturing] = None,
        project_token: Optional[str] = None,
    ) -> ConnectionValidationResult:
        """Validate connection and manufacturing settings against approved interfaces."""
        project = self._verify_project_and_token(project_id, project_token)
        target_conn = connection or project.connection
        target_mfg = manufacturing or project.manufacturing
        return validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, target_conn, target_mfg
        )

    def preview_loft_plan(
        self,
        project_id: str,
        connection: Connection,
        manufacturing: Manufacturing,
        project_token: Optional[str] = None,
    ) -> Optional[LoftPlan]:
        """Build the authoritative candidate plan for the unsaved Step 3 preview."""
        project = self._verify_project_and_token(project_id, project_token)
        if not (project.interface_a.approved and project.interface_b.approved):
            return None
        candidate = project.model_copy(deep=True)
        candidate.connection = connection
        candidate.manufacturing = manufacturing
        candidate.loft_plan = None
        return ensure_loft_plan(candidate)
    def update_connection(
        self, project_id: str, req: ConnectionUpdateRequest, project_token: Optional[str] = None
    ) -> Project:
        """Update connection parameters. Enforces prerequisite approval and geometric rules."""
        project = self._verify_project_and_token(project_id, project_token)

        if not (project.interface_a.approved and project.interface_b.approved):
            msg = "Both Interface A and Interface B must be approved before connection config."
            raise MissingPrerequisiteError(msg)

        candidate_conn = Connection(
            mode=req.mode,
            length_mm=req.length_mm,
            offset_x_mm=req.offset_x_mm,
            offset_y_mm=req.offset_y_mm,
            angle_deg=req.angle_deg,
            extension_a_mm=getattr(req, "extension_a_mm", 0.0),
            extension_b_mm=getattr(req, "extension_b_mm", 0.0),
        )

        validation = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, candidate_conn, project.manufacturing
        )

        if not validation.is_valid or validation.blocking_errors:
            err = validation.blocking_errors[0]
            raise InvalidConnectionConfigError(
                message=err.message,
                error_id=err.id,
                details={"blocking_errors": [b.model_dump() for b in validation.blocking_errors]},
                recovery_steps=err.recovery_steps,
            )

        project.connection = candidate_conn
        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if project.current_model_revision is not None:
            project.state = WorkflowState.MODEL_STALE
        else:
            project.state = WorkflowState.CONNECTION_CONFIGURED

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def update_manufacturing(
        self, project_id: str, req: ManufacturingUpdateRequest, project_token: Optional[str] = None
    ) -> Project:
        """Update manufacturing settings. Enforces validation rules."""
        project = self._verify_project_and_token(project_id, project_token)

        candidate_mfg = Manufacturing(
            process=req.process,
            material=req.material,
            wall_thickness_mm=req.wall_thickness_mm,
            clearance_a_mm=req.clearance_a_mm,
            clearance_b_mm=req.clearance_b_mm,
        )

        validation = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, project.connection, candidate_mfg
        )

        if not validation.is_valid or validation.blocking_errors:
            err = validation.blocking_errors[0]
            raise InvalidConnectionConfigError(
                message=err.message,
                error_id=err.id,
                details={"blocking_errors": [b.model_dump() for b in validation.blocking_errors]},
                recovery_steps=err.recovery_steps,
            )

        project.manufacturing = candidate_mfg
        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if project.current_model_revision is not None:
            project.state = WorkflowState.MODEL_STALE

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def update_connection_and_manufacturing(
        self,
        project_id: str,
        connection_req: ConnectionUpdateRequest,
        manufacturing_req: ManufacturingUpdateRequest,
        project_token: Optional[str] = None,
    ) -> Project:
        """Atomically update both connection and manufacturing parameters."""
        project = self._verify_project_and_token(project_id, project_token)

        if not (project.interface_a.approved and project.interface_b.approved):
            msg = "Both Interface A and Interface B must be approved before connection config."
            raise MissingPrerequisiteError(msg)

        candidate_conn = Connection(
            mode=connection_req.mode,
            length_mm=connection_req.length_mm,
            offset_x_mm=connection_req.offset_x_mm,
            offset_y_mm=connection_req.offset_y_mm,
            angle_deg=connection_req.angle_deg,
            extension_a_mm=getattr(connection_req, "extension_a_mm", 0.0),
            extension_b_mm=getattr(connection_req, "extension_b_mm", 0.0),
        )
        candidate_mfg = Manufacturing(
            process=manufacturing_req.process,
            material=manufacturing_req.material,
            wall_thickness_mm=(manufacturing_req.wall_thickness_mm if hasattr(manufacturing_req, "wall_thickness_mm") else manufacturing_req.wallThicknessMm),
            clearance_a_mm=manufacturing_req.clearance_a_mm,
            clearance_b_mm=manufacturing_req.clearance_b_mm,
        )

        validation = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, candidate_conn, candidate_mfg
        )

        if not validation.is_valid or validation.blocking_errors:
            err = validation.blocking_errors[0]
            raise InvalidConnectionConfigError(
                message=err.message,
                error_id=err.id,
                details={"blocking_errors": [b.model_dump() for b in validation.blocking_errors]},
                recovery_steps=err.recovery_steps,
            )

        project.connection = candidate_conn
        project.manufacturing = candidate_mfg
        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if project.current_model_revision is not None:
            project.state = WorkflowState.MODEL_STALE
        else:
            project.state = WorkflowState.CONNECTION_CONFIGURED

        # Persist the exact plan that Step 3 preview received.
        project.loft_plan = ensure_loft_plan(project)
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def start_model_generation(
        self, project_id: str, project_token: Optional[str] = None
    ) -> Project:
        """Start 3D model generation. Enforces Invariant #3: Connection must be configured."""
        project = self._verify_project_and_token(project_id, project_token)

        if not (project.interface_a.approved and project.interface_b.approved):
            raise MissingPrerequisiteError(
                "Cannot start model generation before both interfaces are approved."
            )

        if project.connection.length_mm <= 0 or project.state in (
            WorkflowState.NEW,
            WorkflowState.INTERFACE_A_UPLOADED,
            WorkflowState.INTERFACE_A_REVIEW_REQUIRED,
            WorkflowState.INTERFACE_A_APPROVED,
            WorkflowState.INTERFACE_B_UPLOADED,
            WorkflowState.INTERFACE_B_REVIEW_REQUIRED,
            WorkflowState.INTERFACES_APPROVED,
        ):
            raise MissingPrerequisiteError(
                "Cannot start model generation before connection configuration is complete."
            )

        calibration_validation = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, project.connection, project.manufacturing
        )
        if calibration_validation.blocking_errors:
            error = calibration_validation.blocking_errors[0]
            raise InvalidConnectionConfigError(
                message=error.message,
                error_id=error.id,
                details={
                    "blocking_errors": [
                        item.model_dump() for item in calibration_validation.blocking_errors
                    ]
                },
                recovery_steps=error.recovery_steps,
            )

        next_model_rev = len(project.model_revisions) + 1
        now = current_iso_timestamp()
        new_rev = ModelRevision(
            model_revision=next_model_rev,
            schema_revision=project.current_schema_revision,
            status=ModelRevisionStatus.GENERATING,
            generated_at=now,
        )
        project.model_revisions.append(new_rev)
        project.state = WorkflowState.GENERATION_IN_PROGRESS
        project.updated_at = now
        return self.repository.save(project)

    def succeed_model_generation(
        self, project_id: str, req: ModelSucceedRequest, project_token: Optional[str] = None
    ) -> Project:
        """Mark model generation as successful. Enforces Invariant #8 & #9."""
        project = self._verify_project_and_token(project_id, project_token)

        target_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == req.model_revision:
                target_rev = rev
                break

        if not target_rev:
            raise MissingPrerequisiteError(f"Model revision '{req.model_revision}' not found.")

        # Supersede existing current model
        for rev in project.model_revisions:
            if rev.status == ModelRevisionStatus.CURRENT:
                rev.status = ModelRevisionStatus.SUPERSEDED

        now = current_iso_timestamp()
        target_rev.status = ModelRevisionStatus.CURRENT
        if req.kcl_artifact_ref:
            target_rev.kcl_artifact_ref = req.kcl_artifact_ref
        if req.preview_artifact_ref:
            target_rev.preview_artifact_ref = req.preview_artifact_ref
        if req.volume_cm3 is not None:
            target_rev.volume_cm3 = req.volume_cm3
        if req.zoo_model_id:
            target_rev.zoo_model_id = req.zoo_model_id
        if req.kcl_hash:
            target_rev.kcl_hash = req.kcl_hash
        if target_rev.kcl_artifact_ref and os.path.exists(target_rev.kcl_artifact_ref):
            with open(target_rev.kcl_artifact_ref, "rb") as kcl_file:
                kcl_bytes = kcl_file.read()
            if not validate_artifact_content("kcl", kcl_bytes):
                raise ExportArtifactNotFoundError(
                    "Model cannot become current with invalid KCL artifact."
                )
            target_rev.kcl_hash = __import__("hashlib").sha256(kcl_bytes).hexdigest()
        target_rev.warnings = req.warnings

        # Set current and last known good model revision
        project.current_model_revision = req.model_revision
        project.last_known_good_model_revision = req.model_revision
        project.state = WorkflowState.MODEL_CURRENT
        project.updated_at = now
        return self.repository.save(project)

    def fail_model_generation(
        self, project_id: str, req: ModelFailRequest, project_token: Optional[str] = None
    ) -> Project:
        """Mark model generation as failed (preserves last known good model)."""
        project = self._verify_project_and_token(project_id, project_token)

        target_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == req.model_revision:
                target_rev = rev
                break

        if target_rev:
            target_rev.status = ModelRevisionStatus.FAILED
            target_rev.warnings = req.warnings + [req.error_message]

        # Preserve last_known_good_model_revision!
        project.state = WorkflowState.GENERATION_FAILED
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def start_export(self, project_id: str, project_token: Optional[str] = None) -> Project:
        """Start export processing. Enforces Invariant #4: Current valid model required."""
        project = self._verify_project_and_token(project_id, project_token)

        if project.current_model_revision is None:
            raise StaleModelOperationError("Cannot start export without a current valid model.")

        current_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == project.current_model_revision:
                current_rev = rev
                break

        if not current_rev or current_rev.status != ModelRevisionStatus.CURRENT:
            raise StaleModelOperationError(
                "Cannot start export for a model that is stale, failed, or not current."
            )

        project.state = WorkflowState.EXPORT_IN_PROGRESS
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def complete_export(
        self, project_id: str, req: ExportCompleteRequest, project_token: Optional[str] = None
    ) -> Project:
        """Complete export processing."""
        project = self._verify_project_and_token(project_id, project_token)

        if project.current_model_revision is not None:
            for rev in project.model_revisions:
                if rev.model_revision == project.current_model_revision:
                    if req.stl_artifact_ref:
                        rev.exports.stl = req.stl_artifact_ref
                    if req.step_artifact_ref:
                        rev.exports.step = req.step_artifact_ref
                    if req.kcl_artifact_ref:
                        rev.exports.kcl = req.kcl_artifact_ref

        project.state = WorkflowState.EXPORT_READY
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    async def generate_exports(
        self,
        project_id: str,
        formats: Optional[list[str]] = None,
        project_token: Optional[str] = None,
        mock_scenario: Optional[str] = None,
        provider: Optional[ExportProvider] = None,
    ) -> ExportStatusResponse:
        """Generate CAD format exports (STL, STEP, KCL) for current valid model per S8."""
        project = self._verify_project_and_token(project_id, project_token)

        if project.current_model_revision is None:
            raise StaleModelOperationError(
                "Cannot export because current model revision is missing."
            )

        current_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == project.current_model_revision:
                current_rev = rev
                break

        if (
            not current_rev
            or current_rev.status != ModelRevisionStatus.CURRENT
            or project.state == WorkflowState.MODEL_STALE
        ):
            raise StaleModelOperationError(
                "Cannot start export for a model that is stale, failed, or not current."
            )

        requested_formats = [f.lower() for f in (formats or ["stl", "step", "kcl"])]

        # Exports must use the exact KCL artifact already attached to this revision.
        if not current_rev.kcl_artifact_ref or not os.path.exists(current_rev.kcl_artifact_ref):
            raise ExportArtifactNotFoundError(
                "Current revision KCL artifact is missing. Regenerate the model first."
            )
        with open(current_rev.kcl_artifact_ref, "rb") as kcl_file:
            kcl_bytes = kcl_file.read()
        if not validate_artifact_content("kcl", kcl_bytes):
            raise ExportArtifactNotFoundError(
                "Current revision KCL artifact failed parser validation."
            )

        import hashlib

        computed_kcl_hash = hashlib.sha256(kcl_bytes).hexdigest()
        if not current_rev.kcl_hash or current_rev.kcl_hash != computed_kcl_hash:
            raise ExportArtifactNotFoundError(
                "Current revision KCL artifact hash does not match lineage."
            )
        kcl_code = kcl_bytes.decode("utf-8")
        effective_kcl_hash = current_rev.kcl_hash
        current_rev.exports.kcl = current_rev.kcl_artifact_ref

        export_prov = provider or get_export_provider(
            project.provider_mode.value
            if hasattr(project.provider_mode, "value")
            else str(project.provider_mode)
        )
        zoo_model_id_val = current_rev.zoo_model_id
        if (
            not zoo_model_id_val
            and isinstance(export_prov, get_export_provider("mock").__class__)
            and (
                project.provider_mode.value
                if hasattr(project.provider_mode, "value")
                else str(project.provider_mode)
            )
            == "mock"
        ):
            zoo_model_id_val = f"mock_model_{project.project_id[:8]}"

        project.state = WorkflowState.EXPORT_IN_PROGRESS
        self.repository.save(project)

        format_details: dict[str, FormatExportDetail] = {}

        # Pre-populate existing ready exports
        for fmt in ("stl", "step", "kcl"):
            ref = getattr(current_rev.exports, fmt, None)
            if fmt == "kcl" and not ref:
                ref = current_rev.kcl_artifact_ref
            lineage_ok = fmt == "kcl" or (
                current_rev.kcl_hash
                and f"_rev{project.current_model_revision}_" in os.path.basename(ref or "")
                and current_rev.kcl_hash[:8] in os.path.basename(ref or "")
            )
            if ref and lineage_ok and os.path.exists(ref) and os.path.getsize(ref) > 0:
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=ExportFormatStatus.READY,
                    artifact_ref=ref,
                    filename=f"interfaceforge_adapter_rev{project.current_model_revision}.{fmt}",
                    size_bytes=os.path.getsize(ref),
                    zoo_model_id=zoo_model_id_val,
                    kcl_hash=effective_kcl_hash,
                    updated_at=current_iso_timestamp(),
                )

        any_success = False
        for fmt in requested_formats:
            if fmt not in ("stl", "step", "kcl"):
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=ExportFormatStatus.FAILED,
                    error_id="IF-EXPORT-002",
                    error_message=f"Unsupported export format '{fmt}'. Supported: stl, step, kcl.",
                    updated_at=current_iso_timestamp(),
                )
                continue

            res = await export_prov.export_format(
                project_id=project.project_id,
                model_revision=project.current_model_revision,
                format_name=fmt,
                kcl_code=kcl_code,
                kcl_artifact_ref=current_rev.kcl_artifact_ref,
                mock_scenario=mock_scenario,
                project=project,
                zoo_model_id=zoo_model_id_val,
                kcl_hash=effective_kcl_hash,
            )

            if res.success and res.artifact_ref and res.kcl_hash == effective_kcl_hash:
                any_success = True
                setattr(current_rev.exports, fmt, res.artifact_ref)
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=ExportFormatStatus.READY,
                    artifact_ref=res.artifact_ref,
                    filename=res.filename,
                    size_bytes=res.size_bytes,
                    zoo_model_id=res.zoo_model_id or zoo_model_id_val,
                    kcl_hash=res.kcl_hash or effective_kcl_hash,
                    updated_at=res.generated_at,
                )
            else:
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=(
                        ExportFormatStatus.UNAVAILABLE
                        if res.error_id == "IF-EXPORT-007"
                        else ExportFormatStatus.FAILED
                    ),
                    error_id=res.error_id or "IF-EXPORT-001",
                    error_message=res.error_message or f"Export generation failed for '{fmt}'.",
                    updated_at=current_iso_timestamp(),
                )

        if any_success or any(
            d.status == ExportFormatStatus.READY for d in format_details.values()
        ):
            project.state = WorkflowState.EXPORT_READY
        else:
            project.state = WorkflowState.MODEL_CURRENT

        project.updated_at = current_iso_timestamp()
        self.repository.save(project)

        return ExportStatusResponse(
            project_id=project.project_id,
            model_revision=project.current_model_revision,
            schema_revision=project.current_schema_revision,
            units="mm",
            model_status=current_rev.status.value,
            volume_cm3=current_rev.volume_cm3,
            formats=format_details,
        )

    def get_export_status(
        self, project_id: str, project_token: Optional[str] = None
    ) -> ExportStatusResponse:
        """Get export status for all formats for current model revision."""
        project = self._verify_project_and_token(project_id, project_token)

        if project.current_model_revision is None:
            raise StaleModelOperationError("Current model revision is missing.")

        current_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == project.current_model_revision:
                current_rev = rev
                break

        if not current_rev or current_rev.status != ModelRevisionStatus.CURRENT:
            raise StaleModelOperationError("Cannot query export status for stale or missing model.")

        format_details: dict[str, FormatExportDetail] = {}
        for fmt in ("stl", "step", "kcl"):
            ref = getattr(current_rev.exports, fmt, None)
            if fmt == "kcl" and not ref:
                ref = current_rev.kcl_artifact_ref
            lineage_ok = fmt == "kcl" or (
                current_rev.kcl_hash
                and f"_rev{project.current_model_revision}_" in os.path.basename(ref or "")
                and current_rev.kcl_hash[:8] in os.path.basename(ref or "")
            )
            artifact_valid = bool(ref and os.path.exists(ref) and os.path.getsize(ref) > 0)
            if artifact_valid and fmt == "kcl" and ref:
                with open(ref, "rb") as kcl_file:
                    kcl_bytes = kcl_file.read()
                artifact_valid = (
                    validate_artifact_content("kcl", kcl_bytes)
                    and current_rev.kcl_hash == __import__("hashlib").sha256(kcl_bytes).hexdigest()
                )
            if ref and lineage_ok and artifact_valid:
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=ExportFormatStatus.READY,
                    artifact_ref=ref,
                    filename=f"interfaceforge_adapter_rev{project.current_model_revision}.{fmt}",
                    size_bytes=os.path.getsize(ref),
                    zoo_model_id=current_rev.zoo_model_id,
                    kcl_hash=current_rev.kcl_hash,
                    updated_at=current_iso_timestamp(),
                )
            else:
                format_details[fmt] = FormatExportDetail(
                    format=fmt,
                    status=ExportFormatStatus.NOT_STARTED,
                    updated_at=current_iso_timestamp(),
                )

        return ExportStatusResponse(
            project_id=project.project_id,
            model_revision=project.current_model_revision,
            schema_revision=project.current_schema_revision,
            units="mm",
            model_status=current_rev.status.value,
            volume_cm3=current_rev.volume_cm3,
            formats=format_details,
        )

    def download_export_artifact(
        self, project_id: str, format_name: str, project_token: Optional[str] = None
    ) -> tuple[str, str, str]:
        """Validate ownership and format signature, returning safe download path and filename."""
        project = self._verify_project_and_token(project_id, project_token)
        fmt = format_name.lower()

        if fmt not in ("stl", "step", "kcl"):
            raise UnsupportedExportFormatError(fmt)

        if project.current_model_revision is None:
            raise StaleModelOperationError("Cannot download export for missing model revision.")

        current_rev = None
        for rev in project.model_revisions:
            if rev.model_revision == project.current_model_revision:
                current_rev = rev
                break

        if (
            not current_rev
            or current_rev.status != ModelRevisionStatus.CURRENT
            or project.state == WorkflowState.MODEL_STALE
        ):
            raise StaleModelOperationError(
                "Cannot download export for a model that is stale, failed, or not current."
            )

        ref = getattr(current_rev.exports, fmt, None)
        if fmt == "kcl" and not ref:
            ref = current_rev.kcl_artifact_ref

        lineage_ok = fmt == "kcl" or (
            current_rev.kcl_hash
            and f"_rev{project.current_model_revision}_" in os.path.basename(ref or "")
            and current_rev.kcl_hash[:8] in os.path.basename(ref or "")
        )
        if not ref or not lineage_ok or not os.path.exists(ref) or os.path.getsize(ref) == 0:
            raise ExportArtifactNotFoundError(
                f"Export artifact for '{fmt}' was not found or is empty. Generate export first."
            )

        with open(ref, "rb") as f:
            content = f.read()

        if not validate_artifact_content(fmt, content):
            raise ExportArtifactNotFoundError(
                f"Export artifact for '{fmt}' failed non-zero or format signature validation."
            )

        try:
            resolve_path_within("artifacts", ref)
        except ValueError:
            raise InvalidProjectTokenError()

        mime_types = {
            "stl": "application/sla",
            "step": "model/step",
            "kcl": "text/plain;charset=utf-8",
        }

        download_name = f"interfaceforge_adapter_rev{project.current_model_revision}.{fmt}"
        return ref, download_name, mime_types.get(fmt, "application/octet-stream")

    def read_current_kcl(
        self, project_id: str, project_token: Optional[str] = None
    ) -> dict[str, object]:
        """Return the exact validated KCL bytes attached to the current revision."""
        project = self._verify_project_and_token(project_id, project_token)
        if project.current_model_revision is None:
            raise StaleModelOperationError("Current model revision is missing.")
        current_rev = next(
            (
                rev
                for rev in project.model_revisions
                if rev.model_revision == project.current_model_revision
            ),
            None,
        )
        if not current_rev or current_rev.status != ModelRevisionStatus.CURRENT:
            raise StaleModelOperationError("Cannot read KCL for a stale or missing model.")
        ref = current_rev.kcl_artifact_ref or current_rev.exports.kcl
        if not ref or not os.path.exists(ref) or os.path.getsize(ref) == 0:
            raise ExportArtifactNotFoundError("Current revision KCL artifact is missing or empty.")
        with open(ref, "rb") as artifact_file:
            content = artifact_file.read()
        actual_hash = __import__("hashlib").sha256(content).hexdigest()
        if not current_rev.kcl_hash or actual_hash != current_rev.kcl_hash:
            raise ExportArtifactNotFoundError(
                "Current revision KCL artifact hash does not match lineage."
            )
        try:
            resolve_path_within("artifacts", ref)
        except ValueError:
            raise InvalidProjectTokenError()
        return {
            "text": content.decode("utf-8"),
            "artifact_ref": ref,
            "schema_revision": current_rev.schema_revision,
            "model_revision": current_rev.model_revision,
            "kcl_hash": actual_hash,
        }

    def validate_kcl_readiness(
        self, project_id: str, project_token: Optional[str] = None
    ) -> ConnectionValidationResult:
        """Validate KCL compilation readiness for a project."""
        project = self._verify_project_and_token(project_id, project_token)
        return validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, project.connection, project.manufacturing
        )

    def compile_kcl(self, project_id: str, project_token: Optional[str] = None) -> KCLCompileResult:
        """Compiles canonical project schema into deterministic KCL without calling Zoo.

        Enforces ADR-001, ADR-002, and saves artifact.
        Does NOT mark model status as CURRENT because Zoo has not executed it.
        """
        project = self._verify_project_and_token(project_id, project_token)
        result = compile_project_to_kcl(project)

        if result.success and result.artifact_ref:
            project.loft_plan = ensure_loft_plan(project)
            next_model_rev = len(project.model_revisions) + 1
            now = current_iso_timestamp()
            new_rev = ModelRevision(
                model_revision=next_model_rev,
                schema_revision=project.current_schema_revision,
                status=ModelRevisionStatus.DRAFT,  # NOT CURRENT! Zoo has not executed it.
                kcl_artifact_ref=result.artifact_ref,
                warnings=[w.message for w in result.warnings],
                generated_at=now,
            )
            project.model_revisions.append(new_rev)
            project.updated_at = now
            self.repository.save(project)

        return result
