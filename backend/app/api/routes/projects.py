"""API routes for canonical project and workflow state management."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Header, UploadFile, status
from pydantic import BaseModel

from app.models.schema import (
    ConnectionConfigRequest,
    ConnectionUpdateRequest,
    ExportCompleteRequest,
    InterfacePatchRequest,
    ManufacturingUpdateRequest,
    ModelFailRequest,
    ModelSucceedRequest,
    ProjectCreateResponse,
    ProjectPatchRequest,
)
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
def create_project() -> Dict[str, Any]:
    """Create a new project with canonical design schema and access token."""
    service = get_service()
    project = service.create_project()
    create_dto = ProjectCreateResponse(
        project_id=project.project_id,
        project_token=project.project_token,
        schema_version=project.schema_version,
        state=project.state,
    )
    return {"success": True, "data": create_dto.model_dump()}


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
    )
    return {"success": True, "data": upload_data.model_dump()}


@router.post(
    "/{project_id}/interfaces/{interface_id}/analyze",
    response_model=StandardResponse,
)
def analyze_interface_image(
    project_id: str,
    interface_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Run mock or AI analysis on uploaded interface image to extract profile candidates."""
    service = get_service()
    result = service.analyze_interface_image(
        project_id=project_id,
        interface_id=interface_id,
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
    return {"success": True, "data": validation.model_dump()}


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

