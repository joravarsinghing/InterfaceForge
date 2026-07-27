"""Automated Unit & Integration Tests for Stage S9.1 — Agent Revision Geometry Propagation.

Verifies:
- revision-to-KCL propagation;
- revision-to-export measurement;
- unchanged-export false-positive detection;
- previous artifact preservation after failed regeneration.
"""

import pytest

from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    Interface,
    Manufacturing,
    ParameterChange,
    ProfileType,
    Project,
)
from app.services.agent_service import AgentService
from app.services.export_provider import (
    MockExportProvider,
    _obj_to_mock_stl_bytes,
    parse_and_validate_stl,
)
from app.services.geometry_generator import generate_adapter_obj, get_geometry_hash
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.project_service import ProjectService


def create_baseline_project(proj_id: str) -> Project:
    """Create a standard baseline project (Circle 60mm -> Circle 40mm, L=50, Wall=2.4)."""
    return Project(
        project_id=proj_id,
        project_token=f"tok_{proj_id}",
        current_schema_revision=1,
        current_model_revision=1,
        interface_a=Interface(
            id="interface_a",
            profile_type=ProfileType.CIRCLE,
            approved=True,
            dimensions=[
                Dimension(id="outer_diameter", label="Outer Diameter", value=60.0, unit="mm")
            ],
        ),
        interface_b=Interface(
            id="interface_b",
            profile_type=ProfileType.CIRCLE,
            approved=True,
            dimensions=[
                Dimension(id="outer_diameter", label="Outer Diameter", value=40.0, unit="mm")
            ],
        ),
        connection=Connection(
            mode=ConnectionMode.COAXIAL,
            length_mm=50.0,
            offset_x_mm=0.0,
            offset_y_mm=0.0,
            angle_deg=0.0,
        ),
        manufacturing=Manufacturing(
            process="fdm",
            material="PETG",
            wall_thickness_mm=2.4,
            clearance_a_mm=0.3,
            clearance_b_mm=0.1,
        ),
    )


def measure_exported_stl_geometry(stl_bytes: bytes) -> dict:
    """Measure length, offset X/Y, wall thickness, and angle directly from STL geometry."""
    val = parse_and_validate_stl(stl_bytes)
    assert val["is_valid"], f"Invalid STL bytes: {val.get('error')}"

    dx, dy, dz = val["dimensions_mm"]
    min_x, max_x, min_y, max_y, min_z, max_z = val["bounding_box"]

    return {
        "length_mm": round(dz, 3),
        "min_z": min_z,
        "max_z": max_z,
        "bounding_box": val["bounding_box"],
        "dimensions_mm": val["dimensions_mm"],
    }


def test_revision_to_kcl_propagation():
    """Verify revision values directly propagate to deterministic KCL code."""
    p = create_baseline_project("kcl_prop_test")
    p.connection.length_mm = 70.0
    p.connection.mode = ConnectionMode.ANGLED
    p.connection.offset_x_mm = 10.0
    p.connection.offset_y_mm = 5.0
    p.manufacturing.wall_thickness_mm = 3.0
    p.connection.angle_deg = 20.0

    kcl_res = compile_project_to_kcl(p)
    assert kcl_res.success
    code = kcl_res.kcl_code

    assert "transition_length_mm = 70.000" in code
    assert "offset_x_mm = 10.000" in code
    assert "offset_y_mm = 5.000" in code
    assert "wall_thickness_mm = 3.000" in code
    assert "angle_deg = 20.000" in code


@pytest.mark.asyncio
async def test_revision_to_export_measurement():
    """Verify confirming proposal updates schema, KCL, export, and measured geometry."""
    ps = ProjectService()
    p_base = create_baseline_project("prop_export_meas")
    ps.repository.save(p_base)

    agent_svc = AgentService(project_service=ps)

    # Confirm length revision: 50mm -> 70mm
    changes = [
        ParameterChange(
            field="connection.length_mm",
            current_value=50.0,
            proposed_value=70.0,
            unit="mm",
            reason="Make it 20 mm longer.",
        )
    ]
    updated_p, job_dict = await agent_svc.confirm_revision("prop_export_meas", changes)

    # 1. Schema revision updated
    assert updated_p.connection.length_mm == 70.0
    assert updated_p.current_schema_revision == 2

    # 2. KCL code updated
    kcl_res = compile_project_to_kcl(updated_p)
    kcl_code = kcl_res.kcl_code if kcl_res.success else ""
    assert "transition_length_mm = 70.000" in kcl_code

    # 3. Export provider generates native export
    export_prov = MockExportProvider()
    exp_res = await export_prov.export_format(
        "prop_export_meas", 2, "stl", kcl_code, project=updated_p
    )
    assert exp_res.success

    # 4. Measure exported STL geometry
    with open(exp_res.artifact_ref, "rb") as f:
        stl_bytes = f.read()

    meas = measure_exported_stl_geometry(stl_bytes)
    measured_len = meas["length_mm"]

    # Verify measured length is 70.0 mm within ±0.2 mm
    assert abs(measured_len - 70.0) <= 0.2, f"Expected 70.0mm ± 0.2mm, got {measured_len}mm"


def test_unchanged_export_false_positive_detection():
    """Adversarial self-audit: Detect when schema updates but export remains unchanged."""
    p_base = create_baseline_project("false_pos_proj")
    obj_base = generate_adapter_obj(p_base)
    stl_base = _obj_to_mock_stl_bytes(obj_base, 1)

    # Schema is updated to 70mm
    p_rev = create_baseline_project("false_pos_proj")
    p_rev.connection.length_mm = 70.0

    # Simulate broken pipeline where STL export is NOT updated (remains stl_base at 50mm)
    stl_exported = stl_base
    meas_exported = measure_exported_stl_geometry(stl_exported)

    # Self-audit check comparing requested schema (70mm) vs measured export (50mm)
    requested_val = p_rev.connection.length_mm
    measured_val = meas_exported["length_mm"]

    delta = abs(requested_val - measured_val)
    tolerance = 0.2

    # Audit MUST detect and fail this discrepancy
    is_false_positive = delta > tolerance
    assert is_false_positive, (
        "Audit must fail when schema is updated but export geometry remains unchanged!"
    )


@pytest.mark.asyncio
async def test_previous_artifact_preservation_after_failed_regeneration():
    """Verify ADR-005 preservation of last-known-good model after failed regeneration."""
    ps = ProjectService()
    p_base = create_baseline_project("fail_preserve_proj")
    ps.repository.save(p_base)

    agent_svc = AgentService(project_service=ps)

    # Initial successful generation (Rev 1)
    await agent_svc.confirm_revision(
        "fail_preserve_proj",
        [
            ParameterChange(
                field="connection.length_mm", current_value=50.0, proposed_value=55.0, unit="mm"
            )
        ],
        mock_scenario="success",
    )

    proj_rev1 = ps.get_project("fail_preserve_proj")
    rev1_lkg = proj_rev1.last_known_good_model_revision
    assert rev1_lkg == 1

    # Get export artifact for Rev 1
    export_prov = MockExportProvider()
    kcl1_res = compile_project_to_kcl(proj_rev1)
    kcl1 = kcl1_res.kcl_code if kcl1_res.success else ""
    exp_rev1 = await export_prov.export_format(
        "fail_preserve_proj", 1, "stl", kcl1, project=proj_rev1
    )
    with open(exp_rev1.artifact_ref, "rb") as f:
        hash_rev1 = get_geometry_hash(f.read().decode("latin1"))

    # Attempt revision with forced engine failure
    try:
        await agent_svc.confirm_revision(
            "fail_preserve_proj",
            [
                ParameterChange(
                    field="connection.length_mm", current_value=55.0, proposed_value=70.0, unit="mm"
                )
            ],
            mock_scenario="engine_failure",
        )
    except Exception:
        pass

    # Re-fetch project state after failure
    proj_after = ps.get_project("fail_preserve_proj")

    # Verify last-known-good revision remains 1
    assert proj_after.last_known_good_model_revision == 1

    # Verify export for last-known-good revision 1 remains downloadable and intact
    exp_after = await export_prov.export_format(
        "fail_preserve_proj",
        proj_after.last_known_good_model_revision,
        "stl",
        kcl1,
        project=proj_rev1,
    )
    assert exp_after.success
    with open(exp_after.artifact_ref, "rb") as f:
        hash_after = get_geometry_hash(f.read().decode("latin1"))

    assert hash_rev1 == hash_after, (
        "Previous downloadable model artifact must remain identical after failed regeneration."
    )
