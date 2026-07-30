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


def test_successful_mock_execution(approved_project):
    """Test successful 3D generation via mock provider."""
    # 1. Start generation via API endpoint
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "success"},
    )
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["status"] == JobStatus.SUCCEEDED
    assert data["current_stage"] == GenerationStage.FINALIZING
    assert data["progress_percent"] == 100
    assert data["preview_metadata"] is not None
    assert "INTERFACEFORGE 3D PREVIEW" in data["preview_metadata"]["preview_svg"]

    # 2. Verify project state updated to model_current
    proj_res = client.get(
        f"/api/projects/{approved_project.project_id}",
        headers={"X-Project-Token": approved_project.project_token},
    )
    proj_data = proj_res.json()["data"]
    assert proj_data["state"] == WorkflowState.MODEL_CURRENT
    assert proj_data["current_model_revision"] == 1
    assert proj_data["last_known_good_model_revision"] == 1


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


def test_duplicate_job_rejection(approved_project):
    """Test prevention of active duplicate jobs per project."""
    job_service = GenerationJobService()

    # Manually register a running job for the project
    from app.models.generation import GenerationJob

    active_job = GenerationJob(
        job_id="job_active_test",
        project_id=approved_project.project_id,
        model_revision=1,
        status=JobStatus.RUNNING,
        current_stage=GenerationStage.EXECUTING,
    )
    job_service._jobs["job_active_test"] = active_job

    # Attempt to start a new job while active_job is running
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "success"},
    )
    assert res.status_code == 409
    json_body = res.json()
    assert json_body["success"] is False
    assert json_body["error"]["id"] == "IF-JOB-409"


def test_engine_validation_failure(approved_project):
    """Test engine validation failure scenario."""
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "engine_validation_failure"},
    )
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["status"] == JobStatus.FAILED
    assert data["error_id"] == "IF-ENG-001"
    assert "validation error" in data["error_message"].lower()

    # Verify project is marked failed without current model
    proj_res = client.get(
        f"/api/projects/{approved_project.project_id}",
        headers={"X-Project-Token": approved_project.project_token},
    )
    proj_data = proj_res.json()["data"]
    assert proj_data["state"] == WorkflowState.GENERATION_FAILED
    assert proj_data["current_model_revision"] is None


def test_timeout_scenario(approved_project):
    """Test timeout failure scenario."""
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "timeout"},
    )
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["status"] == JobStatus.FAILED
    assert data["error_id"] == "IF-ENG-002"
    assert "timed out" in data["error_message"].lower()


def test_malformed_response_scenario(approved_project):
    """Test malformed engine response scenario."""
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "malformed_response"},
    )
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["status"] == JobStatus.FAILED
    assert data["error_id"] == "IF-ENG-003"
    assert "malformed" in data["error_message"].lower()


def test_preview_failure_scenario(approved_project):
    """Test preview rendering failure after model success scenario."""
    res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "preview_failure"},
    )
    assert res.status_code == 201
    data = res.json()["data"]

    assert data["status"] == JobStatus.FAILED
    assert data["error_id"] == "IF-ENG-004"
    assert "preview rendering failed" in data["error_message"].lower()


def test_cancellation_and_retry(approved_project):
    """Test job cancellation and subsequent retry."""
    # 1. Start generation
    start_res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "cancellation"},
    )
    job_data = start_res.json()["data"]
    job_id = job_data["job_id"]
    assert job_data["status"] == JobStatus.CANCELLED

    # 2. Retry the cancelled job
    retry_res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/{job_id}/retry",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "success"},
    )
    assert retry_res.status_code == 201
    retried_data = retry_res.json()["data"]
    assert retried_data["status"] == JobStatus.SUCCEEDED


def test_last_known_good_model_preservation(approved_project):
    """Test last-known-good model preservation per ADR-005."""
    # Step 1: Generate initial successful model (Rev 1)
    res1 = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "success"},
    )
    assert res1.json()["data"]["status"] == JobStatus.SUCCEEDED

    # Verify Rev 1 is current and last known good
    proj1 = client.get(
        f"/api/projects/{approved_project.project_id}",
        headers={"X-Project-Token": approved_project.project_token},
    ).json()["data"]
    assert proj1["current_model_revision"] == 1
    assert proj1["last_known_good_model_revision"] == 1

    # Step 2: Attempt subsequent generation that fails (Rev 2)
    res2 = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "engine_validation_failure"},
    )
    assert res2.json()["data"]["status"] == JobStatus.FAILED

    # Step 3: Verify last-known-good (Rev 1) was preserved as current!
    proj2 = client.get(
        f"/api/projects/{approved_project.project_id}",
        headers={"X-Project-Token": approved_project.project_token},
    ).json()["data"]

    assert proj2["current_model_revision"] == 1
    assert proj2["last_known_good_model_revision"] == 1
    # Check that model revision 2 exists in history as failed
    revs = proj2["model_revisions"]
    assert len(revs) == 2
    assert revs[0]["model_revision"] == 1 and revs[0]["status"] == "current"
    assert revs[1]["model_revision"] == 2 and revs[1]["status"] == "failed"


def test_preview_metadata_endpoint(approved_project):
    """Test GET /preview metadata endpoint."""
    start_res = client.post(
        f"/api/projects/{approved_project.project_id}/generation/start",
        headers={"X-Project-Token": approved_project.project_token},
        json={"mock_scenario": "success"},
    )
    job_id = start_res.json()["data"]["job_id"]

    prev_res = client.get(
        f"/api/projects/{approved_project.project_id}/generation/{job_id}/preview",
        headers={"X-Project-Token": approved_project.project_token},
    )
    assert prev_res.status_code == 200
    prev_data = prev_res.json()["data"]
    assert "preview_svg" in prev_data
    assert prev_data["volume_cm3"] > 0


# --- ZooEngineProvider Contract Tests ---


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
async def test_zoo_successful_execution():
    """Test successful Zoo Engine execution path."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_zoo_success", project_id="p1", model_revision=1)

    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = [
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"set_scene_units"}}}}',
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"make_plane"}}}}',
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"start_path"}}}}',
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"take_snapshot","data":{"contents":"png_bytes"}}}}}',
    ]

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws
            res = await provider.execute_generation(job, "cube(20)")

            assert res.status == JobStatus.SUCCEEDED
            assert res.preview_metadata is not None
            assert res.preview_metadata.is_mock is False


@pytest.mark.asyncio
async def test_zoo_timeout():
    """Test execution timeout handling returning IF-ENG-002."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_zoo_timeout", project_id="p1", model_revision=1)

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch("websockets.connect", side_effect=asyncio.TimeoutError()):
            res = await provider.execute_generation(job, "cube(20)")
            assert res.status == JobStatus.FAILED
            assert res.error_id == "IF-ENG-002"
            assert "timed out" in res.error_message.lower()


@pytest.mark.asyncio
async def test_zoo_malformed_response():
    """Test malformed response payload returning IF-ENG-003."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_zoo_malformed", project_id="p1", model_revision=1)

    mock_ws = AsyncMock()
    mock_ws.recv.return_value = "invalid { json"

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws
            res = await provider.execute_generation(job, "cube(20)")

            assert res.status == JobStatus.FAILED
            assert res.error_id == "IF-ENG-003"
            assert "malformed" in res.error_message.lower()


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


@pytest.mark.asyncio
async def test_zoo_preview_failure():
    """Test preview rendering pipeline error returning IF-ENG-004."""
    provider = ZooEngineProvider()
    job = GenerationJob(job_id="job_zoo_prev_fail", project_id="p1", model_revision=1)

    mock_ws = AsyncMock()
    # Geometry commands succeed, but preview/snapshot raises RuntimeError with render
    mock_ws.recv.side_effect = [
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"set_scene_units"}}}}',
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"make_plane"}}}}',
        '{"success":true,"resp":{"type":"modeling","data":{"modeling_response":{"type":"start_path"}}}}',
        RuntimeError("preview render failure"),
    ]

    with patch.object(settings, "zoo_api_token", "api-test-token"):
        with patch("websockets.connect") as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws
            res = await provider.execute_generation(job, "cube(20)")

            assert res.status == JobStatus.FAILED
            assert res.error_id == "IF-ENG-004"
            assert "render" in res.error_message.lower()
