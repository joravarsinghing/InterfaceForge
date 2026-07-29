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
from app.services.profile_geometry import (
    classify_primitive_candidate,
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
    bbox = _trace_bbox(interface)
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


def _snap_point_to_trace(interface: Interface, point: Point2D) -> ScaleSnapResponse:
    _ensure_point_within_trace_bounds(interface, point)
    segments = _trace_geometry_segments(interface)
    if not segments:
        raise InvalidInterfaceApprovalError(
            "Cannot calibrate scale: no valid trace segments are available.",
            recovery_steps=["Re-run analysis or upload a cleaner interface image."],
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
    return ScaleSnapResponse(point=best[1], distance_px=best[0], feature_id=best[2])


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

        return project

    def _mark_current_model_stale_if_exists(self, project: Project) -> None:
        """Mark current model revision as stale if it exists."""
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
        analysis_provider = (
            "gemini" if effective == ProviderMode.LIVE and settings.gemini_api_key else "mock"
        )
        if effective == ProviderMode.LIVE:
            message = (
                "Live Zoo providers are active for future generation, export, and Agent requests."
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

        active_provider = provider or get_analysis_provider()
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
            primitive_candidate = (
                None
                if result.is_complex
                else classify_primitive_candidate(result.traced_outer_contour.points)
            )
            if primitive_candidate is not None:
                target_interface.profile_type = primitive_candidate.profile_type
                target_interface.verification_status = "primitive_detected_pending_confirmation"
                target_interface.primitive_fallback_active = True
                target_interface.primitive_promotion_confirmed = False
                target_interface.primitive_detection_confidence = primitive_candidate.confidence
                target_interface.primitive_detection_reason = primitive_candidate.reason
                target_interface.primitive_fallback_label = (
                    f"Detected {primitive_candidate.profile_type.value} primitive "
                    f"with confidence {primitive_candidate.confidence:.2f}"
                )
                target_interface.generation_unsupported = False
                target_interface.generation_unsupported_reason = None
            else:
                target_interface.profile_type = ProfileType.TRACED_CLOSED
                target_interface.primitive_fallback_active = False
                target_interface.primitive_promotion_confirmed = False
                target_interface.primitive_detection_confidence = None
                target_interface.primitive_detection_reason = None
                target_interface.verification_status = "opencv_traced_pending_review"
                target_interface.generation_unsupported = True
                target_interface.generation_unsupported_reason = (
                    "Adapter generation for arbitrary traced profiles is not yet enabled. "
                    "Profile is captured and stored for review only."
                )
        else:
            target_interface.traced_outer_contour = None
            target_interface.traced_hole_contours = []
            target_interface.verification_status = "pending_review"
            target_interface.generation_unsupported = False
            target_interface.generation_unsupported_reason = None

        _merge_upload_measurement_after_analysis(target_interface, previous_interface)

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
                target_interface.profile_type == ProfileType.TRACED_CLOSED
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
        if (
            (geometry_changed or (patch.dimensions is not None and measurement_changed))
            and target_interface.scale_calibration
            and not explicit_scale_confirmation
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

        snap_a = _snap_point_to_trace(target_interface, req.point_a)
        snap_b = _snap_point_to_trace(target_interface, req.point_b)
        pixel_distance = _distance(snap_a.point, snap_b.point)
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
            point_a=snap_a.point,
            point_b=snap_b.point,
            pixel_distance=pixel_distance,
            real_distance_mm=req.real_distance_mm,
            scale_factor=scale_factor,
            confidence=1.0,
            confirmed=req.confirmed,
        )
        if req.confirmed:
            if target_interface.profile_type == ProfileType.TRACED_CLOSED:
                _update_derived_dimensions_from_scale(target_interface, scale_factor)
            else:
                set_calibrated_primitive_dimensions(target_interface, scale_factor)

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

        if (
            target_interface.profile_type == ProfileType.TRACED_CLOSED
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

        if target_interface.profile_type == ProfileType.TRACED_CLOSED and (
            target_interface.traced_outer_contour is None
            or len(target_interface.traced_outer_contour.points) < 4
        ):
            raise InvalidInterfaceApprovalError(
                "Cannot approve interface: missing traced profile data.",
                recovery_steps=["Re-run analysis or upload a cleaner interface image."],
            )

        if (
            target_interface.primitive_fallback_active
            and not target_interface.primitive_promotion_confirmed
        ):
            raise InvalidInterfaceApprovalError(
                "Cannot approve interface: detected primitive promotion must be confirmed.",
                recovery_steps=["Review the detected primitive and confirm it before approval."],
            )

        if target_interface.profile_type == ProfileType.ROUNDED_RECTANGLE:
            radius = next(
                (dim for dim in target_interface.dimensions if dim.id == "corner_radius"),
                None,
            )
            if radius is not None and (
                radius.consistency_state == "requires_confirmation"
                or (
                    radius.provenance != DimensionProvenance.USER_ENTERED
                    and radius.confidence < 0.75
                )
            ):
                raise InvalidInterfaceApprovalError(
                    "Cannot approve interface: inferred corner radius must be confirmed.",
                    recovery_steps=["Confirm or edit the corner radius before approval."],
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
        )
        candidate_mfg = Manufacturing(
            process=manufacturing_req.process,
            material=manufacturing_req.material,
            wall_thickness_mm=manufacturing_req.wall_thickness_mm,
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
        target_rev.kcl_artifact_ref = req.kcl_artifact_ref
        target_rev.preview_artifact_ref = req.preview_artifact_ref
        target_rev.volume_cm3 = req.volume_cm3
        target_rev.zoo_model_id = req.zoo_model_id
        target_rev.kcl_hash = req.kcl_hash
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

        # Extract KCL code for export compilation
        kcl_code = ""
        if current_rev.kcl_artifact_ref and os.path.exists(current_rev.kcl_artifact_ref):
            with open(current_rev.kcl_artifact_ref, "r", encoding="utf-8") as f:
                kcl_code = f.read()
        else:
            compile_res = compile_project_to_kcl(project)
            kcl_code = compile_res.kcl_code or ""

        import hashlib

        computed_kcl_hash = (
            hashlib.sha256(kcl_code.encode("utf-8")).hexdigest() if kcl_code else "kcl_empty"
        )
        effective_kcl_hash = current_rev.kcl_hash or computed_kcl_hash
        current_rev.kcl_hash = effective_kcl_hash

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
            if ref and os.path.exists(ref) and os.path.getsize(ref) > 0:
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

            if res.success and res.artifact_ref:
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
                    status=ExportFormatStatus.FAILED,
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
            if ref and os.path.exists(ref) and os.path.getsize(ref) > 0:
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

        if not ref or not os.path.exists(ref) or os.path.getsize(ref) == 0:
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
