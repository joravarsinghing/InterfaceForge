"""Agent service for server-side allowlist, range validation, and confirmation gates."""

import logging
import math
import uuid
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.schema import (
    AgentProposalResult,
    Connection,
    ConnectionUpdateRequest,
    Manufacturing,
    ManufacturingUpdateRequest,
    ParameterChange,
    Project,
    ValidationIssue,
    current_iso_timestamp,
)
from app.services.agent_provider import (
    ALLOWED_REVISION_FIELDS,
    AgentProvider,
    MockAgentProvider,
    ZooAgentProvider,
)
from app.services.connection_validation import (
    validate_connection_and_manufacturing,
)
from app.services.generation_job_service import GenerationJobService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class AgentService:
    """Service orchestrating natural language model revisions per Stage S9."""

    def __init__(
        self,
        project_service: Optional[ProjectService] = None,
        generation_service: Optional[GenerationJobService] = None,
        provider: Optional[AgentProvider] = None,
    ) -> None:
        self._project_service = project_service
        self._generation_service = generation_service
        self.provider = provider or self._resolve_default_provider()

    @property
    def project_service(self) -> ProjectService:
        return self._project_service or ProjectService()

    @property
    def generation_service(self) -> GenerationJobService:
        return self._generation_service or GenerationJobService(
            project_service=self.project_service
        )

    def _resolve_default_provider(self) -> Optional[AgentProvider]:
        """Resolve the Agent independently of the geometry provider."""
        if settings.zoo_api_token and settings.zoo_api_token.strip():
            return ZooAgentProvider()
        return None

    def get_provider(self, provider_name: Optional[str] = None) -> AgentProvider:
        """Get the explicitly requested provider or the configured Zoo provider."""
        name = (provider_name or "").strip().lower()
        if name == "mock":
            return MockAgentProvider()
        if not name and self.provider is not None:
            return self.provider
        if name in {"", "zoo"}:
            if not settings.zoo_api_token or not settings.zoo_api_token.strip():
                raise APIError(
                    error_id="IF-AGENT-503",
                    status_code=503,
                    message=("Zoo Agent is unavailable because no valid Zoo API token is " "configured."),  # noqa: E501
                    recovery_steps=[
                        "Configure ZOO_API_TOKEN or explicitly request the mock provider in tests."
                    ],
                )
            if self.provider is not None and isinstance(self.provider, ZooAgentProvider):
                return self.provider
            return ZooAgentProvider()
        raise APIError(
            error_id="IF-AGENT-400",
            message=f"Unknown Agent provider '{provider_name}'.",
            recovery_steps=[
                "Use the configured Zoo Agent or explicitly request mock for offline tests."
            ],
        )

    async def propose_revision(
        self, project_id: str, prompt: str, provider_name: Optional[str] = None
    ) -> AgentProposalResult:
        """Process prompt, fetch project state, query agent, and validate proposals."""
        project = self.project_service.get_project(project_id)
        provider = self.get_provider(provider_name)
        actual_provider = "mock" if isinstance(provider, MockAgentProvider) else "zoo"
        request_id = uuid.uuid4().hex
        logger.info(
            "agent_provider=%s request_id=%s outcome=request_started", actual_provider, request_id
        )

        # 1. Query Agent Provider
        try:
            proposal = await provider.propose_revision(project, prompt)
        except Exception:
            logger.exception(
                "agent_provider=%s request_id=%s outcome=provider_error",
                actual_provider,
                request_id,
            )
            raise
        proposal.provider_used = actual_provider
        logger.info(
            "agent_provider=%s request_id=%s outcome=%s",
            actual_provider,
            request_id,
            "proposal_valid" if proposal.is_valid else "proposal_invalid",
        )

        # If proposal already rejected (e.g. prompt injection, security gate, offline error)
        if not proposal.is_valid or not proposal.changes:
            return proposal

        # 2. Server-side validation gate
        validated_changes: List[ParameterChange] = []
        blocking_errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        seen_fields: set[str] = set()

        for change in proposal.changes:
            raw_field = change.field.strip().lower()
            field = {
                "length": "connection.length_mm",
                "height": "connection.length_mm",
                "adapter height": "connection.length_mm",
                "transition height": "connection.length_mm",
                "taller": "connection.length_mm",
                "shorter": "connection.length_mm",
            }.get(raw_field, raw_field)

            # Rule A: Allowlist enforcement
            if field not in ALLOWED_REVISION_FIELDS:
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message=f"Field '{field}' is outside allowed revision parameter scope.",
                        field=field,
                        recovery_steps=[
                            "Only connection length, offsets, angle, wall thickness, "
                            "and tolerances can be revised."
                        ],
                    )
                )
                continue

            # Rule B: Duplicate field change check
            if field in seen_fields:
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message=f"Duplicate modification requested for field '{field}'.",
                        field=field,
                        recovery_steps=["Provide a single clear value for each parameter."],
                    )
                )
                continue

            seen_fields.add(field)

            # Rule C: Populate trusted current_value from project schema
            trusted_current = self._get_trusted_field_value(project, field)

            # The Agent supplies intent; the backend calculates the trusted result.
            operation = (change.operation or "").strip().lower() or None
            amount = change.amount if change.amount is not None else change.proposed_value
            if operation is not None and operation not in {"increase", "decrease", "set"}:
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message="Agent operation must be increase, decrease, or set.",
                        field=field,
                    )
                )
                continue
            if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400", message="Agent amount/value must be finite.", field=field
                    )
                )
                continue
            proposed_value = float(change.proposed_value)
            if operation == "increase":
                proposed_value = float(trusted_current) + float(amount)
            elif operation == "decrease":
                proposed_value = float(trusted_current) - float(amount)
            elif operation == "set":
                proposed_value = float(amount)
            if not math.isfinite(proposed_value) or (
                field == "connection.length_mm" and proposed_value <= 0
            ):
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message=("Resulting parameter value is invalid; connection length must be " "greater than zero."),  # noqa: E501
                        field=field,
                    )
                )
                continue

            # Unit check and normalization
            unit = "mm" if "angle" not in field else "deg"
            validated_changes.append(
                ParameterChange(
                    field=field,
                    current_value=trusted_current,
                    proposed_value=proposed_value,
                    unit=unit,
                    reason=change.reason,
                    operation=operation,
                    amount=float(amount),
                )
            )

        if blocking_errors:
            return AgentProposalResult(
                changes=validated_changes,
                summary=proposal.summary or "Validation failed for requested parameter changes.",
                is_valid=False,
                validation_errors=blocking_errors,
                validation_warnings=warnings,
                raw_response=proposal.raw_response,
                provider_used=proposal.provider_used,
            )

        # 3. Server-side geometric & manufacturing boundary check
        test_conn, test_mfg = self._apply_changes_to_cloned_config(project, validated_changes)
        val_res = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, test_conn, test_mfg
        )

        if not val_res.is_valid:
            blocking_errors.extend(val_res.blocking_errors)

        warnings.extend(val_res.warnings)

        return AgentProposalResult(
            changes=validated_changes,
            summary=proposal.summary,
            is_valid=val_res.is_valid,
            validation_errors=blocking_errors,
            validation_warnings=warnings,
            raw_response=proposal.raw_response,
            provider_used=proposal.provider_used,
        )

    async def confirm_revision(
        self,
        project_id: str,
        changes: List[ParameterChange],
        mock_scenario: str = "success",
    ) -> Tuple[Project, Dict]:
        """Confirm approved changes and invalidate derived Step 3/4 geometry.

        Preserves last-known-good model if 3D generation fails.
        """
        project = self.project_service.get_project(project_id)

        # 1. Strict Server-Side Allowlist & Validation Gate
        normalized_changes: List[ParameterChange] = []
        aliases = {
            "length": "connection.length_mm",
            "height": "connection.length_mm",
            "adapter height": "connection.length_mm",
            "transition height": "connection.length_mm",
            "taller": "connection.length_mm",
            "shorter": "connection.length_mm",
        }
        for change in changes:
            field = aliases.get(change.field.strip().lower(), change.field.strip())
            change = change.model_copy(update={"field": field})
            if field not in ALLOWED_REVISION_FIELDS:
                raise APIError(
                    error_id="IF-AGENT-400",
                    status_code=400,
                    message=(
                        f"Cannot confirm change: field '{change.field}' is outside allowed scope."
                    ),
                    recovery_steps=[
                        "Select only allowed connection/manufacturing fields for revision."
                    ],
                )
            normalized_changes.append(change)

        new_conn, new_mfg = self._apply_changes_to_cloned_config(project, normalized_changes)
        val_res = validate_connection_and_manufacturing(
            project.interface_a, project.interface_b, new_conn, new_mfg
        )

        if not val_res.is_valid:
            first_err = val_res.blocking_errors[0]
            raise APIError(
                error_id=first_err.id,
                status_code=400,
                message=f"Geometric boundary validation failed: {first_err.message}",
                recovery_steps=first_err.recovery_steps,
            )

        # 2. Update canonical project connection configuration
        conn_req = ConnectionUpdateRequest(
            mode=new_conn.mode,
            length_mm=new_conn.length_mm,
            offset_x_mm=new_conn.offset_x_mm,
            offset_y_mm=new_conn.offset_y_mm,
            angle_deg=new_conn.angle_deg,
            extension_a_mm=new_conn.extension_a_mm,
            extension_b_mm=new_conn.extension_b_mm,
        )
        mfg_req = ManufacturingUpdateRequest(
            process=new_mfg.process,
            material=new_mfg.material,
            wall_thickness_mm=new_mfg.wall_thickness_mm,
            clearance_a_mm=new_mfg.clearance_a_mm,
            clearance_b_mm=new_mfg.clearance_b_mm,
        )
        updated_project = self.project_service.update_connection_and_manufacturing(
            project_id=project_id,
            connection_req=conn_req,
            manufacturing_req=mfg_req,
        )

        # The canonical update is the revision confirmation boundary. Derived
        # geometry is deliberately invalidated; Step 3 rebuilds the preview and
        # Step 4 is the only compile/execute authority.
        updated_project.loft_plan = None
        updated_project.updated_at = current_iso_timestamp()
        self.project_service.repository.save(updated_project)
        return self.project_service.get_project(project_id), {}

    def _get_trusted_field_value(self, project: Project, field: str) -> float:
        """Lookup exact trusted current value from canonical project schema."""
        if field == "connection.length_mm":
            return project.connection.length_mm
        elif field == "connection.offset_x_mm":
            return project.connection.offset_x_mm
        elif field == "connection.offset_y_mm":
            return project.connection.offset_y_mm
        elif field == "connection.angle_deg":
            return project.connection.angle_deg
        elif field == "manufacturing.wall_thickness_mm":
            return project.manufacturing.wall_thickness_mm
        elif field == "manufacturing.clearance_a_mm":
            return project.manufacturing.clearance_a_mm
        elif field == "manufacturing.clearance_b_mm":
            return project.manufacturing.clearance_b_mm
        else:
            raise ValueError(f"Unknown field: {field}")

    def _apply_changes_to_cloned_config(
        self, project: Project, changes: List[ParameterChange]
    ) -> Tuple[Connection, Manufacturing]:
        """Apply parameter changes to a cloned Connection and Manufacturing object."""
        conn_dict = project.connection.model_dump()
        mfg_dict = project.manufacturing.model_dump()

        for c in changes:
            field_name = c.field.split(".")[-1]
            current = (conn_dict if c.field.startswith("connection.") else mfg_dict).get(field_name)
            amount = c.amount if c.amount is not None else c.proposed_value
            if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
                raise APIError(
                    error_id="IF-AGENT-400",
                    message=f"Parameter value for '{c.field}' must be finite.",
                )
            operation = (c.operation or "").strip().lower()
            if operation == "increase":
                value = float(current) + float(amount)
            elif operation == "decrease":
                value = float(current) - float(amount)
            elif operation == "set":
                value = float(amount)
            else:
                value = float(c.proposed_value)
            if not math.isfinite(value) or (c.field == "connection.length_mm" and value <= 0):
                raise APIError(
                    error_id="IF-AGENT-400", message=f"Resulting value for '{c.field}' is invalid."
                )
            if c.field.startswith("connection."):
                conn_dict[field_name] = value
            elif c.field.startswith("manufacturing."):
                mfg_dict[field_name] = value

        # Automatically infer connection mode based on revised parameters
        if abs(float(conn_dict.get("angle_deg", 0.0))) > 1e-6:
            conn_dict["mode"] = "angled"
        elif (
            abs(float(conn_dict.get("offset_x_mm", 0.0))) > 1e-6
            or abs(float(conn_dict.get("offset_y_mm", 0.0))) > 1e-6
        ):
            conn_dict["mode"] = "offset"
        else:
            conn_dict["mode"] = "coaxial"

        return Connection(**conn_dict), Manufacturing(**mfg_dict)


_agent_service_instance: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Singleton getter for AgentService."""
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = AgentService()
    return _agent_service_instance
