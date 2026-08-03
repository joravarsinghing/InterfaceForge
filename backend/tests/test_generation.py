"""Unit and integration tests for Zoo Engine integration preparation,
mock execution, job service, and last-known-good recovery.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.exceptions import APIError
from app.main import app
from app.models.generation import (
    GenerationJob,
    GenerationStage,
    JobStatus,
)
from app.models.schema import ValidationIssue, WorkflowState
from app.services.kcl_compiler import KCLCompileResult
from app.services.engine_provider import ZooEngineProvider, redact_secrets
from app.services.generation_job_service import GenerationJobService
from app.services.project_service import ProjectService

client = TestClient(app)


@pytest.fixture
def approved_project():
    """Create a project with both Interface A and Interface B approved and connection configured."""
    service = ProjectService()
    proj = service.create_project()

    # Approve Interface A
    service.approve_interface(proj.project_id, "interface_a", proj.project_token)

    # Approve Interface B
    service.approve_interface(proj.project_id, "interface_b", proj.project_token)

    # Update connection parameters
    from app.models.schema import ConnectionUpdateRequest, ManufacturingUpdateRequest

    service.update_connection_and_manufacturing(
        proj.project_id,
        connection_req=ConnectionUpdateRequest(
            mode="coaxial", length_mm=40.0, offset_x_mm=0.0, offset_y_mm=0.0, angle_deg=0.0
        ),
        manufacturing_req=ManufacturingUpdateRequest(
            process="fdm",
            material="PETG",
            wall_thickness_mm=2.5,
            clearance_a_mm=0.3,
            clearance_b_mm=0.2,
        ),
        project_token=proj.project_token,
    )

    return service.get_project(proj.project_id, proj.project_token)


@pytest.mark.asyncio
async def test_generation_preserves_underlying_kcl_compiler_error(approved_project):
    compiler_error = ValidationIssue(
        id='IF-KCL-006',
        message='Installed Zoo KCL parser is unavailable: missing execute_code_and_export',
        field='kcl_code',
        recovery_steps=['Install zoo-kcl in venv314.'],
    )
    failed_compile = KCLCompileResult(
        success=False,
        schema_revision=approved_project.current_schema_revision,
        errors=[compiler_error],
    )

    with patch.object(ProjectService, 'compile_kcl', return_value=failed_compile):
        with pytest.raises(APIError) as exc_info:
            await GenerationJobService().start_generation_job(
                approved_project.project_id,
                project_token=approved_project.project_token,
            )

    assert exc_info.value.error_id == 'IF-KCL-006'
    assert 'execute_code_and_export' in exc_info.value.message
    assert exc_info.value.details['compiler_errors'][0]['id'] == 'IF-KCL-006'


def test_zoo_provider_selection():
    """Test engine provider selection logic per ADR-009."""
    with patch.object(settings, "engine_provider", "zoo"):
        with patch.object(settings, "zoo_api_token", ""):
            assert settings.get_effective_engine_provider() == "mock"

        with patch.object(settings, "zoo_api_token", "api-test-token"):
            assert settings.get_effective_engine_provider() == "zoo"


def test_zoo_secret_redaction():
    """Test redaction of API keys, bearer tokens, and headers."""
    raw_error = "Authorization header Bearer api-612d7f17-86f1-4b42-9160-67916e76b20e failed"
    token = "api-612d7f17-86f1-4b42-9160-67916e76b20e"

    clean = redact_secrets(raw_error, token)
    assert token not in clean
    assert "[REDACTED" in clean


@pytest.mark.asyncio
async def test_zoo_authentication_failure():
    """Test handling of missing API token returning IF-ZOO-401."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_auth_fail", project_id="p1", model_revision=1)

    with patch.object(settings, "zoo_api_token", ""):
        res = await provider.execute_generation(job, "cube(20)")
        assert res.status == JobStatus.FAILED
        assert res.error_id == "IF-ZOO-401"
        assert "token" in res.error_message.lower()


@pytest.mark.asyncio
async def test_zoo_engine_validation_failure():
    """Test engine validation error returning IF-ENG-001."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_zoo_val_fail", project_id="p1", model_revision=1)

    mock_ws = AsyncMock()
    mock_ws.recv.return_value = (
        '{"success":false,"errors":[{"message":"Lofting surface self-intersects"}]}'
    )

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws
            res = await provider.execute_generation(job, "cube(20)")

            assert res.status == JobStatus.FAILED
            assert res.error_id == "IF-ENG-001"
            assert "validation" in res.error_message.lower()
