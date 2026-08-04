"""Tests for deterministic KCL Compiler service layer (Stage S5A)."""

from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    DimensionProvenance,
    Interface,
    Manufacturing,
    ManufacturingProcess,
    ModelRevisionStatus,
    Point2D,
    ProfileType,
    Project,
    TracedContour,
)
from app.services.kcl_compiler import (
    COMPILER_VERSION,
    compile_project_to_kcl,
)
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
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=50.0,
                provenance=DimensionProvenance.USER_ENTERED,
            )
        ]
    else:
        dims_a = [
            Dimension(
                id="width", label="Width", value=60.0, provenance=DimensionProvenance.USER_ENTERED
            ),
            Dimension(
                id="height", label="Height", value=40.0, provenance=DimensionProvenance.USER_ENTERED
            ),
        ]
        if p_type_a == ProfileType.ROUNDED_RECTANGLE:
            dims_a.append(
                Dimension(
                    id="corner_radius",
                    label="Corner Radius",
                    value=5.0,
                    provenance=DimensionProvenance.USER_ENTERED,
                )
            )

    if p_type_b == ProfileType.CIRCLE:
        dims_b = [
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=34.5,
                provenance=DimensionProvenance.USER_ENTERED,
            )
        ]
    else:
        dims_b = [
            Dimension(
                id="width", label="Width", value=50.0, provenance=DimensionProvenance.USER_ENTERED
            ),
            Dimension(
                id="height", label="Height", value=30.0, provenance=DimensionProvenance.USER_ENTERED
            ),
        ]
        if p_type_b == ProfileType.ROUNDED_RECTANGLE:
            dims_b.append(
                Dimension(
                    id="corner_radius",
                    label="Corner Radius",
                    value=4.0,
                    provenance=DimensionProvenance.USER_ENTERED,
                )
            )

    iface_a = Interface(
        id="interface_a",
        profile_type=p_type_a,
        dimensions=dims_a,
        approved=True,
        approved_at="2026-07-23T00:00:00Z",
    )
    iface_b = Interface(
        id="interface_b",
        profile_type=p_type_b,
        dimensions=dims_b,
        approved=True,
        approved_at="2026-07-23T00:00:00Z",
    )

    conn = Connection(
        mode=mode,
        length_mm=length_mm,
        offset_x_mm=offset_x,
        offset_y_mm=offset_y,
        angle_deg=angle_deg,
    )
    mfg = Manufacturing(
        process=ManufacturingProcess.FDM,
        material="PETG",
        wallThicknessMm=2.4,
        clearance_a_mm=0.3,
        clearance_b_mm=0.1,
    )

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



def test_generated_kcl_header_is_clean_ascii_and_utf8(tmp_path):
    project = create_base_approved_project()
    project.connection.extension_a_mm = 10.0
    project.connection.extension_b_mm = 12.0
    result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))
    assert result.success is True
    assert result.kcl_code is not None
    assert result.kcl_code.startswith("// InterfaceForge - Deterministic KCL Adapter Model\n")
    result.kcl_code.encode("utf-8")
    mojibake_markers = (chr(0xC3), chr(0xC2), chr(0xE2))
    assert not any(marker in result.kcl_code for marker in mojibake_markers)
    assert "// extensionAMm = 10.000" in result.kcl_code
    assert "// extensionBMm = 12.000" in result.kcl_code
    assert "// Compiler Version: 2.0.0" in result.kcl_code
    assert "// Schema Version: 0.1" in result.kcl_code
