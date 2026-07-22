"""Health and readiness endpoints for backend status checks."""

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings


class HealthData(BaseModel):
    """Safe health response metadata."""

    service_name: str
    status: str
    environment: str
    version: str


class ResponseEnvelope(BaseModel):
    """Standard success response envelope."""

    success: bool = True
    data: Dict[str, Any]


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=ResponseEnvelope)
async def get_health() -> ResponseEnvelope:
    """Return application health metadata. Safe information only."""
    health_info = HealthData(
        service_name=settings.app_name,
        status="ok",
        environment=settings.environment,
        version=settings.app_version,
    )
    return ResponseEnvelope(success=True, data=health_info.model_dump())


@router.get("/ready", response_model=ResponseEnvelope)
async def get_ready() -> ResponseEnvelope:
    """Return application readiness status."""
    ready_info = {
        "status": "ready",
        "service": settings.app_name,
        "checks": {
            "api": "healthy",
            "zoo_integration": "not_integrated_stage_s2",
        },
    }
    return ResponseEnvelope(success=True, data=ready_info)
