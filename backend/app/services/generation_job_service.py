"""Generation job service managing execution lifecycle and recovery per ADR-005."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.config import settings
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


logger = logging.getLogger(__name__)
RESTART_ERROR_ID = "IF-JOB-RESTARTED"
RESTART_ERROR_MESSAGE = (
    "Generation was interrupted because the backend restarted. "
    "Your last successful model is still available. Please try again."
)


def log_generation_stage(stage: str, job_id: str, project_id: str) -> None:
    """Write a safe, structured generation diagnostic without payload data."""
    logger.info(
        "generation stage=%s timestamp=%s job_id=%s project_id=%s",
        stage,
        current_iso_timestamp(),
        job_id,
        project_id,
    )


class GenerationJobService:
    """Service managing generation jobs, staged progress, and recovery."""

    # In-memory storage for active and completed generation jobs
    _jobs: Dict[str, GenerationJob] = {}

    def __init__(self, project_service: Optional[ProjectService] = None) -> None:
        self.project_service = project_service or ProjectService()
        self._jobs: Dict[str, GenerationJob] = {}
        self._active_tasks: dict[str, asyncio.Task[GenerationJob]] = {}

    def _all_persisted_jobs(self) -> Dict[str, GenerationJob]:
        jobs = {job.job_id: job for job in self.project_service.repository.list_generation_jobs()}
        jobs.update(self._jobs)
        return jobs

    def _save_job(self, job: GenerationJob) -> GenerationJob:
        self._jobs[job.job_id] = job
        self.project_service.repository.save_generation_job(job)
        return job

    def _flush_diagnostic_logs(self) -> None:
        """Flush configured handlers after a durable generation checkpoint."""
        handlers = list(logger.handlers) + list(logging.getLogger().handlers)
        seen: set[int] = set()
        for handler in handlers:
            if id(handler) in seen:
                continue
            seen.add(id(handler))
            try:
                handler.flush()
            except Exception:
                continue

    def _record_operation(self, job: GenerationJob, operation: str) -> None:
        """Persist and emit one safe diagnostic operation checkpoint."""
        job.last_operation = operation
        job.last_operation_at = current_iso_timestamp()
        job.updated_at = job.last_operation_at
        self._save_job(job)
        logger.info(
            "generation stage=%s timestamp=%s job_id=%s project_id=%s "
            "last_operation=%s progress=%s current_stage=%s",
            operation,
            job.last_operation_at,
            job.job_id,
            job.project_id,
            job.last_operation,
            job.progress_percent,
            job.current_stage.value if hasattr(job.current_stage, "value") else job.current_stage,
        )
        self._flush_diagnostic_logs()

    def _bind_operation_callback(self, job: GenerationJob) -> None:
        job.set_operation_callback(lambda operation: self._record_operation(job, operation))
    def _log_background_task_result(
        self, project_id: str, task: asyncio.Task[GenerationJob]
    ) -> None:
        """Release a retained task and record unexpected task failures safely."""
        if self._active_tasks.get(project_id) is task:
            self._active_tasks.pop(project_id, None)
        if task.cancelled():
            logger.warning(
                "generation background task cancelled job_id=unknown project_id=%s",
                project_id,
            )
            return
        try:
            error = task.exception()
        except asyncio.CancelledError:
            logger.warning(
                "generation background task cancelled job_id=unknown project_id=%s",
                project_id,
            )
            return
        if error is not None:
            logger.error(
                "generation background task failed project_id=%s exception_type=%s",
                project_id,
                type(error).__name__,
            )

    def recover_abandoned_jobs(self) -> int:
        """Fail transient jobs left behind by a backend restart."""
        recovered = 0
        for job in self._all_persisted_jobs().values():
            if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED):
                continue
            project = self.project_service.get_project(job.project_id, None)
            if not project:
                continue
            job.status = JobStatus.FAILED
            job.error_id = RESTART_ERROR_ID
            job.error_message = RESTART_ERROR_MESSAGE
            job.recovery_steps = ["Retry model generation when the backend is available."]
            job.completed_at = current_iso_timestamp()
            job.updated_at = job.completed_at
            target_rev = next(
                (rev for rev in project.model_revisions if rev.model_revision == job.model_revision),
                None,
            )
            if target_rev:
                target_rev.status = ModelRevisionStatus.FAILED
                target_rev.warnings.append(RESTART_ERROR_MESSAGE)
            if project.last_known_good_model_revision is not None:
                project.current_model_revision = project.last_known_good_model_revision
            project.state = WorkflowState.GENERATION_FAILED
            self.project_service.repository.save(project)
            self._save_job(job)
            recovered += 1
            logger.warning(
                "generation stage=recovered_on_startup timestamp=%s job_id=%s project_id=%s "
                "last_operation=%s progress=%s current_stage=%s",
                current_iso_timestamp(),
                job.job_id,
                job.project_id,
                job.last_operation,
                job.progress_percent,
                job.current_stage.value if hasattr(job.current_stage, "value") else job.current_stage,
            )
            self._flush_diagnostic_logs()
        return recovered

    def get_active_job_for_project(self, project_id: str) -> Optional[GenerationJob]:
        """Return currently active generation job for a project if one exists."""
        for job in self._all_persisted_jobs().values():
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

        job = self._jobs.get(job_id) or self.project_service.repository.get_generation_job(job_id)
        if job is None:
            raise APIError(
                error_id="IF-JOB-404",
                message=f"Generation job '{job_id}' not found.",
                status_code=404,
                recovery_steps=["Check the job ID or start a new generation job."],
            )

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
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        log_generation_stage("persisted_project_loaded", job_id, project_id)

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

        log_generation_stage("validation_completed", job_id, project_id)
        log_generation_stage("loft_plan_load_or_build_started", job_id, project_id)
        log_generation_stage("kcl_compile_started", job_id, project_id)
        compile_result = self.project_service.compile_kcl(project_id, project_token)
        log_generation_stage("loft_plan_load_or_build_completed", job_id, project_id)
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

        log_generation_stage("kcl_compile_completed", job_id, project_id)

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
        self._bind_operation_callback(job)
        job.record_operation("task_created")
        job.record_operation("job_persisted")
        job.record_operation("project_loaded")
        job.record_operation("loft_plan_loaded_or_built")
        job.record_operation("kcl_compile_started")
        job.record_operation("kcl_compile_completed")

        # 6. Execute job via active EngineProvider
        engine = get_engine_provider(
            project.provider_mode.value
            if hasattr(project.provider_mode, "value")
            else str(project.provider_mode)
        )
        job.status = JobStatus.RUNNING
        job.progress_percent = 0
        self._save_job(job)
        job.record_operation("task_started")
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
        self._save_job(executed_job)
        executed_job.record_operation("job_succeeded" if executed_job.status == JobStatus.SUCCEEDED else "job_failed")
        log_generation_stage(
            ("job_marked_completed" if executed_job.status == JobStatus.SUCCEEDED else "job_marked_failed"),
            executed_job.job_id,
            executed_job.project_id,
        )

        # 7. Finalize project state based on job execution result (ADR-005)
        executed_job.record_operation("project_finalization_started")
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

        executed_job.record_operation("artifact_persistence_started")
        self.project_service.repository.save(fresh_project)
        executed_job.record_operation("artifact_persistence_completed")
        executed_job.record_operation("project_finalization_completed")
        executed_job.record_operation("task_completed")
        if executed_job.status != JobStatus.SUCCEEDED:
            executed_job.record_operation("job_failed")
        return executed_job
    async def _run_background_generation(
        self,
        project_id: str,
        mock_scenario: MockScenario,
        project_token: Optional[str],
    ) -> GenerationJob:
        """Run generation and fail any persisted active job on unexpected errors."""
        try:
            return await self.start_generation_job(
                project_id=project_id,
                mock_scenario=mock_scenario,
                project_token=project_token,
            )
        except APIError:
            raise
        except BaseException:
            self._fail_unexpected_background_job(project_id)
            raise

    def _fail_unexpected_background_job(self, project_id: str) -> None:
        """Prevent an unexpected task error from leaving an active job stuck."""
        job = self.get_active_job_for_project(project_id)
        if job is None:
            return
        job.status = JobStatus.FAILED
        job.error_id = "IF-JOB-999"
        job.error_message = "Generation background task failed unexpectedly."
        job.recovery_steps = ["Retry model generation."]
        job.completed_at = current_iso_timestamp()
        job.updated_at = job.completed_at
        job.record_operation("job_failed")
        self._save_job(job)
        try:
            project = self.project_service.get_project(project_id, None)
            target_rev = next(
                (rev for rev in project.model_revisions if rev.model_revision == job.model_revision),
                None,
            )
            if target_rev:
                target_rev.status = ModelRevisionStatus.FAILED
                target_rev.warnings.append(job.error_message)
            if project.last_known_good_model_revision is not None:
                project.current_model_revision = project.last_known_good_model_revision
            else:
                project.current_model_revision = None
            project.state = WorkflowState.GENERATION_FAILED
            self.project_service.repository.save(project)
        except Exception as cleanup_error:
            logger.error(
                "generation background cleanup failed project_id=%s exception_type=%s",
                project_id,
                type(cleanup_error).__name__,
            )

    async def start_generation_job_background(
        self,
        project_id: str,
        mock_scenario: MockScenario = MockScenario.SUCCESS,
        project_token: Optional[str] = None,
    ) -> GenerationJob:
        """Start generation without holding the HTTP request open."""
        if project_id in self._active_tasks:
            active_job = self.get_active_job_for_project(project_id)
            if active_job is not None:
                raise APIError(
                    error_id="IF-JOB-409",
                    message=(
                        f"Active generation job '{active_job.job_id}' is already in progress "
                        f"for project '{project_id}'."
                    ),
                    status_code=409,
                    recovery_steps=["Wait for the active generation job to complete or cancel it."],
                )
            raise APIError(
                error_id="IF-JOB-409",
                message="A generation task is already starting for this project.",
                status_code=409,
            )

        task = asyncio.create_task(
            self._run_background_generation(
                project_id=project_id,
                mock_scenario=mock_scenario,
                project_token=project_token,
            )
        )
        self._active_tasks[project_id] = task
        task.add_done_callback(
            lambda completed_task: self._log_background_task_result(project_id, completed_task)
        )
        await asyncio.sleep(0)
        active_job = self.get_active_job_for_project(project_id)
        if active_job is not None:
            log_generation_stage(
                "background_task_started", active_job.job_id, active_job.project_id
            )
            return active_job
        if task.done():
            try:
                return task.result()
            except APIError:
                raise
            except BaseException:
                raise APIError(
                    error_id="IF-JOB-500",
                    message="Generation failed before a job could be created.",
                    status_code=500,
                    recovery_steps=["Retry model generation."],
                )
        raise APIError(
            error_id="IF-JOB-503",
            message="Generation started but its job was not persisted.",
            status_code=503,
            recovery_steps=["Retry model generation."],
        )


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
        self._save_job(cancelled_job)

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
    if _generation_job_service_instance is None or (
        _generation_job_service_instance.project_service.repository.db_path != str(settings.db_path)
    ):
        _generation_job_service_instance = GenerationJobService()
    return _generation_job_service_instance
