"""Focused tests for generation recovery after a backend restart."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.generation import GenerationJob, GenerationStage, JobStatus
from app.models.schema import (
    ConnectionUpdateRequest,
    ManufacturingUpdateRequest,
    ModelRevision,
    ModelRevisionStatus,
    WorkflowState,
)
from app.services.generation_job_service import (
    RESTART_ERROR_ID,
    RESTART_ERROR_MESSAGE,
    GenerationJobService,
)
from app.services.project_service import ProjectService
from app.services.kcl_compiler import KCLCompileResult


def seed_abandoned_job(stage: GenerationStage, status: JobStatus = JobStatus.RUNNING):
    service = ProjectService()
    project = service.create_project()
    project.current_model_revision = 1
    project.last_known_good_model_revision = 1
    project.state = WorkflowState.GENERATION_IN_PROGRESS
    project.model_revisions = [
        ModelRevision(model_revision=1, schema_revision=1, status=ModelRevisionStatus.CURRENT),
        ModelRevision(model_revision=2, schema_revision=1, status=ModelRevisionStatus.GENERATING),
    ]
    service.repository.save(project)
    job = GenerationJob(
        job_id=f"job_recovery_{stage.value}",
        project_id=project.project_id,
        model_revision=2,
        status=status,
        current_stage=stage,
        progress_percent=60,
    )
    service.repository.save_generation_job(job)
    return service, project, job


@pytest.mark.parametrize("stage", list(GenerationStage))
def test_startup_recovery_handles_each_transient_stage(stage):
    service, project, job = seed_abandoned_job(stage)

    assert GenerationJobService(project_service=service).recover_abandoned_jobs() == 1

    recovered = service.repository.get_generation_job(job.job_id)
    saved = service.get_project(project.project_id, project.project_token)
    assert recovered is not None
    assert recovered.status == JobStatus.FAILED
    assert recovered.error_id == RESTART_ERROR_ID
    assert recovered.error_message == RESTART_ERROR_MESSAGE
    assert saved.current_model_revision == 1
    assert saved.last_known_good_model_revision == 1
    assert saved.state == WorkflowState.GENERATION_FAILED
    assert saved.model_revisions[0].status != ModelRevisionStatus.FAILED
    assert saved.model_revisions[1].status == ModelRevisionStatus.FAILED
    assert GenerationJobService(project_service=service).get_active_job_for_project(project.project_id) is None


def test_startup_recovery_handles_queued_jobs_and_is_idempotent():
    service, project, job = seed_abandoned_job(GenerationStage.VALIDATING, JobStatus.QUEUED)
    recovery = GenerationJobService(project_service=service)

    assert recovery.recover_abandoned_jobs() == 1
    recovered = service.repository.get_generation_job(job.job_id)
    assert recovered is not None
    completed_at = recovered.completed_at
    assert recovery.recover_abandoned_jobs() == 0
    assert service.repository.get_generation_job(job.job_id).completed_at == completed_at


@pytest.mark.parametrize("status", [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED])
def test_completed_or_failed_jobs_are_not_modified(status):
    service, project, job = seed_abandoned_job(GenerationStage.FINALIZING, status)
    before = service.repository.get_generation_job(job.job_id).model_dump()

    assert GenerationJobService(project_service=service).recover_abandoned_jobs() == 0
    assert service.repository.get_generation_job(job.job_id).model_dump() == before


def test_active_endpoint_does_not_report_recovered_job(client: TestClient):
    service, project, job = seed_abandoned_job(GenerationStage.EXECUTING)
    GenerationJobService(project_service=service).recover_abandoned_jobs()

    response = client.get(
        f"/api/projects/{project.project_id}/generation/active",
        headers={"X-Project-Token": project.project_token},
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.asyncio
async def test_new_generation_can_start_after_recovery():
    service = ProjectService()
    project = service.create_project()
    service.approve_interface(project.project_id, "interface_a", project.project_token)
    service.approve_interface(project.project_id, "interface_b", project.project_token)
    service.update_connection_and_manufacturing(
        project.project_id,
        ConnectionUpdateRequest(
            mode="coaxial",
            length_mm=40,
            offset_x_mm=0,
            offset_y_mm=0,
            angle_deg=0,
        ),
        ManufacturingUpdateRequest(
            process="fdm",
            material="PETG",
            wall_thickness_mm=2.5,
            clearance_a_mm=0.3,
            clearance_b_mm=0.2,
        ),
        project.project_token,
    )
    project = service.get_project(project.project_id, project.project_token)
    project.current_model_revision = 1
    project.last_known_good_model_revision = 1
    project.state = WorkflowState.GENERATION_IN_PROGRESS
    project.model_revisions.append(
        ModelRevision(model_revision=2, schema_revision=1, status=ModelRevisionStatus.GENERATING)
    )
    service.repository.save(project)
    abandoned = GenerationJob(
        job_id="job_recovery_then_retry",
        project_id=project.project_id,
        model_revision=2,
        status=JobStatus.RUNNING,
        current_stage=GenerationStage.EXECUTING,
    )
    service.repository.save_generation_job(abandoned)
    generation = GenerationJobService(project_service=service)
    generation.recover_abandoned_jobs()

    service.validate_kcl_readiness = lambda *_args, **_kwargs: type("Readiness", (), {"is_valid": True, "blocking_errors": []})()
    service.compile_kcl = lambda *_args, **_kwargs: KCLCompileResult(success=True, kcl_code="cube(20)", schema_revision=1)

    class CompletedEngine:
        async def execute_generation(self, job, _kcl_code, project=None):
            job.status = JobStatus.SUCCEEDED
            job.current_stage = GenerationStage.FINALIZING
            job.progress_percent = 100
            return job

    with patch("app.services.generation_job_service.get_engine_provider", return_value=CompletedEngine()):
        new_job = await generation.start_generation_job(project.project_id, project_token=project.project_token)
    assert new_job.status == JobStatus.SUCCEEDED
    assert generation.get_active_job_for_project(project.project_id) is None

