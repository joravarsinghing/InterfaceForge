"""Project service layer managing domain workflow state transitions and schema invariants."""

import io
import logging
import os
import secrets
import uuid
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
from app.models.schema import (
    AnalysisResult,
    Connection,
    ConnectionUpdateRequest,
    ConnectionValidationResult,
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
    ProfileType,
    ProfileValidation,
    Project,
    ProjectPatchRequest,
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
from app.services.profile_validation import validate_interface_profile

logger = logging.getLogger(__name__)


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

    def create_project(self) -> Project:
        """Create a new project with initialized canonical schema and unguessable token."""
        project_id = str(uuid.uuid4())
        project_token = f"tok_{secrets.token_urlsafe(24)}"
        now = current_iso_timestamp()

        project = Project(
            project_id=project_id,
            project_token=project_token,
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
        target_path = os.path.abspath(os.path.join(upload_dir, safe_filename))

        abs_upload_dir = os.path.abspath(upload_dir)
        if not target_path.startswith(abs_upload_dir):
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
        if artifact_type == "cleaned_image":
            artifact_ref = target_interface.cleaned_image_ref
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
        target_interface.trace_svg_ref = result.trace_svg_ref
        target_interface.overlay_svg_ref = result.overlay_svg_ref
        target_interface.raw_outer_point_count = result.raw_outer_point_count
        target_interface.simplified_outer_point_count = result.simplified_outer_point_count
        target_interface.inner_contour_count = result.inner_contour_count
        if result.traced_outer_contour is not None:
            target_interface.traced_outer_contour = result.traced_outer_contour
            target_interface.traced_hole_contours = result.traced_hole_contours
            target_interface.verification_status = "opencv_traced_pending_review"
            # Mark traced profiles as generation_unsupported (KCL adapter not yet implemented)
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

        target_interface = (
            project.interface_a if interface_id == "interface_a" else project.interface_b
        )

        if interface_id == "interface_b" and not project.interface_a.approved:
            raise MissingPrerequisiteError(
                "Interface A must be approved before Interface B can be modified.",
                recovery_steps=["Approve Interface A first."],
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
                and target_interface.source_image_ref
                and os.path.exists(target_interface.source_image_ref)
            ):
                try:
                    with open(target_interface.source_image_ref, "rb") as f:
                        img_bytes = f.read()
                    from app.services.opencv_tracer import generate_svg_trace_and_overlay

                    trace_svg, overlay_svg, _ = generate_svg_trace_and_overlay(
                        target_interface.traced_outer_contour,
                        target_interface.traced_hole_contours or [],
                        img_bytes,
                        img_bytes,
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
            target_interface.scale_calibration = patch.scale_calibration
        if patch.verification_status is not None:
            target_interface.verification_status = patch.verification_status
        if patch.primitive_fallback_active is not None:
            target_interface.primitive_fallback_active = patch.primitive_fallback_active
        if patch.primitive_fallback_label is not None:
            target_interface.primitive_fallback_label = patch.primitive_fallback_label

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

        # Allow setting approved directly in patch if requested
        if patch.approved is not None:
            target_interface.approved = patch.approved
            if patch.approved:
                target_interface.approved_at = current_iso_timestamp()

        # Upstream modification rule: clears approval (unless explicitly setting approved)
        # and increments schema revision
        if patch.approved is None:
            target_interface.approved = False
            target_interface.approved_at = None
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

        # Scale confirmation check for traced profiles
        if target_interface.profile_type == ProfileType.TRACED_CLOSED:
            if (
                target_interface.scale_calibration is None
                or not target_interface.scale_calibration.confirmed
            ):
                raise InvalidInterfaceApprovalError(
                    "Cannot approve interface: Scale calibration must be confirmed.",
                    recovery_steps=["Confirm the scale calibration in the review panel."],
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

        export_prov = provider or get_export_provider()
        zoo_model_id_val = current_rev.zoo_model_id
        if (
            not zoo_model_id_val
            and isinstance(export_prov, get_export_provider().__class__)
            and settings.get_effective_export_provider() == "mock"
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

        # Path traversal check
        abs_artifacts_dir = os.path.abspath("artifacts")
        abs_ref = os.path.abspath(ref)
        if not abs_ref.startswith(abs_artifacts_dir):
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
