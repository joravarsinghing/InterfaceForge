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

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch(
            "app.services.engine_provider._execute_zoo_sdk_isolated",
            return_value=(
                "response",
                {
                    "kind": "error",
                    "error_id": "IF-ZOO-SDK-EXCEPTION",
                    "message": "Zoo SDK execution failed (RuntimeError).",
                },
            ),
        ):
            res = await provider.execute_generation(job, "cube(20)")

    assert res.status == JobStatus.FAILED
    assert res.error_id == "IF-ZOO-SDK-EXCEPTION"
    assert "RuntimeError" in res.error_message

@pytest.mark.asyncio
async def test_background_generation_retains_task_and_completes(approved_project):
    """The service-owned task remains alive after the start call returns."""
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingCompletedEngine:
        async def execute_generation(self, job, _kcl_code, project=None):
            started.set()
            job.progress_percent = 25
            await release.wait()
            job.status = JobStatus.SUCCEEDED
            job.current_stage = GenerationStage.FINALIZING
            job.progress_percent = 100
            return job

    service = GenerationJobService()
    with patch("app.services.generation_job_service.get_engine_provider", return_value=BlockingCompletedEngine()):
        returned = await service.start_generation_job_background(
            approved_project.project_id,
            project_token=approved_project.project_token,
        )
        assert returned.status == JobStatus.RUNNING
        assert approved_project.project_id in service._active_tasks
        assert started.is_set()
        release.set()
        task = service._active_tasks[approved_project.project_id]
        result = await asyncio.wait_for(task, timeout=1)

    assert result.status == JobStatus.SUCCEEDED
    assert service.project_service.repository.get_generation_job(result.job_id).status == JobStatus.SUCCEEDED
    await asyncio.sleep(0)
    assert approved_project.project_id not in service._active_tasks


@pytest.mark.asyncio
async def test_background_provider_failure_marks_job_failed_and_cleans_task(approved_project):
    class FailingEngine:
        async def execute_generation(self, _job, _kcl_code, project=None):
            raise RuntimeError("provider failure")

    service = GenerationJobService()
    with patch("app.services.generation_job_service.get_engine_provider", return_value=FailingEngine()):
        returned = await service.start_generation_job_background(
            approved_project.project_id,
            project_token=approved_project.project_token,
        )
        assert returned.status == JobStatus.FAILED
        await asyncio.sleep(0)

    failed = service.project_service.repository.get_generation_job(returned.job_id)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    await asyncio.sleep(0)
    assert approved_project.project_id not in service._active_tasks


@pytest.mark.asyncio
async def test_unexpected_background_exception_is_retrieved_and_logged(approved_project, caplog):
    service = GenerationJobService()
    caplog.set_level("ERROR")
    with patch.object(
        service,
        "start_generation_job",
        side_effect=RuntimeError("secret payload must not be logged"),
    ):
        with pytest.raises(APIError) as exc_info:
            await service.start_generation_job_background(
                approved_project.project_id,
                project_token=approved_project.project_token,
            )

    assert exc_info.value.error_id == "IF-JOB-500"
    await asyncio.sleep(0)
    assert approved_project.project_id not in service._active_tasks
    assert "exception_type=RuntimeError" in caplog.text
    assert "secret payload" not in caplog.text


@pytest.mark.asyncio
async def test_background_duplicate_start_is_rejected(approved_project):
    release = asyncio.Event()

    class BlockingEngine:
        async def execute_generation(self, job, _kcl_code, project=None):
            job.progress_percent = 25
            await release.wait()
            job.status = JobStatus.SUCCEEDED
            job.current_stage = GenerationStage.FINALIZING
            job.progress_percent = 100
            return job

    service = GenerationJobService()
    with patch("app.services.generation_job_service.get_engine_provider", return_value=BlockingEngine()):
        first = await service.start_generation_job_background(
            approved_project.project_id,
            project_token=approved_project.project_token,
        )
        with pytest.raises(APIError) as exc_info:
            await service.start_generation_job_background(
                approved_project.project_id,
                project_token=approved_project.project_token,
            )
        assert exc_info.value.error_id == "IF-JOB-409"
        release.set()
        await asyncio.wait_for(service._active_tasks[approved_project.project_id], timeout=1)

    assert first.status == JobStatus.SUCCEEDED
@pytest.mark.asyncio
async def test_start_endpoint_returns_201_and_background_job_progresses(
    approved_project, async_client
):
    release = asyncio.Event()

    class BlockingEngine:
        async def execute_generation(self, job, _kcl_code, project=None):
            job.progress_percent = 25
            await release.wait()
            job.status = JobStatus.SUCCEEDED
            job.current_stage = GenerationStage.FINALIZING
            job.progress_percent = 100
            return job

    with patch("app.services.generation_job_service.get_engine_provider", return_value=BlockingEngine()):
        response = await async_client.post(
            f"/api/projects/{approved_project.project_id}/generation/start",
            headers={"X-Project-Token": approved_project.project_token},
        )
        assert response.status_code == 201
        assert response.json()["data"]["progress_percent"] > 0
        job_id = response.json()["data"]["job_id"]
        release.set()
        for _ in range(20):
            status_response = await async_client.get(
                f"/api/projects/{approved_project.project_id}/generation/{job_id}",
                headers={"X-Project-Token": approved_project.project_token},
            )
            if status_response.json()["data"]["status"] == JobStatus.SUCCEEDED.value:
                break
            await asyncio.sleep(0)

    assert status_response.json()["data"]["status"] == JobStatus.SUCCEEDED.value

@pytest.mark.asyncio
async def test_generation_diagnostics_persist_through_success(approved_project, caplog):
    caplog.set_level("INFO")
    service = GenerationJobService()
    result = await service.start_generation_job(
        approved_project.project_id,
        project_token=approved_project.project_token,
    )

    persisted = service.project_service.repository.get_generation_job(result.job_id)
    assert persisted is not None
    assert persisted.status == JobStatus.SUCCEEDED
    assert persisted.last_operation == "task_completed"
    assert persisted.last_operation_at is not None
    for operation in (
        "task_created",
        "job_persisted",
        "project_loaded",
        "loft_plan_loaded_or_built",
        "kcl_compile_started",
        "kcl_compile_completed",
        "task_started",
        "zoo_execution_started",
        "zoo_response_received",
        "preview_generation_started",
        "preview_generation_completed",
        "artifact_persistence_started",
        "artifact_persistence_completed",
        "project_finalization_started",
        "project_finalization_completed",
        "job_succeeded",
        "task_completed",
    ):
        assert f"stage={operation}" in caplog.text
    assert "secret" not in caplog.text.lower()
    assert "kcl_code" not in caplog.text.lower()


@pytest.mark.asyncio
async def test_generation_diagnostics_end_with_job_failed_on_provider_failure(approved_project):
    class FailingEngine:
        async def execute_generation(self, _job, _kcl_code, project=None):
            raise RuntimeError("provider failure")

    service = GenerationJobService()
    with patch("app.services.generation_job_service.get_engine_provider", return_value=FailingEngine()):
        result = await service.start_generation_job(
            approved_project.project_id,
            project_token=approved_project.project_token,
        )

    persisted = service.project_service.repository.get_generation_job(result.job_id)
    assert persisted is not None
    assert persisted.status == JobStatus.FAILED
    assert persisted.last_operation == "job_failed"
    assert persisted.last_operation_at is not None
