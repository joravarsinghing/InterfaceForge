"""Tests for deterministic KCL Compiler service layer (Stage S5A)."""

import os
import math
import pytest
from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    DimensionProvenance,
    Interface,
    Manufacturing,
    ManufacturingProcess,
    ModelRevisionStatus,
    ProfileType,
    Project,
)
from app.services.kcl_compiler import COMPILER_VERSION, compile_project_to_kcl
from app.services.project_service import ProjectService


def create_base_approved_project(
    p_type_a: ProfileType = ProfileType.CIRCLE,
    p_type_b: ProfileType = ProfileType.CIRCLE,
    mode: ConnectionMode = ConnectionMode.COAXIAL,
    length_mm: float = 40.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    angle_deg: float = 0.0,
) -> Project:
    """Helper fixture creating a project with approved interfaces and valid connection settings."""
    if p_type_a == ProfileType.CIRCLE:
        dims_a = [
            Dimension(id="outer_diameter", label="Outer Diameter", value=50.0, provenance=DimensionProvenance.USER_ENTERED)
        ]
    else:
        dims_a = [
            Dimension(id="width", label="Width", value=60.0, provenance=DimensionProvenance.USER_ENTERED),
            Dimension(id="height", label="Height", value=40.0, provenance=DimensionProvenance.USER_ENTERED),
        ]
        if p_type_a == ProfileType.ROUNDED_RECTANGLE:
            dims_a.append(Dimension(id="corner_radius", label="Corner Radius", value=5.0, provenance=DimensionProvenance.USER_ENTERED))

    if p_type_b == ProfileType.CIRCLE:
        dims_b = [
            Dimension(id="outer_diameter", label="Outer Diameter", value=34.5, provenance=DimensionProvenance.USER_ENTERED)
        ]
    else:
        dims_b = [
            Dimension(id="width", label="Width", value=50.0, provenance=DimensionProvenance.USER_ENTERED),
            Dimension(id="height", label="Height", value=30.0, provenance=DimensionProvenance.USER_ENTERED),
        ]
        if p_type_b == ProfileType.ROUNDED_RECTANGLE:
            dims_b.append(Dimension(id="corner_radius", label="Corner Radius", value=4.0, provenance=DimensionProvenance.USER_ENTERED))

    iface_a = Interface(id="interface_a", profile_type=p_type_a, dimensions=dims_a, approved=True, approved_at="2026-07-23T00:00:00Z")
    iface_b = Interface(id="interface_b", profile_type=p_type_b, dimensions=dims_b, approved=True, approved_at="2026-07-23T00:00:00Z")

    conn = Connection(mode=mode, length_mm=length_mm, offset_x_mm=offset_x, offset_y_mm=offset_y, angle_deg=angle_deg)
    mfg = Manufacturing(process=ManufacturingProcess.FDM, material="PETG", wall_thickness_mm=2.4, clearance_a_mm=0.3, clearance_b_mm=0.1)

    return Project(
        project_id="test-proj-1234",
        project_token="tok_test_1234",
        schema_version="0.1",
        current_schema_revision=3,
        interface_a=iface_a,
        interface_b=iface_b,
        connection=conn,
        manufacturing=mfg,
    )


def test_circular_coaxial_compilation(tmp_path):
    project = create_base_approved_project()
    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is True
    assert result.compiler_version == COMPILER_VERSION
    assert result.schema_revision == 3
    assert result.kcl_code is not None
    assert "@settings(defaultLengthUnit = mm)" in result.kcl_code
    assert "const interface_a_outer_diameter_mm = 50.000" in result.kcl_code
    assert "const interface_b_outer_diameter_mm = 34.500" in result.kcl_code
    assert "const transition_length_mm = 40.000" in result.kcl_code
    assert "const wall_thickness_mm = 2.400" in result.kcl_code
    assert "const adapter_model = subtract(outer_solid, tools = [inner_void])" in result.kcl_code

    assert result.artifact_ref is not None
    assert result.artifact_ref.startswith("artifacts/kcl_")
    assert result.kcl_hash is not None
    assert len(result.kcl_hash) == 64
    assert result.preview_snippet is not None


def test_rectangular_coaxial_compilation(tmp_path):
    project = create_base_approved_project(
        p_type_a=ProfileType.RECTANGLE,
        p_type_b=ProfileType.ROUNDED_RECTANGLE,
        mode=ConnectionMode.COAXIAL,
    )
    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is True
    assert "const interface_a_width_mm = 60.000" in result.kcl_code
    assert "const interface_a_height_mm = 40.000" in result.kcl_code
    assert "const interface_b_width_mm = 50.000" in result.kcl_code
    assert "const interface_b_corner_radius_mm = 4.000" in result.kcl_code
    assert "tangentialArcTo" in result.kcl_code
    assert "startProfileAt" in result.kcl_code


def test_circular_offset_compilation(tmp_path):
    project = create_base_approved_project(
        mode=ConnectionMode.OFFSET,
        offset_x=15.0,
        offset_y=5.0,
    )
    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is True
    assert 'const connection_mode = "offset"' in result.kcl_code
    assert "const offset_x_mm = 15.000" in result.kcl_code
    assert "const offset_y_mm = 5.000" in result.kcl_code
    assert "center = [15.000, 5.000]" in result.kcl_code


def test_angled_compilation(tmp_path):
    project = create_base_approved_project(
        mode=ConnectionMode.ANGLED,
        offset_x=10.0,
        offset_y=0.0,
        angle_deg=15.0,
    )
    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is True
    assert 'const connection_mode = "angled"' in result.kcl_code
    assert "const angle_deg = 15.000" in result.kcl_code
    assert "const top_plane = plane(origin =" in result.kcl_code


def test_invalid_unsupported_profile(tmp_path):
    project = create_base_approved_project()
    project.interface_a.profile_type = ProfileType.TRACED_CLOSED

    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is False
    assert len(result.errors) > 0
    assert result.errors[0].id == "IF-KCL-001"


def test_non_finite_input(tmp_path):
    project = create_base_approved_project()
    project.connection.length_mm = float("nan")

    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is False
    assert len(result.errors) > 0
    assert any(e.id in ("IF-CONN-003", "IF-KCL-002", "IF-KCL-004") for e in result.errors)


def test_unapproved_prerequisites_fail(tmp_path):
    project = create_base_approved_project()
    project.interface_a.approved = False

    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert result.success is False
    assert len(result.errors) > 0
    assert result.errors[0].id == "IF-KCL-003"


def test_repeated_identical_compilation_is_deterministic(tmp_path):
    project = create_base_approved_project()

    res1 = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))
    res2 = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))

    assert res1.success is True
    assert res2.success is True
    assert res1.kcl_code == res2.kcl_code
    assert res1.kcl_hash == res2.kcl_hash


def test_project_service_kcl_compilation_does_not_mark_current():
    service = ProjectService()
    proj = service.create_project()

    # Approve interfaces and configure connection
    proj.interface_a.approved = True
    proj.interface_b.approved = True
    service.repository.save(proj)

    conn_req = type("Req", (), {
        "mode": ConnectionMode.COAXIAL,
        "length_mm": 40.0,
        "offset_x_mm": 0.0,
        "offset_y_mm": 0.0,
        "angle_deg": 0.0,
    })()
    mfg_req = type("MfgReq", (), {
        "process": ManufacturingProcess.FDM,
        "material": "PETG",
        "wall_thickness_mm": 2.4,
        "clearance_a_mm": 0.3,
        "clearance_b_mm": 0.1,
    })()
    updated_proj = service.update_connection_and_manufacturing(proj.project_id, conn_req, mfg_req)

    # Perform KCL compilation
    result = service.compile_kcl(updated_proj.project_id)

    assert result.success is True
    fresh_proj = service.get_project(updated_proj.project_id)

    # Verify model is NOT marked current because Zoo has not executed it
    assert fresh_proj.current_model_revision is None
    assert len(fresh_proj.model_revisions) == 1
    assert fresh_proj.model_revisions[0].status == ModelRevisionStatus.DRAFT
    assert fresh_proj.model_revisions[0].kcl_artifact_ref is not None
