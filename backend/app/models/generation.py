"""Generation job models, staged progress enums, and preview metadata definitions."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def current_iso_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    """Lifecycle status for generation jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class GenerationStage(str, Enum):
    """Staged execution pipeline progress steps per ADR-006."""

    VALIDATING = "validating"
    COMPILING = "compiling"
    EXECUTING = "executing"
    RENDERING = "rendering"
    FINALIZING = "finalizing"


class MockScenario(str, Enum):
    """Supported mock execution scenarios for testing and offline development."""

    SUCCESS = "success"
    ENGINE_VALIDATION_FAILURE = "engine_validation_failure"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    CANCELLATION = "cancellation"
    PREVIEW_FAILURE = "preview_failure"


class BoundingBox(BaseModel):
    """Bounding box dimensions in millimeters."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0


class PreviewMetadata(BaseModel):
    """Preview artifact metadata and mock rendering specs."""

    preview_svg: str
    bounding_box: BoundingBox = Field(default_factory=BoundingBox)
    volume_cm3: float = 0.0
    facet_count: int = 0
    render_timestamp: str = Field(default_factory=current_iso_timestamp)
    is_mock: bool = True


class GenerationJobRequest(BaseModel):
    """Payload to request a new generation job."""

    mock_scenario: MockScenario = MockScenario.SUCCESS


class GenerationJob(BaseModel):
    """Generation job execution state tracking object."""

    job_id: str
    project_id: str
    model_revision: int
    status: JobStatus = JobStatus.QUEUED
    current_stage: GenerationStage = GenerationStage.VALIDATING
    progress_percent: int = 0
    mock_scenario: MockScenario = MockScenario.SUCCESS
    error_id: Optional[str] = None
    error_message: Optional[str] = None
    recovery_steps: List[str] = Field(default_factory=list)
    preview_metadata: Optional[PreviewMetadata] = None
    kcl_code_snippet: Optional[str] = None
    zoo_model_id: Optional[str] = None
    kcl_hash: Optional[str] = None
    created_at: str = Field(default_factory=current_iso_timestamp)
    updated_at: str = Field(default_factory=current_iso_timestamp)
    completed_at: Optional[str] = None
