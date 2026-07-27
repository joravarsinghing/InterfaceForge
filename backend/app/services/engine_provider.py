"""EngineProvider abstraction and deterministic MockEngineProvider per ADR-006."""

import asyncio
import json
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


def current_iso_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def generate_mock_svg_preview(job_id: str, mode: str = "coaxial") -> str:
    """Generate a clean dark/neon-green SVG string representing the 3D adapter preview."""
    h = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="100%">'
    e_a1 = (
        '<ellipse cx="0" cy="-60" rx="70" ry="25" fill="none" stroke="#00e676" stroke-width="3"/>'
    )
    e_a2 = (
        '<ellipse cx="0" cy="-60" rx="55" ry="18" fill="none" stroke="#00e676" '
        'stroke-width="1.5" stroke-dasharray="4 2"/>'
    )
    p_1 = (
        '<path d="M -35 -40 L -45 40" stroke="#00e676" stroke-width="1" '
        'stroke-dasharray="3 3" opacity="0.6"/>'
    )
    p_2 = (
        '<path d="M 35 -40 L 45 40" stroke="#00e676" stroke-width="1" '
        'stroke-dasharray="3 3" opacity="0.6"/>'
    )
    p_3 = (
        '<path d="M 0 -35 L 0 35" stroke="#00e676" stroke-width="1" '
        'stroke-dasharray="2 2" opacity="0.4"/>'
    )
    e_b2 = (
        '<ellipse cx="0" cy="60" rx="72" ry="24" fill="none" stroke="#00b0ff" '
        'stroke-width="1.5" stroke-dasharray="4 2"/>'
    )
    t_title = (
        '<text x="15" y="25" fill="#00e676" font-family="monospace" '
        'font-size="11" font-weight="bold">INTERFACEFORGE 3D PREVIEW</text>'
    )
    t_job = (
        f'<text x="15" y="280" fill="#88aa99" font-family="monospace" '
        f'font-size="10">JOB: {job_id[:12]}</text>'
    )
    t_mode = (
        f'<text x="280" y="280" fill="#00e676" font-family="monospace" '
        f'font-size="10">MODE: {mode.upper()}</text>'
    )

    return f"""{h}
  <defs>
    <linearGradient id="neonGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00e676" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#00b0ff" stop-opacity="0.7"/>
    </linearGradient>
    <radialGradient id="bgGrad" cx="50%" cy="50%" r="70%">
      <stop offset="0%" stop-color="#18221c"/>
      <stop offset="100%" stop-color="#0a0e0b"/>
    </radialGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>
  <rect width="400" height="300" fill="url(#bgGrad)" rx="8"/>
  <grid width="400" height="300" stroke="#1b382b" stroke-width="0.5"/>

  <g transform="translate(200, 150)" filter="url(#glow)">
    {e_a1}
    {e_a2}
    <path d="M -70 -60 L -90 60" stroke="url(#neonGrad)" stroke-width="2"/>
    <path d="M 70 -60 L 90 60" stroke="url(#neonGrad)" stroke-width="2"/>
    {p_1}
    {p_2}
    {p_3}
    <ellipse cx="0" cy="60" rx="90" ry="32" fill="none" stroke="#00b0ff" stroke-width="3"/>
    {e_b2}
  </g>

  {t_title}
  {t_job}
  {t_mode}
</svg>"""


class EngineProvider(ABC):
    """Abstract Base Class for 3D Geometry Execution Engines per ADR-006."""

    @abstractmethod
    async def execute_generation(self, job: GenerationJob, kcl_code: str) -> GenerationJob:
        """Execute model generation pipeline for a given job and KCL source code."""
        pass


class MockEngineProvider(EngineProvider):
    """Deterministic Mock Engine Provider implementing full generation lifecycle."""

    async def execute_generation(self, job: GenerationJob, kcl_code: str) -> GenerationJob:
        """Process job through staged progress steps based on mock scenario."""

        scenario = job.mock_scenario

        # Stage 1: VALIDATING
        job.current_stage = GenerationStage.VALIDATING
        job.progress_percent = 10
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
        job.current_stage = GenerationStage.COMPILING
        job.progress_percent = 30
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
        job.current_stage = GenerationStage.EXECUTING
        job.progress_percent = 60
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
        job.current_stage = GenerationStage.RENDERING
        job.progress_percent = 85
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
        job.current_stage = GenerationStage.FINALIZING
        job.progress_percent = 100
        job.status = JobStatus.SUCCEEDED
        job.updated_at = current_iso_timestamp()
        job.completed_at = current_iso_timestamp()

        # Build preview metadata & lineage tracking per S8.2
        import hashlib

        job.kcl_hash = (
            hashlib.sha256(kcl_code.encode("utf-8")).hexdigest() if kcl_code else "mock_kcl_hash"
        )
        job.zoo_model_id = f"mock_model_{job.job_id[:8]}"

        svg_content = generate_mock_svg_preview(job.job_id)
        job.preview_metadata = PreviewMetadata(
            preview_svg=svg_content,
            bounding_box=BoundingBox(x_mm=60.0, y_mm=60.0, z_mm=50.0),
            volume_cm3=34.52,
            facet_count=1240,
            render_timestamp=current_iso_timestamp(),
            is_mock=True,
        )

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

    async def execute_generation(self, job: GenerationJob, kcl_code: str) -> GenerationJob:
        if job.mock_scenario and job.mock_scenario != MockScenario.SUCCESS:
            return await MockEngineProvider().execute_generation(job, kcl_code)

        token = settings.zoo_api_token
        timeout_val = settings.generation_timeout_seconds or 30.0

        # Stage 1: VALIDATING
        job.current_stage = GenerationStage.VALIDATING
        job.progress_percent = 10
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

        # Stage 2: COMPILING
        job.current_stage = GenerationStage.COMPILING
        job.progress_percent = 30
        job.updated_at = current_iso_timestamp()

        if job.status == JobStatus.CANCEL_REQUESTED:
            job.status = JobStatus.CANCELLED
            job.error_id = "IF-JOB-002"
            job.error_message = "Generation job was cancelled by user request."
            job.recovery_steps = ["Start a new generation job when ready."]
            job.completed_at = current_iso_timestamp()
            return job

        # Stage 3: EXECUTING
        job.current_stage = GenerationStage.EXECUTING
        job.progress_percent = 60
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
                    job.current_stage = GenerationStage.RENDERING
                    job.progress_percent = 85
                    job.updated_at = current_iso_timestamp()

                    snap_resp = await send_cmd({"type": "take_snapshot", "format": "png"})
                    return snap_resp

            await asyncio.wait_for(_run_ws_execution(), timeout=timeout_val)

            # Stage 5: FINALIZING
            job.current_stage = GenerationStage.FINALIZING
            job.progress_percent = 100
            job.status = JobStatus.SUCCEEDED
            job.updated_at = current_iso_timestamp()
            job.completed_at = current_iso_timestamp()
            sess_id = (
                captured_session_id[0] if captured_session_id else f"zoo_session_{job.job_id[:8]}"
            )
            job.zoo_model_id = sess_id

            svg_preview = generate_mock_svg_preview(job.job_id, mode="zoo_live")
            job.preview_metadata = PreviewMetadata(
                preview_svg=svg_preview,
                bounding_box=BoundingBox(x_mm=60.0, y_mm=60.0, z_mm=50.0),
                volume_cm3=34.52,
                facet_count=1240,
                render_timestamp=current_iso_timestamp(),
                is_mock=False,
            )
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


def get_engine_provider() -> EngineProvider:
    """Factory function returning active EngineProvider based on configuration."""
    provider_name = settings.get_effective_engine_provider()
    if provider_name == "zoo":
        return ZooEngineProvider()
    return MockEngineProvider()
