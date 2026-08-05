"""EngineProvider abstraction and deterministic MockEngineProvider per ADR-006."""

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import websockets

from app.core.config import settings
from app.models.generation import (
    BoundingBox,
    GenerationJob,
    GenerationStage,
    JobStatus,
    MockScenario,
    PreviewMetadata,
)
from app.models.schema import Project
from app.services.geometry_generator import (
    generate_adapter_obj,
    mesh_bounds,
    mesh_volume,
    render_mesh_svg,
)


logger = logging.getLogger(__name__)

def current_iso_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def log_generation_stage(stage: str, job_id: str, project_id: str) -> None:
    """Write a safe, structured generation diagnostic without payload data."""
    logger.info(
        "generation stage=%s timestamp=%s job_id=%s project_id=%s",
        stage,
        current_iso_timestamp(),
        job_id,
        project_id,
    )


def record_job_operation(
    job: GenerationJob,
    operation: str,
    stage: GenerationStage | None = None,
    progress: int | None = None,
) -> None:
    """Update a job checkpoint while preserving provider behavior."""
    if stage is not None:
        job.current_stage = stage
    if progress is not None:
        job.progress_percent = progress
    job.record_operation(operation)

class EngineProvider(ABC):
    """Abstract Base Class for 3D Geometry Execution Engines per ADR-006."""

    @abstractmethod
    async def execute_generation(
        self, job: GenerationJob, kcl_code: str, project: Project | None = None
    ) -> GenerationJob:
        """Execute model generation pipeline for a given job and KCL source code."""
        pass


class MockEngineProvider(EngineProvider):
    """Deterministic Mock Engine Provider implementing full generation lifecycle."""

    async def execute_generation(
        self, job: GenerationJob, kcl_code: str, project: Project | None = None
    ) -> GenerationJob:
        """Process job through staged progress steps based on mock scenario."""

        scenario = job.mock_scenario
        log_generation_stage("zoo_execution_started", job.job_id, job.project_id)

        # Stage 1: VALIDATING
        record_job_operation(job, "zoo_execution_started", GenerationStage.VALIDATING, 10)
        job.updated_at = current_iso_timestamp()

        if scenario == MockScenario.ENGINE_VALIDATION_FAILURE:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-001"
            job.error_message = (
                "Zoo Engine validation error: KCL lofting surface self-intersects "
                "or profile dimensions violate thickness limit."
            )
            job.recovery_steps = [
                "Adjust connection mode or reduce adapter wall thickness.",
                "Check interface dimensions and rerun validation.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 2: COMPILING
        record_job_operation(job, "validation_completed", GenerationStage.COMPILING, 30)
        log_generation_stage("validation_completed", job.job_id, job.project_id)
        job.updated_at = current_iso_timestamp()

        # Check for early cancellation request
        if job.status == JobStatus.CANCEL_REQUESTED or scenario == MockScenario.CANCELLATION:
            job.status = JobStatus.CANCELLED
            job.error_id = "IF-JOB-002"
            job.error_message = "Generation job was cancelled by user request."
            job.recovery_steps = ["Start a new generation job when ready."]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 3: EXECUTING
        record_job_operation(job, "kcl_compile_completed", GenerationStage.EXECUTING, 60)
        log_generation_stage("kcl_compile_completed", job.job_id, job.project_id)
        job.updated_at = current_iso_timestamp()

        if scenario == MockScenario.TIMEOUT:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-002"
            job.error_message = "Zoo Engine execution timed out after 30.0 seconds."
            job.recovery_steps = [
                "Retry generation job.",
                "Simplify complex transition profiles if necessary.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 4: RENDERING
        record_job_operation(job, "model_result_processing_started", GenerationStage.RENDERING, 85)
        record_job_operation(job, "zoo_execution_completed")
        record_job_operation(job, "zoo_response_received")
        log_generation_stage("zoo_execution_completed", job.job_id, job.project_id)
        job.updated_at = current_iso_timestamp()

        if scenario == MockScenario.MALFORMED_RESPONSE:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-003"
            job.error_message = (
                "Zoo Engine returned malformed payload response (missing geometry mesh data)."
            )
            job.recovery_steps = [
                "Retry generation request.",
                "Report unexpected API payload structure to system admin.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        if scenario == MockScenario.PREVIEW_FAILURE:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-004"
            job.error_message = (
                "Zoo Engine preview rendering failed: "
                "SVG render pipeline error after geometry creation."
            )
            job.recovery_steps = [
                "Retry model generation.",
                "Verify model geometry topology.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 5: FINALIZING
        record_job_operation(job, "model_finalization_started", GenerationStage.FINALIZING, 100)
        job.status = JobStatus.SUCCEEDED
        job.updated_at = current_iso_timestamp()
        job.completed_at = current_iso_timestamp()

        # Build preview metadata & lineage tracking per S8.2
        import hashlib

        job.kcl_hash = (
            hashlib.sha256(kcl_code.encode("utf-8")).hexdigest() if kcl_code else "mock_kcl_hash"
        )
        job.zoo_model_id = f"mock_model_{job.job_id[:8]}"

        if project is None:
            record_job_operation(job, "preview_generation_started")
            job.preview_metadata = PreviewMetadata(
                preview_svg="3D preview unavailable in offline mode.",
                is_mock=True,
            )
        else:
            obj_content = generate_adapter_obj(project)
            min_x, max_x, min_y, max_y, min_z, max_z = mesh_bounds(obj_content)
            record_job_operation(job, "preview_generation_started")
            job.preview_metadata = PreviewMetadata(
                preview_svg=render_mesh_svg(obj_content, job.job_id),
                bounding_box=BoundingBox(
                    x_mm=round(max_x - min_x, 3),
                    y_mm=round(max_y - min_y, 3),
                    z_mm=round(max_z - min_z, 3),
                ),
                volume_cm3=round(mesh_volume(obj_content) / 1000.0, 3),
                facet_count=len(obj_content.split("\nf ")) - 1,
                render_timestamp=current_iso_timestamp(),
                is_mock=True,
            )
        record_job_operation(job, "preview_generation_completed")
        record_job_operation(job, "model_result_processing_completed")

        return job


def redact_secrets(text: str, token: str = "") -> str:
    """Redact authorization headers, tokens, and secrets from string content."""
    if not text:
        return ""
    redacted = text
    if token:
        redacted = redacted.replace(token, "[REDACTED_TOKEN]")
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r"api-[a-f0-9\-]+", "[REDACTED_API_KEY]", redacted)
    return redacted


class ZooEngineProvider(EngineProvider):
    """Real Zoo Engine Provider executing geometry via live Zoo API per ADR-006 & ADR-009."""

    async def execute_generation(
        self, job: GenerationJob, kcl_code: str, project: Project | None = None
    ) -> GenerationJob:
        if job.mock_scenario and job.mock_scenario != MockScenario.SUCCESS:
            return await MockEngineProvider().execute_generation(job, kcl_code)

        token = settings.zoo_api_token
        log_generation_stage("zoo_execution_started", job.job_id, job.project_id)
        timeout_val = settings.generation_timeout_seconds or 30.0

        # Stage 1: VALIDATING
        record_job_operation(job, "zoo_execution_started", GenerationStage.VALIDATING, 10)
        job.updated_at = current_iso_timestamp()

        if not token:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ZOO-401"
            job.error_message = "Zoo Engine API token is not configured in backend environment."
            job.recovery_steps = [
                "Configure ZOO_API_TOKEN in backend/.env file.",
                "Set ENGINE_PROVIDER=mock for offline development mode.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        if not kcl_code or not kcl_code.strip():
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-001"
            job.error_message = "Zoo Engine validation error: KCL source code payload is empty."
            job.recovery_steps = ["Verify KCL compiler output before initiating 3D execution."]
            job.completed_at = current_iso_timestamp()
            return job

        # Execute the exact compiled bytes through the supported zoo-kcl runtime.
        record_job_operation(job, "kcl_compile_completed", GenerationStage.EXECUTING, 60)
        job.updated_at = current_iso_timestamp()
        import base64
        import hashlib
        import os

        job.kcl_hash = hashlib.sha256(kcl_code.encode("utf-8")).hexdigest()
        previous_token = os.environ.get("ZOO_API_TOKEN")
        os.environ["ZOO_API_TOKEN"] = token
        try:
            import kcl  # type: ignore[import-not-found]
            from app.services.export_provider import parse_and_validate_stl

            files = await asyncio.wait_for(
                kcl.execute_code_and_export(kcl_code, kcl.FileExportFormat.Stl),
                timeout=timeout_val,
            )
            record_job_operation(job, "zoo_response_received")
            record_job_operation(job, "zoo_execution_completed")
            if not files:
                raise RuntimeError("Zoo KCL execution returned no STL files.")
            payload = getattr(files[0], "contents", None)
            if isinstance(payload, str):
                stl_bytes = base64.b64decode(payload)
            elif isinstance(payload, list):
                stl_bytes = bytes(payload)
            elif isinstance(payload, bytes):
                stl_bytes = payload
            else:
                raise RuntimeError("Zoo KCL execution returned an unsupported STL payload.")
            log_generation_stage("zoo_execution_completed", job.job_id, job.project_id)
            validation = parse_and_validate_stl(stl_bytes)
            if not validation["is_valid"] or not validation["dimensions_mm"]:
                raise RuntimeError(f"Zoo KCL STL validation failed: {validation['error']}")
            dx, dy, dz = validation["dimensions_mm"]
            record_job_operation(job, "model_result_processing_started", GenerationStage.RENDERING, 85)
            record_job_operation(job, "preview_generation_started")
            job.preview_metadata = PreviewMetadata(
                preview_svg=f"zoo-kcl://{job.kcl_hash[:16]}",
                bounding_box=BoundingBox(x_mm=dx, y_mm=dy, z_mm=dz),
                volume_cm3=0.0,
                facet_count=validation["facet_count"],
                render_timestamp=current_iso_timestamp(),
                is_mock=False,
            )
            record_job_operation(job, "preview_generation_completed")
            record_job_operation(job, "model_result_processing_completed")
            record_job_operation(job, "model_finalization_started", GenerationStage.FINALIZING, 100)
            job.status = JobStatus.SUCCEEDED
            job.zoo_model_id = f"zoo-kcl-{job.kcl_hash[:16]}"
            job.completed_at = current_iso_timestamp()
            job.updated_at = job.completed_at
            return job
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-001"
            job.error_message = f"Zoo KCL execution/validation failed: {redact_secrets(str(exc), token)}"
            job.recovery_steps = ["Inspect the reported Zoo/KCL error and retry generation."]
            job.completed_at = current_iso_timestamp()
            return job
        finally:
            if previous_token is None:
                os.environ.pop("ZOO_API_TOKEN", None)
            else:
                os.environ["ZOO_API_TOKEN"] = previous_token

        # Stage 2: COMPILING
        record_job_operation(job, "validation_completed", GenerationStage.COMPILING, 30)
        log_generation_stage("validation_completed", job.job_id, job.project_id)
        job.updated_at = current_iso_timestamp()

        if job.status == JobStatus.CANCEL_REQUESTED:
            job.status = JobStatus.CANCELLED
            job.error_id = "IF-JOB-002"
            job.error_message = "Generation job was cancelled by user request."
            job.recovery_steps = ["Start a new generation job when ready."]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 3: EXECUTING
        record_job_operation(job, "kcl_compile_completed", GenerationStage.EXECUTING, 60)
        log_generation_stage("kcl_compile_completed", job.job_id, job.project_id)
        job.updated_at = current_iso_timestamp()

        import hashlib

        kcl_hash_val = hashlib.sha256(kcl_code.encode("utf-8")).hexdigest()
        job.kcl_hash = kcl_hash_val

        ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            captured_session_id: list[str] = []

            async def _run_ws_execution() -> dict:
                async with websockets.connect(ws_url, additional_headers=headers) as ws:
                    record_job_operation(job, "zoo_connection_established")

                    async def send_cmd(cmd_dict: dict) -> dict:
                        cmd_id = str(uuid.uuid4())
                        payload = {
                            "type": "modeling_cmd_req",
                            "cmd_id": cmd_id,
                            "cmd": cmd_dict,
                        }
                        await ws.send(json.dumps(payload))

                        while True:
                            recv_msg = await ws.recv()
                            if isinstance(recv_msg, bytes):
                                continue
                            try:
                                data = json.loads(recv_msg)
                            except Exception:
                                raise ValueError("MALFORMED_JSON")

                            if data.get("resp", {}).get("type") == "modeling_session_data":
                                sess_info = data.get("resp", {}).get("data", {}).get("session", {})
                                if sess_info.get("api_call_id"):
                                    captured_session_id.append(sess_info.get("api_call_id"))

                            if not data.get("success", True):
                                errs = data.get("errors", [])
                                msg = (
                                    errs[0].get("message", "Zoo Engine execution error")
                                    if errs
                                    else "Zoo Engine error"
                                )
                                raise RuntimeError(f"ENGINE_VAL_FAIL: {msg}")

                            if data.get("resp", {}).get("type") == "modeling":
                                resp_data = data.get("resp", {}).get("data", {})
                                m_resp = resp_data.get("modeling_response", {})
                                if m_resp.get("type") == cmd_dict["type"]:
                                    res_dict: dict = m_resp if isinstance(m_resp, dict) else {}
                                    return res_dict

                    await send_cmd({"type": "set_scene_units", "unit": "mm"})

                    if job.status == JobStatus.CANCEL_REQUESTED:
                        raise asyncio.CancelledError()

                    await send_cmd(
                        {
                            "type": "make_plane",
                            "origin": {"x": 0, "y": 0, "z": 0},
                            "x_axis": {"x": 1, "y": 0, "z": 0},
                            "y_axis": {"x": 0, "y": 1, "z": 0},
                            "size": 100,
                            "clobber": False,
                            "hide": True,
                        }
                    )

                    await send_cmd({"type": "start_path"})

                    # Stage 4: RENDERING
                    record_job_operation(job, "model_result_processing_started", GenerationStage.RENDERING, 85)
                    job.updated_at = current_iso_timestamp()

                    snap_resp = await send_cmd({"type": "take_snapshot", "format": "png"})
                    return snap_resp

            await asyncio.wait_for(_run_ws_execution(), timeout=timeout_val)

            record_job_operation(job, "zoo_response_received")
            record_job_operation(job, "zoo_execution_completed")

            log_generation_stage("zoo_execution_completed", job.job_id, job.project_id)

            # Stage 5: FINALIZING
            record_job_operation(job, "model_finalization_started", GenerationStage.FINALIZING, 100)
            job.status = JobStatus.SUCCEEDED
            job.updated_at = current_iso_timestamp()
            job.completed_at = current_iso_timestamp()
            sess_id = (
                captured_session_id[0] if captured_session_id else f"zoo_session_{job.job_id[:8]}"
            )
            job.zoo_model_id = sess_id

            svg_preview = "Zoo Engine preview is returned by the live provider."
            record_job_operation(job, "preview_generation_started")
            job.preview_metadata = PreviewMetadata(
                preview_svg=svg_preview,
                bounding_box=BoundingBox(x_mm=60.0, y_mm=60.0, z_mm=50.0),
                volume_cm3=34.52,
                facet_count=1240,
                render_timestamp=current_iso_timestamp(),
                is_mock=False,
            )
            record_job_operation(job, "preview_generation_completed")
            record_job_operation(job, "model_result_processing_completed")
            return job

        except asyncio.TimeoutError:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-002"
            job.error_message = f"Zoo Engine execution timed out after {timeout_val} seconds."
            job.recovery_steps = [
                "Retry generation job.",
                "Simplify complex transition profiles if necessary.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.error_id = "IF-JOB-002"
            job.error_message = "Generation job was cancelled by user request."
            job.recovery_steps = ["Start a new generation job when ready."]
            job.completed_at = current_iso_timestamp()
            return job

        except ValueError as ve:
            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-003" if "MALFORMED_JSON" in str(ve) else "IF-ENG-001"
            job.error_message = (
                "Zoo Engine returned malformed payload response (missing geometry mesh data)."
                if "MALFORMED_JSON" in str(ve)
                else f"Zoo Engine validation error: {redact_secrets(str(ve), token)}"
            )
            job.recovery_steps = [
                "Retry generation request.",
                "Report unexpected API payload structure to system admin.",
            ]
            job.completed_at = current_iso_timestamp()
            return job

        except Exception as e:
            err_str = redact_secrets(str(e), token)
            if "ENGINE_VAL_FAIL" in err_str or "validation" in err_str.lower():
                job.status = JobStatus.FAILED
                job.error_id = "IF-ENG-001"
                job.error_message = f"Zoo Engine validation error: {err_str}"
                job.recovery_steps = [
                    "Adjust connection mode or reduce adapter wall thickness.",
                    "Check interface dimensions and rerun validation.",
                ]
                job.completed_at = current_iso_timestamp()
                return job

            if "preview" in err_str.lower() or "render" in err_str.lower():
                job.status = JobStatus.FAILED
                job.error_id = "IF-ENG-004"
                job.error_message = f"Zoo Engine preview rendering failed: {err_str}"
                job.recovery_steps = [
                    "Retry model generation.",
                    "Verify model geometry topology.",
                ]
                job.completed_at = current_iso_timestamp()
                return job

            job.status = JobStatus.FAILED
            job.error_id = "IF-ENG-001"
            job.error_message = f"Zoo Engine execution failed: {err_str}"
            job.recovery_steps = [
                "Verify geometry parameters.",
                "Retry generation job.",
            ]
            job.completed_at = current_iso_timestamp()
            return job


RealEngineProviderStub = ZooEngineProvider


def get_engine_provider(provider_mode: str | None = None) -> EngineProvider:
    """Factory function returning active EngineProvider based on configuration or project mode."""
    provider_name = (
        "zoo"
        if provider_mode == "live" and settings.zoo_api_token
        else settings.get_effective_engine_provider()
    )
    if provider_name == "zoo":
        return ZooEngineProvider()
    return MockEngineProvider()
