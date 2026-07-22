"""Project service layer managing domain workflow state transitions and schema invariants."""

import io
import os
import secrets
import uuid
from typing import Optional

from PIL import Image

from app.core.exceptions import (
    InvalidConnectionConfigError,
    InvalidFileUploadError,
    InvalidInterfaceApprovalError,
    InvalidProjectTokenError,
    MissingPrerequisiteError,
    ProjectNotFoundError,
    SchemaVersionMismatchError,
    StaleModelOperationError,
)
from app.models.schema import (
    AnalysisResult,
    Connection,
    ConnectionUpdateRequest,
    ConnectionValidationResult,
    ExportCompleteRequest,
    Interface,
    InterfacePatchRequest,
    Manufacturing,
    ManufacturingUpdateRequest,
    ModelFailRequest,
    ModelRevision,
    ModelRevisionStatus,
    ModelSucceedRequest,
    ProfileValidation,
    Project,
    ProjectPatchRequest,
    UploadResponseData,
    WorkflowState,
    current_iso_timestamp,
)
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.analysis_provider import AnalysisProvider, MockAnalysisProvider
from app.services.connection_validation import validate_connection_and_manufacturing
from app.services.kcl_compiler import KCLCompileResult, compile_project_to_kcl
from app.services.profile_validation import validate_interface_profile


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

        if not target_interface.source_image_ref:
            raise MissingPrerequisiteError(
                f"No image uploaded for {interface_id}. Upload an image before starting analysis."
            )

        image_bytes = b""
        filename = os.path.basename(target_interface.source_image_ref)
        if os.path.exists(target_interface.source_image_ref):
            with open(target_interface.source_image_ref, "rb") as f:
                image_bytes = f.read()

        active_provider = provider or MockAnalysisProvider()
        result = active_provider.analyze(image_bytes, filename)

        target_interface.profile_type = result.profile_type
        target_interface.profile_points = result.candidate_points
        target_interface.dimensions = result.candidate_dimensions

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

        if patch.source_image_ref is not None:
            target_interface.source_image_ref = patch.source_image_ref
        if patch.profile_type is not None:
            target_interface.profile_type = patch.profile_type
        if patch.profile_points is not None:
            target_interface.profile_points = patch.profile_points
        if patch.center is not None:
            target_interface.center = patch.center
        if patch.dimensions is not None:
            target_interface.dimensions = patch.dimensions

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

        # Upstream modification rule: clears approval and increments schema revision
        target_interface.approved = False
        target_interface.approved_at = None
        project.current_schema_revision += 1
        self._mark_current_model_stale_if_exists(project)

        if interface_id == "interface_a":
            project.state = WorkflowState.INTERFACE_A_REVIEW_REQUIRED
        else:
            project.state = WorkflowState.INTERFACE_B_REVIEW_REQUIRED

        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def approve_interface(
        self, project_id: str, interface_id: str, project_token: Optional[str] = None
    ) -> Project:
        """Approve interface. Enforces Interface B prerequisite and structural validation."""
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

        project.state = WorkflowState.EXPORT_READY
        project.updated_at = current_iso_timestamp()
        return self.repository.save(project)

    def validate_kcl_readiness(
        self, project_id: str, project_token: Optional[str] = None
    ) -> ConnectionValidationResult:
        """Validate KCL compilation readiness for a project."""
        project = self._verify_project_and_token(project_id, project_token)
        return validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, project.connection, project.manufacturing
        )

    def compile_kcl(
        self, project_id: str, project_token: Optional[str] = None
    ) -> KCLCompileResult:
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

