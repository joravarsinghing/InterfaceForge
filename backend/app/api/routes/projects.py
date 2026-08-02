"""API routes for canonical project and workflow state management."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, Header, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.core.exceptions import APIError
from app.models.schema import (
    ConnectionConfigRequest,
    ConnectionUpdateRequest,
    ExportCompleteRequest,
    ExportGenerateRequest,
    InterfacePatchRequest,
    ManufacturingUpdateRequest,
    ModelFailRequest,
    ModelSucceedRequest,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectPatchRequest,
    ProviderMode,
    ProviderModeUpdateRequest,
    RevisionConfirmRequest,
    RevisionProposeRequest,
    ScaleSnapRequest,
    TwoPointScaleCalibrationRequest,
)
from app.services.agent_service import get_agent_service
from app.services.analysis_provider import get_analysis_provider
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


class StandardResponse(BaseModel):
    """Standard success API response envelope."""

    success: bool = True
    data: Any


def get_service() -> ProjectService:
    """Dependency provider for ProjectService."""
    return ProjectService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StandardResponse)
def create_project(req: Optional[ProjectCreateRequest] = None) -> Dict[str, Any]:
    """Create a new project with canonical design schema and access token."""
    service = get_service()
    provider_mode = req.provider_mode if req else ProviderMode.MOCK
    mode_status = service.get_provider_mode_status_for_selection(provider_mode)
    if provider_mode == ProviderMode.LIVE and mode_status.effective_mode != ProviderMode.LIVE:
        raise APIError(
            error_id="IF-PROVIDER-409",
            message=mode_status.message,
            status_code=409,
            recovery_steps=[
                "Configure required backend provider credentials, then retry Live mode.",
                "Continue in Mock / Offline mode without changing project geometry.",
            ],
        )
    project = service.create_project(provider_mode=provider_mode)
    create_dto = ProjectCreateResponse(
        project_id=project.project_id,
        project_token=project.project_token,
        display_name=project.display_name,
        provider_mode=project.provider_mode,
        schema_version=project.schema_version,
        state=project.state,
    )
    return {"success": True, "data": create_dto.model_dump()}


@router.get("/provider-mode", response_model=StandardResponse)
def get_default_provider_mode() -> Dict[str, Any]:
    """Return default mock provider status before a project exists."""
    service = get_service()
    mode_status = service.get_provider_mode_status_for_selection(ProviderMode.MOCK)
    return {"success": True, "data": mode_status.model_dump()}


@router.patch("/provider-mode", response_model=StandardResponse)
def validate_default_provider_mode(req: ProviderModeUpdateRequest) -> Dict[str, Any]:
    """Validate a pre-project provider mode preference without creating a project."""
    service = get_service()
    mode_status = service.get_provider_mode_status_for_selection(req.provider_mode)
    if req.provider_mode == ProviderMode.LIVE and mode_status.effective_mode != ProviderMode.LIVE:
        raise APIError(
            error_id="IF-PROVIDER-409",
            message=mode_status.message,
            status_code=409,
            recovery_steps=[
                "Configure required backend provider credentials, then retry Live mode.",
                "Continue in Mock / Offline mode before starting a project.",
            ],
        )
    return {"success": True, "data": mode_status.model_dump()}


@router.get("/{project_id}/provider-mode", response_model=StandardResponse)
def get_project_provider_mode(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Return selected/effective provider mode without exposing credentials."""
    service = get_service()
    project = service.get_project(project_id=project_id, project_token=x_project_token)
    mode_status = service.get_provider_mode_status(project)
    return {"success": True, "data": mode_status.model_dump()}


@router.patch("/{project_id}/provider-mode", response_model=StandardResponse)
def update_project_provider_mode(
    project_id: str,
    req: ProviderModeUpdateRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Persist provider mode when the requested mode can be honored by backend config."""
    service = get_service()
    project, mode_status = service.set_provider_mode(
        project_id=project_id,
        provider_mode=req.provider_mode,
        project_token=x_project_token,
    )
    if req.provider_mode == ProviderMode.LIVE and mode_status.effective_mode != ProviderMode.LIVE:
        raise APIError(
            error_id="IF-PROVIDER-409",
            message=mode_status.message,
            status_code=409,
            recovery_steps=[
                "Configure required backend provider credentials, then retry Live mode.",
                "Continue in Mock / Offline mode without changing project geometry.",
            ],
        )
    return {
        "success": True,
        "data": {
            "project": project.model_dump(),
            "provider_status": mode_status.model_dump(),
        },
    }


@router.get("/{project_id}", response_model=StandardResponse)
def get_project(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Retrieve full project schema and workflow state."""
    service = get_service()
    project = service.get_project(project_id=project_id, project_token=x_project_token)
    return {"success": True, "data": project.model_dump()}


@router.patch("/{project_id}", response_model=StandardResponse)
def patch_project(
    project_id: str,
    patch: ProjectPatchRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Apply structured patch to top-level project model."""
    service = get_service()
    project = service.update_project_patch(
        project_id=project_id, patch=patch, project_token=x_project_token
    )
    return {"success": True, "data": project.model_dump()}


@router.post(
    "/{project_id}/interfaces/{interface_id}/mark-uploaded", response_model=StandardResponse
)
def mark_interface_uploaded(
    project_id: str,
    interface_id: str,
    source_image_ref: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Mark an interface as uploaded with a source artifact reference."""
    service = get_service()
    project = service.mark_interface_uploaded(
        project_id=project_id,
        interface_id=interface_id,
        source_image_ref=source_image_ref,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post(
    "/{project_id}/interfaces/{interface_id}/upload",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_interface_image(
    project_id: str,
    interface_id: str,
    file: UploadFile = File(...),
    known_measurement_type: Optional[str] = Form(None),
    known_measurement_value: Optional[float] = Form(None),
    known_measurement_unit: str = Form("mm"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Multipart upload endpoint for Interface A/B image files."""
    service = get_service()
    content_type = file.content_type or "image/png"
    filename = file.filename or "uploaded_image.png"
    file_bytes = await file.read()

    upload_data = service.upload_interface_image(
        project_id=project_id,
        interface_id=interface_id,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        project_token=x_project_token,
        known_measurement_type=known_measurement_type,
        known_measurement_value=known_measurement_value,
        known_measurement_unit=known_measurement_unit,
    )
    return {"success": True, "data": upload_data.model_dump()}


@router.get(
    "/{project_id}/interfaces/{interface_id}/image",
)
def serve_interface_image(
    project_id: str,
    interface_id: str,
    token: Optional[str] = Query(None, description="Project token (query param fallback)"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Response:
    """Serve the uploaded interface source image as a binary response.

    Accepts the project token via X-Project-Token header or ?token= query parameter
    so browser <img> tags can load the image without custom headers.
    """
    service = get_service()
    # Accept token from header OR query param (header takes precedence)
    effective_token = x_project_token or token
    file_bytes, content_type = service.get_interface_image_bytes(
        project_id=project_id,
        interface_id=interface_id,
        project_token=effective_token,
    )
    return Response(content=file_bytes, media_type=content_type)


@router.get("/{project_id}/interfaces/{interface_id}/cleaned_image")
def get_interface_cleaned_image(
    project_id: str,
    interface_id: str,
    token: Optional[str] = Query(None, description="Optional project token in query parameter"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Response:
    """Fetch cleaned binary image V2 artifact for an interface."""
    service = get_service()
    effective_token = x_project_token or token
    file_bytes, content_type = service.get_interface_artifact_bytes(
        project_id=project_id,
        interface_id=interface_id,
        artifact_type="cleaned_image",
        project_token=effective_token,
    )
    return Response(content=file_bytes, media_type=content_type)


@router.get("/{project_id}/interfaces/{interface_id}/analysis_image")
def get_interface_analysis_image(
    project_id: str,
    interface_id: str,
    token: Optional[str] = Query(None, description="Optional project token in query parameter"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Response:
    """Fetch the exact processed analysis image passed to OpenCV contour extraction."""
    service = get_service()
    effective_token = x_project_token or token
    file_bytes, content_type = service.get_interface_artifact_bytes(
        project_id=project_id,
        interface_id=interface_id,
        artifact_type="analysis_image",
        project_token=effective_token,
    )
    return Response(content=file_bytes, media_type=content_type)


@router.get("/{project_id}/interfaces/{interface_id}/trace_svg")
def get_interface_trace_svg(
    project_id: str,
    interface_id: str,
    token: Optional[str] = Query(None, description="Optional project token in query parameter"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Response:
    """Fetch vector SVG trace artifact for an interface."""
    service = get_service()
    effective_token = x_project_token or token
    file_bytes, content_type = service.get_interface_artifact_bytes(
        project_id=project_id,
        interface_id=interface_id,
        artifact_type="trace_svg",
        project_token=effective_token,
    )
    return Response(content=file_bytes, media_type=content_type)


@router.get("/{project_id}/interfaces/{interface_id}/overlay_svg")
def get_interface_overlay_svg(
    project_id: str,
    interface_id: str,
    token: Optional[str] = Query(None, description="Optional project token in query parameter"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Response:
    """Fetch real source image overlay SVG artifact for an interface."""
    service = get_service()
    effective_token = x_project_token or token
    file_bytes, content_type = service.get_interface_artifact_bytes(
        project_id=project_id,
        interface_id=interface_id,
        artifact_type="overlay_svg",
        project_token=effective_token,
    )
    return Response(content=file_bytes, media_type=content_type)


@router.post(
    "/{project_id}/interfaces/{interface_id}/analyze",
    response_model=StandardResponse,
)
def analyze_interface_image(
    project_id: str,
    interface_id: str,
    provider: Optional[str] = Query(
        None, description="Optional provider override ('opencv', 'mock', or 'gemini')"
    ),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Run OpenCV-only, mock, or optional AI-guided analysis on an uploaded image."""
    service = get_service()
    service.get_project(project_id=project_id, project_token=x_project_token)
    provider_name = provider or "opencv"
    active_provider = get_analysis_provider(provider_name)
    result = service.analyze_interface_image(
        project_id=project_id,
        interface_id=interface_id,
        provider=active_provider,
        project_token=x_project_token,
    )
    return {"success": True, "data": result.model_dump()}


@router.patch("/{project_id}/interfaces/{interface_id}", response_model=StandardResponse)
def patch_interface(
    project_id: str,
    interface_id: str,
    patch: InterfacePatchRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Update interface parameters (clears approval and marks current model stale)."""
    service = get_service()
    project = service.patch_interface(
        project_id=project_id,
        interface_id=interface_id,
        patch=patch,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/interfaces/{interface_id}/scale/snap", response_model=StandardResponse)
def snap_interface_scale_point(
    project_id: str,
    interface_id: str,
    req: ScaleSnapRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Snap a trace-space calibration point to valid traced geometry."""
    service = get_service()
    result = service.snap_scale_point(
        project_id=project_id,
        interface_id=interface_id,
        point=req.point,
        project_token=x_project_token,
    )
    return {"success": True, "data": result.model_dump()}


@router.post(
    "/{project_id}/interfaces/{interface_id}/scale/calibrate", response_model=StandardResponse
)
def calibrate_interface_scale(
    project_id: str,
    interface_id: str,
    req: TwoPointScaleCalibrationRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Persist or confirm two-point traced scale calibration."""
    service = get_service()
    project = service.calibrate_interface_scale(
        project_id=project_id,
        interface_id=interface_id,
        req=req,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.delete(
    "/{project_id}/interfaces/{interface_id}/scale/calibration", response_model=StandardResponse
)
def reset_interface_scale_calibration(
    project_id: str,
    interface_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Reset trace scale calibration and invalidate approval."""
    service = get_service()
    project = service.reset_interface_scale_calibration(
        project_id=project_id,
        interface_id=interface_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/interfaces/{interface_id}/approve", response_model=StandardResponse)
def approve_interface(
    project_id: str,
    interface_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Approve an interface (Enforces: Interface B cannot be approved before Interface A)."""
    service = get_service()
    project = service.approve_interface(
        project_id=project_id,
        interface_id=interface_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.put("/{project_id}/connection", response_model=StandardResponse)
def update_connection(
    project_id: str,
    connection_update: ConnectionUpdateRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Update connection settings (Enforces: Both interfaces must be approved first)."""
    service = get_service()
    project = service.update_connection(
        project_id=project_id,
        req=connection_update,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.put("/{project_id}/manufacturing", response_model=StandardResponse)
def update_manufacturing(
    project_id: str,
    manufacturing_update: ManufacturingUpdateRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Update manufacturing parameters."""
    service = get_service()
    project = service.update_manufacturing(
        project_id=project_id,
        req=manufacturing_update,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/validate-connection", response_model=StandardResponse)
def validate_connection(
    project_id: str,
    connection_config: Optional[ConnectionConfigRequest] = None,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Validate connection and manufacturing configuration against approved interfaces."""
    service = get_service()
    conn_obj = connection_config.connection if connection_config else None
    mfg_obj = connection_config.manufacturing if connection_config else None

    # Convert DTOs if provided
    from app.models.schema import Connection, Manufacturing

    target_conn = (
        Connection(
            mode=conn_obj.mode,
            length_mm=conn_obj.length_mm,
            offset_x_mm=conn_obj.offset_x_mm,
            offset_y_mm=conn_obj.offset_y_mm,
            angle_deg=conn_obj.angle_deg,
            extension_a_mm=conn_obj.extension_a_mm,
            extension_b_mm=conn_obj.extension_b_mm,
        )
        if conn_obj
        else None
    )
    target_mfg = (
        Manufacturing(
            process=mfg_obj.process,
            material=mfg_obj.material,
            wall_thickness_mm=mfg_obj.wall_thickness_mm,
            clearance_a_mm=mfg_obj.clearance_a_mm,
            clearance_b_mm=mfg_obj.clearance_b_mm,
        )
        if mfg_obj
        else None
    )

    validation = service.validate_connection_config(
        project_id=project_id,
        connection=target_conn,
        manufacturing=target_mfg,
        project_token=x_project_token,
    )
    data = validation.model_dump()
    if validation.is_valid and target_conn is not None and target_mfg is not None:
        plan = service.preview_loft_plan(
            project_id=project_id,
            connection=target_conn,
            manufacturing=target_mfg,
            project_token=x_project_token,
        )
        data["loft_plan"] = plan.model_dump() if plan is not None else None
    return {"success": True, "data": data}
@router.put("/{project_id}/connection-config", response_model=StandardResponse)
def update_connection_config(
    project_id: str,
    req: ConnectionConfigRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Atomically update both connection and manufacturing parameters."""
    service = get_service()
    project = service.update_connection_and_manufacturing(
        project_id=project_id,
        connection_req=req.connection,
        manufacturing_req=req.manufacturing,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/model/start", response_model=StandardResponse)
def start_model_generation(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Start 3D model generation process."""
    service = get_service()
    project = service.start_model_generation(
        project_id=project_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/model/succeed", response_model=StandardResponse)
def succeed_model_generation(
    project_id: str,
    req: ModelSucceedRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Complete 3D model generation successfully."""
    service = get_service()
    project = service.succeed_model_generation(
        project_id=project_id,
        req=req,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/model/fail", response_model=StandardResponse)
def fail_model_generation(
    project_id: str,
    req: ModelFailRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Register 3D model generation failure (preserves last-known-good model)."""
    service = get_service()
    project = service.fail_model_generation(
        project_id=project_id,
        req=req,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/export/start", response_model=StandardResponse)
def start_export(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Start export generation (Enforces: Current valid model required)."""
    service = get_service()
    project = service.start_export(
        project_id=project_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/export/complete", response_model=StandardResponse)
def complete_export(
    project_id: str,
    req: ExportCompleteRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Complete export generation."""
    service = get_service()
    project = service.complete_export(
        project_id=project_id,
        req=req,
        project_token=x_project_token,
    )
    return {"success": True, "data": project.model_dump()}


@router.post("/{project_id}/exports/generate", response_model=StandardResponse)
async def generate_exports(
    project_id: str,
    req: Optional[ExportGenerateRequest] = None,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Generate requested format exports (STL, STEP, KCL) per S8."""
    service = get_service()
    formats = req.formats if req and req.formats else ["stl", "step", "kcl"]
    mock_scenario = req.mock_scenario if req else None
    result = await service.generate_exports(
        project_id=project_id,
        formats=formats,
        project_token=x_project_token,
        mock_scenario=mock_scenario,
    )
    return {"success": True, "data": result.model_dump()}


@router.get("/{project_id}/exports/status", response_model=StandardResponse)
def get_export_status(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Get per-format export status and metadata per S8."""
    service = get_service()
    result = service.get_export_status(
        project_id=project_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": result.model_dump()}


@router.post("/{project_id}/exports/{format_name}/retry", response_model=StandardResponse)
async def retry_format_export(
    project_id: str,
    format_name: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Retry export generation for a single failed format per S8."""
    service = get_service()
    result = await service.generate_exports(
        project_id=project_id,
        formats=[format_name],
        project_token=x_project_token,
    )
    return {"success": True, "data": result.model_dump()}


@router.get("/{project_id}/exports/{format_name}/download")
def download_export_artifact(
    project_id: str,
    format_name: str,
    token: Optional[str] = Query(None, description="Project token for browser download"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> FileResponse:
    """Download verified export artifact file per S8."""
    service = get_service()
    file_path, filename, media_type = service.download_export_artifact(
        project_id=project_id,
        format_name=format_name,
        project_token=x_project_token or token,
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get("/{project_id}/kcl", response_model=StandardResponse)
def read_current_kcl(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Read the exact KCL artifact attached to the current model revision."""
    service = get_service()
    return {"success": True, "data": service.read_current_kcl(project_id, x_project_token)}

@router.get("/{project_id}/kcl/readiness", response_model=StandardResponse)
def validate_kcl_readiness(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Validate project compile readiness before KCL generation."""
    service = get_service()
    validation = service.validate_kcl_readiness(
        project_id=project_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": validation.model_dump()}


@router.post("/{project_id}/kcl/compile", response_model=StandardResponse)
def compile_kcl(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Compile canonical project schema into deterministic KCL code."""
    service = get_service()
    result = service.compile_kcl(
        project_id=project_id,
        project_token=x_project_token,
    )
    return {"success": result.success, "data": result.model_dump()}


@router.post("/{project_id}/revision/propose", response_model=StandardResponse)
async def propose_revision(
    project_id: str,
    req: RevisionProposeRequest,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Propose structured natural language parameter revisions per Stage S9."""
    service = get_service()
    project = service.get_project(project_id, project_token=x_project_token)
    agent_svc = get_agent_service()
    project_mode = (
        project.provider_mode.value
        if hasattr(project.provider_mode, "value")
        else str(project.provider_mode)
    )
    provider_name = req.provider or ("zoo" if project_mode == "live" else "mock")
    proposal = await agent_svc.propose_revision(
        project_id=project_id,
        prompt=req.prompt,
        provider_name=provider_name,
    )
    return {"success": True, "data": proposal.model_dump()}


@router.post("/{project_id}/revision/confirm", response_model=StandardResponse)
async def confirm_revision(
    project_id: str,
    req: RevisionConfirmRequest,
    mock_scenario: Optional[str] = Query("success"),
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Confirm parameter changes and return a stale project for Step 3/4 regeneration per S9."""
    service = get_service()
    service.get_project(project_id, project_token=x_project_token)
    agent_svc = get_agent_service()
    project, _ = await agent_svc.confirm_revision(
        project_id=project_id,
        changes=req.changes,
        mock_scenario=mock_scenario or "success",
    )
    return {
        "success": True,
        "data": {
            "project": project.model_dump(),
            "job": None,
        },
    }

