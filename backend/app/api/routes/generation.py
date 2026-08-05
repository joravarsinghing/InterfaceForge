"""API routes for 3D model generation, staged progress, job status, cancellation, and retry."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, status
from pydantic import BaseModel

from app.models.generation import GenerationJobRequest, MockScenario
from app.services.generation_job_service import GenerationJobService, get_generation_job_service

router = APIRouter(prefix="/api/projects", tags=["generation"])


class StandardResponse(BaseModel):
    """Standard success API response envelope."""

    success: bool = True
    data: Any


def get_generation_service() -> GenerationJobService:
    """Dependency provider for GenerationJobService."""
    return get_generation_job_service()


@router.post(
    "/{project_id}/generation/start",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
)
async def start_generation(
    project_id: str,
    req: Optional[GenerationJobRequest] = None,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Start 3D model generation job using configured engine provider."""
    service = get_generation_service()
    mock_scenario = req.mock_scenario if req else MockScenario.SUCCESS
    job = await service.start_generation_job_background(
        project_id=project_id,
        mock_scenario=mock_scenario,
        project_token=x_project_token,
    )
    return {"success": True, "data": job.model_dump()}


@router.get("/{project_id}/generation/active", response_model=StandardResponse)
def get_active_generation(
    project_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Return the active job so Step 4 can resume after navigation or refresh."""
    service = get_generation_service()
    service.project_service.get_project(project_id, x_project_token)
    job = service.get_active_job_for_project(project_id)
    return {"success": True, "data": job.model_dump() if job else None}


@router.get("/{project_id}/generation/{job_id}", response_model=StandardResponse)
def get_generation_status(
    project_id: str,
    job_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Retrieve generation job status and staged progress details."""
    service = get_generation_service()
    job = service.get_job(
        project_id=project_id,
        job_id=job_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": job.model_dump()}


@router.post("/{project_id}/generation/{job_id}/cancel", response_model=StandardResponse)
async def cancel_generation(
    project_id: str,
    job_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Request cancellation of an active generation job."""
    service = get_generation_service()
    job = await service.cancel_job(
        project_id=project_id,
        job_id=job_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": job.model_dump()}


@router.post(
    "/{project_id}/generation/{job_id}/retry",
    status_code=status.HTTP_201_CREATED,
    response_model=StandardResponse,
)
async def retry_generation(
    project_id: str,
    job_id: str,
    req: Optional[GenerationJobRequest] = None,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Retry a failed or cancelled generation job."""
    service = get_generation_service()
    mock_scenario = req.mock_scenario if req else None
    job = await service.retry_job(
        project_id=project_id,
        job_id=job_id,
        mock_scenario=mock_scenario,
        project_token=x_project_token,
    )
    return {"success": True, "data": job.model_dump()}


@router.get("/{project_id}/generation/{job_id}/preview", response_model=StandardResponse)
def get_preview_metadata(
    project_id: str,
    job_id: str,
    x_project_token: Optional[str] = Header(None, alias="X-Project-Token"),
) -> Dict[str, Any]:
    """Retrieve preview artifact metadata for a generation job."""
    service = get_generation_service()
    preview = service.get_job_preview(
        project_id=project_id,
        job_id=job_id,
        project_token=x_project_token,
    )
    return {"success": True, "data": preview.model_dump()}
