"""Generation job service managing execution lifecycle and recovery per ADR-005."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.exceptions import APIError
from app.models.generation import (
    GenerationJob,
    GenerationStage,
    JobStatus,
    MockScenario,
    PreviewMetadata,
)
from app.models.schema import ModelRevision, ModelRevisionStatus, WorkflowState
from app.services.engine_provider import get_engine_provider
from app.services.project_service import ProjectService


def current_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationJobService:
    """Service managing generation jobs, staged progress, and recovery."""

    # In-memory storage for active and completed generation jobs
    _jobs: Dict[str, GenerationJob] = {}

    def __init__(self, project_service: Optional[ProjectService] = None) -> None:
        self.project_service = project_service or ProjectService()

    def get_active_job_for_project(self, project_id: str) -> Optional[GenerationJob]:
        """Return currently active generation job for a project if one exists."""
        for job in self._jobs.values():
            if job.project_id == project_id and job.status in (
                JobStatus.QUEUED,
                JobStatus.RUNNING,
                JobStatus.CANCEL_REQUESTED,
            ):
                return job
        return None

    def get_job(
        self, project_id: str, job_id: str, project_token: Optional[str] = None
    ) -> GenerationJob:
        """Retrieve job status for a given project and job ID."""
        # Verify project access
        self.project_service.get_project(project_id, project_token)

        if job_id not in self._jobs:
            raise APIError(
                error_id="IF-JOB-404",
                message=f"Generation job '{job_id}' not found.",
                status_code=404,
                recovery_steps=["Check the job ID or start a new generation job."],
            )

        job = self._jobs[job_id]
        if job.project_id != project_id:
            raise APIError(
                error_id="IF-JOB-400",
                message=f"Job '{job_id}' does not belong to project '{project_id}'.",
                status_code=400,
            )
        return job

    async def start_generation_job(
        self,
        project_id: str,
        mock_scenario: MockScenario = MockScenario.SUCCESS,
        project_token: Optional[str] = None,
    ) -> GenerationJob:
        """Start a new generation job with duplicate prevention and draft tracking."""

        # 1. Verify project exists & token is valid
        project = self.project_service.get_project(project_id, project_token)

        # 2. Duplicate active-job prevention per project
        active_job = self.get_active_job_for_project(project_id)
        if active_job:
            raise APIError(
                error_id="IF-JOB-409",
                message=(
                    f"Active generation job '{active_job.job_id}' is already "
                    f"in progress for project '{project_id}'."
                ),
                status_code=409,
                recovery_steps=["Wait for the active generation job to complete or cancel it."],
            )

        # 3. Pre-flight KCL compilation & readiness verification
        readiness = self.project_service.validate_kcl_readiness(project_id, project_token)
        if not readiness.is_valid:
            error_msgs = [e.message for e in readiness.blocking_errors]
            raise APIError(
                error_id="IF-PREREQ-400",
                message=f"Project is not ready for 3D generation: {'; '.join(error_msgs)}",
                status_code=400,
                recovery_steps=[
                    "Approve interfaces and configure valid connection parameters first."
                ],
            )

        compile_result = self.project_service.compile_kcl(project_id, project_token)
        if not compile_result.success or not compile_result.kcl_code:
            compiler_issue = compile_result.errors[0] if compile_result.errors else None
            raise APIError(
                error_id=compiler_issue.id if compiler_issue else "IF-KCL-400",
                message=(
                    compiler_issue.message
                    if compiler_issue
                    else "KCL compilation failed prior to generation."
                ),
                status_code=400,
                details={
                    "compiler_errors": [issue.model_dump() for issue in compile_result.errors]
                },
                recovery_steps=(
                    compiler_issue.recovery_steps
                    if compiler_issue
                    else ["Fix design schema parameters and re-compile KCL."]
                ),
            )

        # 4. Preserve last-known-good model revision per ADR-005
        # If current model is CURRENT, preserve its revision as last known good
        if project.current_model_revision is not None:
            if project.last_known_good_model_revision is None:
                project.last_known_good_model_revision = project.current_model_revision

        # Determine new draft revision index
        next_rev_num = max([r.model_revision for r in project.model_revisions], default=0) + 1

        draft_revision = ModelRevision(
            model_revision=next_rev_num,
            schema_revision=project.current_schema_revision,
            status=ModelRevisionStatus.GENERATING,
            kcl_artifact_ref=compile_result.artifact_ref,
        )
        project.model_revisions.append(draft_revision)
        project.state = WorkflowState.GENERATION_IN_PROGRESS
        self.project_service.repository.save(project)

        # 5. Create GenerationJob
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = GenerationJob(
            job_id=job_id,
            project_id=project_id,
            model_revision=next_rev_num,
            status=JobStatus.QUEUED,
            current_stage=GenerationStage.VALIDATING,
            progress_percent=0,
            mock_scenario=mock_scenario,
            kcl_code_snippet=compile_result.preview_snippet or compile_result.kcl_code[:200],
        )
        self._jobs[job_id] = job

        # 6. Execute job via active EngineProvider
        engine = get_engine_provider(
            project.provider_mode.value
            if hasattr(project.provider_mode, "value")
            else str(project.provider_mode)
        )
        job.status = JobStatus.RUNNING
        try:
            executed_job = await engine.execute_generation(
                job, compile_result.kcl_code, project=project
            )
        except Exception as exc:
            # Never leave a job stuck in RUNNING after an unexpected provider failure.
            executed_job = job
            executed_job.status = JobStatus.FAILED
            executed_job.error_id = "IF-ENG-999"
            executed_job.error_message = f"Generation provider failed unexpectedly: {exc}"
            executed_job.recovery_steps = ["Retry model generation."]
            executed_job.completed_at = current_iso_timestamp()
            executed_job.updated_at = executed_job.completed_at
        self._jobs[job_id] = executed_job

        # 7. Finalize project state based on job execution result (ADR-005)
        fresh_project = self.project_service.get_project(project_id, project_token)
        target_rev = next(
            (r for r in fresh_project.model_revisions if r.model_revision == next_rev_num),
            None,
        )

        if executed_job.status == JobStatus.SUCCEEDED:
            if target_rev:
                target_rev.status = ModelRevisionStatus.CURRENT
                target_rev.preview_artifact_ref = (
                    executed_job.preview_metadata.preview_svg
                    if executed_job.preview_metadata
                    else None
                )
                target_rev.volume_cm3 = (
                    executed_job.preview_metadata.volume_cm3
                    if executed_job.preview_metadata
                    else None
                )
                target_rev.zoo_model_id = executed_job.zoo_model_id
                target_rev.kcl_hash = executed_job.kcl_hash
            fresh_project.current_model_revision = next_rev_num
            fresh_project.last_known_good_model_revision = next_rev_num
            fresh_project.state = WorkflowState.MODEL_CURRENT
        else:
            # Failure / Cancellation / Timeout handling: Preserve last known good!
            if target_rev:
                target_rev.status = ModelRevisionStatus.FAILED
                if executed_job.error_message:
                    target_rev.warnings.append(executed_job.error_message)

            if fresh_project.last_known_good_model_revision is not None:
                # Revert current_model_revision to last known good
                fresh_project.current_model_revision = fresh_project.last_known_good_model_revision
                fresh_project.state = WorkflowState.GENERATION_FAILED
            else:
                fresh_project.current_model_revision = None
                fresh_project.state = WorkflowState.GENERATION_FAILED

        self.project_service.repository.save(fresh_project)
        return executed_job
    async def start_generation_job_background(
        self,
        project_id: str,
        mock_scenario: MockScenario = MockScenario.SUCCESS,
        project_token: Optional[str] = None,
    ) -> GenerationJob:
        """Start the exact generation pipeline without holding the HTTP request open."""
        task = asyncio.create_task(
            self.start_generation_job(
                project_id=project_id,
                mock_scenario=mock_scenario,
                project_token=project_token,
            )
        )
        await asyncio.sleep(0)
        active_job = self.get_active_job_for_project(project_id)
        if active_job is not None:
            return active_job
        return await task


    async def cancel_job(
        self, project_id: str, job_id: str, project_token: Optional[str] = None
    ) -> GenerationJob:
        """Cancel an in-progress generation job."""
        job = self.get_job(project_id, job_id, project_token)
        if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
            raise APIError(
                error_id="IF-JOB-400",
                message=(
                    f"Cannot cancel job in state '{job.status}'. "
                    "Only queued or running jobs can be cancelled."
                ),
                status_code=400,
            )

        job.status = JobStatus.CANCEL_REQUESTED
        # Execute cancellation logic via active project engine provider
        project = self.project_service.get_project(project_id, project_token)
        engine = get_engine_provider(
            project.provider_mode.value
            if hasattr(project.provider_mode, "value")
            else str(project.provider_mode)
        )
        job.mock_scenario = MockScenario.CANCELLATION
        cancelled_job = await engine.execute_generation(job, "")
        self._jobs[job_id] = cancelled_job

        # Restore last known good model state
        target_rev = next(
            (r for r in project.model_revisions if r.model_revision == job.model_revision),
            None,
        )
        if target_rev:
            target_rev.status = ModelRevisionStatus.FAILED

        if project.last_known_good_model_revision is not None:
            project.current_model_revision = project.last_known_good_model_revision
            project.state = WorkflowState.GENERATION_FAILED
        else:
            project.current_model_revision = None
            project.state = WorkflowState.GENERATION_FAILED

        self.project_service.repository.save(project)
        return cancelled_job

    async def retry_job(
        self,
        project_id: str,
        job_id: str,
        mock_scenario: Optional[MockScenario] = None,
        project_token: Optional[str] = None,
    ) -> GenerationJob:
        """Retry a failed or cancelled generation job."""
        job = self.get_job(project_id, job_id, project_token)
        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            raise APIError(
                error_id="IF-JOB-400",
                message=(
                    f"Cannot retry job in state '{job.status}'. "
                    "Only failed or cancelled jobs can be retried."
                ),
                status_code=400,
            )

        target_scenario = mock_scenario or MockScenario.SUCCESS
        return await self.start_generation_job(
            project_id=project_id,
            mock_scenario=target_scenario,
            project_token=project_token,
        )

    def get_job_preview(
        self, project_id: str, job_id: str, project_token: Optional[str] = None
    ) -> PreviewMetadata:
        """Retrieve preview metadata for a generation job."""
        job = self.get_job(project_id, job_id, project_token)
        if not job.preview_metadata:
            raise APIError(
                error_id="IF-PREVIEW-404",
                message=(
                    f"Preview metadata not available for job '{job_id}' in state '{job.status}'."
                ),
                status_code=404,
                recovery_steps=[
                    "Ensure the generation job completes successfully before requesting preview."
                ],
            )
        return job.preview_metadata


_generation_job_service_instance: Optional[GenerationJobService] = None


def get_generation_job_service() -> GenerationJobService:
    """Singleton getter for GenerationJobService."""
    global _generation_job_service_instance
    if _generation_job_service_instance is None:
        _generation_job_service_instance = GenerationJobService()
    return _generation_job_service_instance
