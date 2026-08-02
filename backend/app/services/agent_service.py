"""Agent service for server-side allowlist, range validation, and confirmation gates."""

import logging
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import APIError
from app.models.generation import MockScenario
from app.models.schema import (
    AgentProposalResult,
    Connection,
    ConnectionUpdateRequest,
    Manufacturing,
    ManufacturingUpdateRequest,
    ParameterChange,
    Project,
    ValidationIssue,
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
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.project_service import ProjectService
from app.services.loft_plan import ensure_loft_plan

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

    def _resolve_default_provider(self) -> AgentProvider:
        """Resolve active agent provider based on settings."""

        # Use ZooAgentProvider if ZOO_API_TOKEN is configured and ENGINE_PROVIDER != mock
        if settings.zoo_api_token and settings.zoo_api_token.startswith("api-"):
            return ZooAgentProvider()
        return MockAgentProvider()

    def get_provider(self, provider_name: Optional[str] = None) -> AgentProvider:
        """Get requested or default provider."""
        if provider_name == "zoo":
            return ZooAgentProvider()
        elif provider_name == "mock":
            return MockAgentProvider()
        return self.provider

    async def propose_revision(
        self, project_id: str, prompt: str, provider_name: Optional[str] = None
    ) -> AgentProposalResult:
        """Process prompt, fetch project state, query agent, and validate proposals."""
        project = self.project_service.get_project(project_id)
        provider = self.get_provider(provider_name)

        # 1. Query Agent Provider
        proposal = await provider.propose_revision(project, prompt)

        # If proposal already rejected (e.g. prompt injection, security gate, offline error)
        if not proposal.is_valid or not proposal.changes:
            return proposal

        # 2. Server-side validation gate
        validated_changes: List[ParameterChange] = []
        blocking_errors: List[ValidationIssue] = []
        warnings: List[ValidationIssue] = []
        seen_fields: set[str] = set()

        for change in proposal.changes:
            field = change.field.strip()

            # Rule A: Allowlist enforcement
            if field not in ALLOWED_REVISION_FIELDS:
                blocking_errors.append(
                    ValidationIssue(
                        id="IF-AGENT-400",
                        message=f"Field '{field}' is outside allowed revision parameter scope.",
                        field=field,
                        recovery_steps=[
                            "Only connection length, offsets, angle, wall thickness, "
                            "and clearances can be revised."
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

            # Unit check and normalization
            unit = "mm" if "angle" not in field else "deg"

            validated_changes.append(
                ParameterChange(
                    field=field,
                    current_value=trusted_current,
                    proposed_value=change.proposed_value,
                    unit=unit,
                    reason=change.reason,
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
        """Confirm approved parameter changes, patch schema, recompile KCL, and start 3D generation.

        Preserves last-known-good model if 3D generation fails.
        """
        project = self.project_service.get_project(project_id)

        # 1. Strict Server-Side Allowlist & Validation Gate
        for change in changes:
            if change.field not in ALLOWED_REVISION_FIELDS:
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

        new_conn, new_mfg = self._apply_changes_to_cloned_config(project, changes)
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

        # 3. Rebuild the derived LoftPlan from the newly updated canonical config,
        # then compile the regenerated KCL before starting Zoo Engine generation.
        updated_project.loft_plan = None
        ensure_loft_plan(updated_project)
        compile_result = compile_project_to_kcl(updated_project)
        if not compile_result.success or not compile_result.kcl_code:
            issue = compile_result.errors[0] if compile_result.errors else None
            raise APIError(
                error_id=issue.id if issue else "IF-KCL-400",
                status_code=400,
                message=issue.message if issue else "KCL recompilation failed after revision confirmation.",
                details={"compiler_errors": [e.model_dump() for e in compile_result.errors]},
                recovery_steps=issue.recovery_steps if issue else ["Retry the revision after correcting the design parameters."],
            )

        # 4. Initiate 3D Generation Job. The job reloads the persisted canonical
        # project and compiles that same regenerated KCL as its authoritative input.
        job = await self.generation_service.start_generation_job(
            project_id=project_id,
            mock_scenario=MockScenario(mock_scenario),
        )

        # Re-fetch project to return latest state
        current_project = self.project_service.get_project(project_id)

        return current_project, job.model_dump()

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
            if c.field.startswith("connection."):
                conn_dict[field_name] = float(c.proposed_value)
            elif c.field.startswith("manufacturing."):
                mfg_dict[field_name] = float(c.proposed_value)

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
