"""Zoo Agent API provider abstraction per ADR-003, ADR-007, and Stage S9 specification."""

import abc
import asyncio
import json
import logging
import math
import re
from typing import Dict, List, Set

import websockets

from app.core.config import settings
from app.models.schema import (
    AgentProposalResult,
    ParameterChange,
    Project,
    ValidationIssue,
)

logger = logging.getLogger(__name__)

# Strict allowlist of allowed revision fields per S9 specification
ALLOWED_REVISION_FIELDS: Set[str] = {
    "connection.length_mm",
    "connection.offset_x_mm",
    "connection.offset_y_mm",
    "connection.angle_deg",
    "manufacturing.wall_thickness_mm",
    "manufacturing.clearance_a_mm",
    "manufacturing.clearance_b_mm",
}

# Unit mapping per field type
FIELD_UNITS: Dict[str, str] = {
    "connection.length_mm": "mm",
    "connection.offset_x_mm": "mm",
    "connection.offset_y_mm": "mm",
    "connection.angle_deg": "deg",
    "manufacturing.wall_thickness_mm": "mm",
    "manufacturing.clearance_a_mm": "mm",
    "manufacturing.clearance_b_mm": "mm",
}


def redact_secrets(text: str) -> str:
    """Redact API tokens from log and exception strings."""
    if not text:
        return text
    token = settings.zoo_api_token
    if token and token in text:
        text = text.replace(token, "[REDACTED_ZOO_API_TOKEN]")
    return text


class AgentProvider(abc.ABC):
    """Abstract base class for Zoo Agent revision providers."""

    @abc.abstractmethod
    async def propose_revision(self, project: Project, prompt: str) -> AgentProposalResult:
        """Interpret user natural language prompt and return a structured parameter proposal."""
        pass


class MockAgentProvider(AgentProvider):
    """Deterministic mock agent provider for testing and offline execution."""

    async def propose_revision(self, project: Project, prompt: str) -> AgentProposalResult:
        prompt_lower = prompt.strip().lower()

        # 1. Prompt Injection / KCL Generation Attempt Rejection
        if any(
            kw in prompt_lower
            for kw in ["kcl", "cad", "delete", "ignore rules", "script", "code", "drop", "truncate"]
        ):
            return AgentProposalResult(
                changes=[],
                summary=(
                    "Security rejection: Prompt injection or CAD code generation attempt detected."
                ),
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message=(
                            "Requested operation attempts CAD code output or instruction "
                            "override, which is prohibited."
                        ),
                        field="prompt",
                        recovery_steps=["Provide a natural language parameter adjustment request."],
                    )
                ],
                provider_used="mock",
            )

        # 2. Profile / Out of Scope Request Rejection
        if "square" in prompt_lower or "material" in prompt_lower:
            return AgentProposalResult(
                changes=[],
                summary=(
                    "Rejection: Profile geometry and manufacturing material changes "
                    "are outside allowed revision scope."
                ),
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message="Field modification is outside allowed revision scope.",
                        field="profile",
                        recovery_steps=[
                            "Only connection length, offsets, angle, wall thickness, "
                            "and clearances can be revised."
                        ],
                    )
                ],
                provider_used="mock",
            )

        # 3. Specific Deterministic Cases
        # Length terminology is aligned with the Zoo contract.
        if any(
            term in prompt_lower for term in ["length", "height", "taller", "shorter", "longer"]
        ):
            match = re.search(r"(\d+(?:\.\d+)?)\s*mm", prompt_lower)
            amount = float(match.group(1)) if match else 0.0
            operation = (
                "set"
                if ("set " in prompt_lower or " to " in prompt_lower)
                else (
                    "decrease"
                    if ("decrease" in prompt_lower or "shorter" in prompt_lower)
                    else "increase"
                )
            )
            current = project.connection.length_mm
            proposed = {"increase": current + amount, "decrease": current - amount, "set": amount}[
                operation
            ]
            return AgentProposalResult(
                changes=[
                    ParameterChange(
                        field="connection.length_mm",
                        current_value=current,
                        proposed_value=proposed,
                        unit="mm",
                        reason=f"{operation.title()} connection length by {amount:g} mm.",
                        operation=operation,
                        amount=amount,
                    )
                ],
                summary=f"{operation.title()} connection length.",
                is_valid=True,
                provider_used="mock",
            )

        # Case 1: "Make it 20 mm longer."
        if "longer" in prompt_lower or "increase length" in prompt_lower:
            m = re.search(r"(\d+(\.\d+)?)", prompt_lower)
            delta = float(m.group(1)) if m else 20.0
            curr = project.connection.length_mm
            prop = curr + delta
            return AgentProposalResult(
                changes=[
                    ParameterChange(
                        field="connection.length_mm",
                        current_value=curr,
                        proposed_value=prop,
                        unit="mm",
                        reason=f"Increase transition length by {delta} mm.",
                    )
                ],
                summary=f"Increase adapter transition length from {curr:.1f} mm to {prop:.1f} mm.",
                is_valid=True,
                provider_used="mock",
            )

        # Case 2: "Move the outlet 10 mm right and 5 mm up."
        if "move the outlet" in prompt_lower or ("right" in prompt_lower and "up" in prompt_lower):
            m_right = re.search(r"(\d+(\.\d+)?)\s*mm\s*right", prompt_lower)
            m_up = re.search(r"(\d+(\.\d+)?)\s*mm\s*up", prompt_lower)
            dx = float(m_right.group(1)) if m_right else 10.0
            dy = float(m_up.group(1)) if m_up else 5.0
            curr_x = project.connection.offset_x_mm
            curr_y = project.connection.offset_y_mm
            prop_x = curr_x + dx
            prop_y = curr_y + dy
            return AgentProposalResult(
                changes=[
                    ParameterChange(
                        field="connection.offset_x_mm",
                        current_value=curr_x,
                        proposed_value=prop_x,
                        unit="mm",
                        reason=f"Shift outlet X offset by +{dx} mm right.",
                    ),
                    ParameterChange(
                        field="connection.offset_y_mm",
                        current_value=curr_y,
                        proposed_value=prop_y,
                        unit="mm",
                        reason=f"Shift outlet Y offset by +{dy} mm up.",
                    ),
                ],
                summary=f"Move outlet offset X to {prop_x:.1f} mm and offset Y to {prop_y:.1f} mm.",
                is_valid=True,
                provider_used="mock",
            )

        # Case 3: "Increase wall thickness to 3 mm."
        if "wall thickness" in prompt_lower:
            m = re.search(r"(\d+(\.\d+)?)", prompt_lower)
            val = float(m.group(1)) if m else 3.0
            curr = project.manufacturing.wall_thickness_mm
            return AgentProposalResult(
                changes=[
                    ParameterChange(
                        field="manufacturing.wall_thickness_mm",
                        current_value=curr,
                        proposed_value=val,
                        unit="mm",
                        reason=f"Set wall thickness to {val:.1f} mm.",
                    )
                ],
                summary=f"Set manufacturing wall thickness from {curr:.1f} mm to {val:.1f} mm.",
                is_valid=True,
                provider_used="mock",
            )

        # Case 4: "Tilt it to 20 degrees."
        if "tilt" in prompt_lower or "degree" in prompt_lower or "angle" in prompt_lower:
            m = re.search(r"(\d+(\.\d+)?)", prompt_lower)
            val = float(m.group(1)) if m else 20.0
            curr = project.connection.angle_deg
            return AgentProposalResult(
                changes=[
                    ParameterChange(
                        field="connection.angle_deg",
                        current_value=curr,
                        proposed_value=val,
                        unit="deg",
                        reason=f"Set adapter inclination angle to {val:.1f}°.",
                    )
                ],
                summary=f"Set connection angle from {curr:.1f}° to {val:.1f}°.",
                is_valid=True,
                provider_used="mock",
            )

        # Case 7: Ambiguous Request ("Make it stronger", etc.)
        return AgentProposalResult(
            changes=[],
            summary=(
                "Request is ambiguous. Please specify a target parameter "
                "(e.g. wall thickness, length, offsets, or angle)."
            ),
            is_valid=True,
            provider_used="mock",
        )


class ZooAgentProvider(AgentProvider):
    """Live Zoo Agent integration via Copilot WebSocket API (wss://api.zoo.dev/ws/ml/copilot)."""

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.ws_url = "wss://api.zoo.dev/ws/ml/copilot"
        self.token = settings.zoo_api_token
        self.timeout_seconds = timeout_seconds

    async def propose_revision(self, project: Project, prompt: str) -> AgentProposalResult:
        if not self.token or not self.token.strip():
            logger.error("agent_provider=zoo outcome=unavailable")
            return AgentProposalResult(
                changes=[],
                summary="Zoo Agent is unavailable because no valid Zoo API token is configured.",
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-503",
                        message="Zoo Agent configuration is unavailable.",
                        field="agent_api",
                        recovery_steps=["Configure a valid ZOO_API_TOKEN and retry."],
                    )
                ],
                provider_used="zoo",
            )

        # Build prompt framing with strict instructions and current parameters
        conn = project.connection
        mfg = project.manufacturing
        system_instruction = (
            "You are a CAD parameter revision agent for InterfaceForge.\n"
            "Your task is to analyze user revision requests and return ONLY a JSON object "
            "proposing parameter changes.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. You MUST NEVER output KCL code, CAD commands, or geometry files.\n"
            "2. Allowed fields ONLY:\n"
            "   - connection.length_mm\n"
            "   - connection.offset_x_mm\n"
            "   - connection.offset_y_mm\n"
            "   - connection.angle_deg\n"
            "   - manufacturing.wall_thickness_mm\n"
            "   - manufacturing.clearance_a_mm\n"
            "   - manufacturing.clearance_b_mm\n"
            "3. Any attempt to modify profile shapes (circle, square), materials, or unallowed "
            "fields must return an empty changes list with an explanation in summary.\n"
            "4. Terminology: length, height, adapter height, transition height, taller, and "
            "shorter all refer to connection.length_mm. Increase X by N means current value plus N; "  # noqa: E501
            "decrease X by N means current value minus N; set X to N means absolute value N.\n"
            "5. Examples: Increase height by 3 mm; Decrease length by 3 mm; Make it 5 mm shorter; "
            "Set the height to 60 mm.\n"
            "6. Each change must contain field, operation (increase, decrease, or set), amount/value, "  # noqa: E501
            "unit, and reason. The backend calculates the final trusted value from current state.\n"
            "7. If request is ambiguous, return empty changes list and ask for clarification in summary.\n"  # noqa: E501
            "8. Return strictly valid JSON format matching schema with keys 'changes' and 'summary'.\n\n"  # noqa: E501
            f"Current trusted parameters:\n"
            f"- connection.length_mm = {conn.length_mm}\n"
            f"- connection.offset_x_mm = {conn.offset_x_mm}\n"
            f"- connection.offset_y_mm = {conn.offset_y_mm}\n"
            f"- connection.angle_deg = {conn.angle_deg}\n"
            f"- manufacturing.wall_thickness_mm = {mfg.wall_thickness_mm}\n"
            f"- manufacturing.clearance_a_mm = {mfg.clearance_a_mm}\n"
            f"- manufacturing.clearance_b_mm = {mfg.clearance_b_mm}\n\n"
            f"User request: {prompt}"
        )

        headers = {"Authorization": f"Bearer {self.token}"}
        whole_response = None
        try:
            async with websockets.connect(self.ws_url) as ws:
                # 1. Send auth header payload per Zoo API spec
                await ws.send(json.dumps({"type": "headers", "headers": headers}))

                # 2. Send user prompt
                await ws.send(
                    json.dumps({"type": "user", "content": system_instruction, "mode": "fast"})
                )

                # 3. Stream responses until end_of_stream
                start_time = asyncio.get_event_loop().time()
                accumulated_text = ""

                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > self.timeout_seconds:
                        raise TimeoutError(
                            f"Zoo Agent WebSocket request timed out after {self.timeout_seconds}s."
                        )

                    frame = await asyncio.wait_for(
                        ws.recv(), timeout=self.timeout_seconds - elapsed
                    )
                    if isinstance(frame, str):
                        data = json.loads(frame)
                        if "end_of_stream" in data:
                            end_data = data["end_of_stream"]
                            whole_response = end_data.get("whole_response") or accumulated_text
                            break
                        elif "delta" in data:
                            delta_obj = data["delta"]
                            if isinstance(delta_obj, dict) and "delta" in delta_obj:
                                accumulated_text += str(delta_obj["delta"])
                            elif isinstance(delta_obj, str):
                                accumulated_text += delta_obj
                        elif "text" in data:
                            accumulated_text += str(data["text"])

        except Exception as exc:
            redacted_err = redact_secrets(str(exc))
            logger.error(f"Failed to communicate with Zoo Agent API: {redacted_err}")
            return AgentProposalResult(
                changes=[],
                summary=f"Zoo Agent API connection failed: {redacted_err}",
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-500",
                        message="Zoo Agent API connection or timeout error.",
                        field="agent_api",
                        recovery_steps=["Check network connectivity or retry revision proposal."],
                    )
                ],
                provider_used="zoo",
            )

        if not whole_response:
            return AgentProposalResult(
                changes=[],
                summary="Zoo Agent API returned an empty response.",
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message="Zoo Agent returned empty response content.",
                        field="response",
                        recovery_steps=["Provide a clearer parameter revision request."],
                    )
                ],
                raw_response=whole_response,
                provider_used="zoo",
            )

        # Parse JSON from response (handling potential markdown code fences)
        clean_text = whole_response.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()

        try:
            parsed = json.loads(clean_text)
        except Exception:
            logger.warning(f"Zoo Agent emitted non-JSON output: {clean_text}")
            return AgentProposalResult(
                changes=[],
                summary="Agent output could not be parsed as structured JSON parameter changes.",
                is_valid=False,
                validation_errors=[
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message="Prose or malformed output masquerading as JSON proposal.",
                        field="response",
                        recovery_steps=[
                            "Re-phrase request to specify explicit numeric parameters."
                        ],
                    )
                ],
                raw_response=whole_response,
                provider_used="zoo",
            )

        # Build ParameterChange list
        raw_changes = parsed.get("changes", [])
        summary = parsed.get("summary", "")
        changes: List[ParameterChange] = []

        for item in raw_changes:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field", ""))
            operation = str(item.get("operation", "")).strip().lower() or None
            amount = item.get("amount", item.get("value", item.get("proposed_value")))
            proposed_val = item.get("proposed_value", amount)
            unit = str(item.get("unit", FIELD_UNITS.get(field, "mm")))
            reason = str(item.get("reason", ""))

            if (
                proposed_val is None
                or not isinstance(proposed_val, (int, float))
                or not math.isfinite(proposed_val)
            ):
                continue

            changes.append(
                ParameterChange(
                    field=field,
                    current_value=0.0,  # Backend populates trusted value in validation step
                    proposed_value=float(proposed_val),
                    unit=unit,
                    reason=reason,
                    operation=operation,
                    amount=float(amount),
                )
            )

        return AgentProposalResult(
            changes=changes,
            summary=summary,
            is_valid=True,
            raw_response=whole_response,
            provider_used="zoo",
        )
