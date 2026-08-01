"""Backend unit and integration tests for connection configuration (S4C)."""

from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    DimensionProvenance,
    Interface,
    Manufacturing,
    ManufacturingProcess,
    ProfileType,
)
from app.services.connection_validation import validate_connection_and_manufacturing
from app.services.project_service import ProjectService


def create_approved_interface(
    interface_id: str, profile_type: ProfileType = ProfileType.CIRCLE
) -> Interface:
    """Helper to construct a structurally valid and approved interface."""
    dims = [
        Dimension(
            id="outer_diameter",
            label="Outer Diameter",
            value=50.0,
            unit="mm",
            provenance=DimensionProvenance.USER_ENTERED,
            confidence=1.0,
            critical=True,
        ),
        Dimension(
            id="wall_thickness",
            label="Wall Thickness",
            value=5.0,
            unit="mm",
            provenance=DimensionProvenance.USER_ENTERED,
            confidence=1.0,
            critical=False,
        ),
    ]
    if profile_type in (ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE):
        dims = [
            Dimension(
                id="width",
                label="Width",
                value=40.0,
                unit="mm",
                provenance=DimensionProvenance.USER_ENTERED,
                confidence=1.0,
                critical=True,
            ),
            Dimension(
                id="height",
                label="Height",
                value=30.0,
                unit="mm",
                provenance=DimensionProvenance.USER_ENTERED,
                confidence=1.0,
                critical=True,
            ),
        ]
    return Interface(
        id=interface_id,
        profile_type=profile_type,
        dimensions=dims,
        approved=True,
        approved_at="2026-07-23T00:00:00Z",
    )


def test_validate_all_three_valid_modes():
    """Verify coaxial, offset, and angled modes pass validation within bounds."""
    iface_a = create_approved_interface("interface_a", ProfileType.CIRCLE)
    iface_b = create_approved_interface("interface_b", ProfileType.RECTANGLE)

    # 1. Coaxial
    conn_coaxial = Connection(
        mode=ConnectionMode.COAXIAL,
        length_mm=40.0,
        offset_x_mm=0.0,
        offset_y_mm=0.0,
        angle_deg=0.0,
    )
    mfg = Manufacturing(
        process=ManufacturingProcess.FDM,
        material="PETG",
        wall_thickness_mm=2.4,
        clearance_a_mm=0.3,
        clearance_b_mm=0.1,
    )

    res_coaxial = validate_connection_and_manufacturing(iface_a, iface_b, conn_coaxial, mfg)
    assert res_coaxial.is_valid is True
    assert len(res_coaxial.blocking_errors) == 0

    # 2. Offset
    conn_offset = Connection(
        mode=ConnectionMode.OFFSET,
        length_mm=50.0,
        offset_x_mm=10.0,
        offset_y_mm=5.0,
        angle_deg=0.0,
    )
    res_offset = validate_connection_and_manufacturing(iface_a, iface_b, conn_offset, mfg)
    assert res_offset.is_valid is True
    assert len(res_offset.blocking_errors) == 0

    # 3. Angled
    conn_angled = Connection(
        mode=ConnectionMode.ANGLED,
        length_mm=60.0,
        offset_x_mm=10.0,
        offset_y_mm=5.0,
        angle_deg=15.0,
    )
    res_angled = validate_connection_and_manufacturing(iface_a, iface_b, conn_angled, mfg)
    assert res_angled.is_valid is True
    assert len(res_angled.blocking_errors) == 0

def test_large_coaxial_profiles_do_not_trigger_motion_self_intersection_check():
    """Coaxial geometry has no transition motion, even for large profiles."""
    iface_a = create_approved_interface("interface_a", ProfileType.CIRCLE)
    iface_b = create_approved_interface("interface_b", ProfileType.RECTANGLE)
    iface_a.dimensions[0].value = 120.0
    iface_b.dimensions[0].value = 180.0
    iface_b.dimensions[1].value = 140.0

    result = validate_connection_and_manufacturing(
        iface_a,
        iface_b,
        Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0),
        Manufacturing(wall_thickness_mm=2.4),
    )

    assert result.is_valid is True
    assert not any(issue.id == "IF-CONN-009" for issue in result.blocking_errors)



def test_prerequisite_approval_failure():
    """Verify validation fails if either Interface A or Interface B is not approved."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")
    iface_b.approved = False  # Unapprove Interface B

    conn = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0)
    mfg = Manufacturing(wall_thickness_mm=2.4)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    assert any(e.id == "IF-CONN-001" for e in res.blocking_errors)


def test_invalid_negative_or_non_finite_length_and_wall():
    """Verify negative or non-finite values produce blocking errors."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    conn = Connection(mode=ConnectionMode.COAXIAL, length_mm=-10.0)
    mfg = Manufacturing(wall_thickness_mm=0.0)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    error_ids = [e.id for e in res.blocking_errors]
    assert "IF-CONN-003" in error_ids
    assert "IF-MFG-001" in error_ids


def test_excessive_angle_limit():
    """Verify angle exceeding 45 degrees returns blocking error IF-CONN-004."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    conn = Connection(mode=ConnectionMode.ANGLED, length_mm=50.0, angle_deg=50.0)
    mfg = Manufacturing(wall_thickness_mm=2.4)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    assert any(e.id == "IF-CONN-004" for e in res.blocking_errors)


def test_excessive_offset_to_length_ratio():
    """Verify offset-to-length ratio > 1.5 returns blocking error IF-CONN-006."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    # length = 20mm, offset_x = 40mm -> ratio = 2.0 > 1.5
    conn = Connection(mode=ConnectionMode.OFFSET, length_mm=20.0, offset_x_mm=40.0, offset_y_mm=0.0)
    mfg = Manufacturing(wall_thickness_mm=2.4)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    assert any(e.id == "IF-CONN-006" for e in res.blocking_errors)


def test_wall_thickness_warnings_and_errors():
    """Verify thin wall (< 0.4mm) returns error and thin wall (0.8mm) returns warning."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    conn = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0)

    # 1. Below 0.4mm -> Error
    mfg_error = Manufacturing(wall_thickness_mm=0.2)
    res_err = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg_error)
    assert res_err.is_valid is False
    assert any(e.id == "IF-MFG-002" for e in res_err.blocking_errors)

    # 2. 0.8mm -> Warning for FDM (< 1.2mm)
    mfg_warn = Manufacturing(wall_thickness_mm=0.8)
    res_warn = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg_warn)
    assert res_warn.is_valid is True
    assert any(w.id == "IF-MFG-W001" for w in res_warn.warnings)


def test_clearance_bounds():
    """Verify clearances outside [0.0, 5.0] mm produce blocking errors."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    conn = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0)
    mfg = Manufacturing(clearance_a_mm=6.0, clearance_b_mm=-0.5)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    assert any(e.id == "IF-MFG-003" for e in res.blocking_errors)


def test_mode_parameter_mismatch_rules():
    """Verify coaxial mode with non-zero offsets or angle returns blocking error."""
    iface_a = create_approved_interface("interface_a")
    iface_b = create_approved_interface("interface_b")

    conn = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0, offset_x_mm=5.0, angle_deg=10.0)
    mfg = Manufacturing(wall_thickness_mm=2.4)

    res = validate_connection_and_manufacturing(iface_a, iface_b, conn, mfg)
    assert res.is_valid is False
    error_ids = [e.id for e in res.blocking_errors]
    assert "IF-CONN-007" in error_ids
    assert "IF-CONN-005" in error_ids


def test_project_service_connection_update_and_stale_model_behavior():
    """Verify updating connection via service increments schema revision and marks model stale."""
    service = ProjectService()
    project = service.create_project()

    # Approve Interface A and B
    project.interface_a = create_approved_interface("interface_a")
    project.interface_b = create_approved_interface("interface_b")

    # Simulate existing current 3D model revision
    from app.models.schema import ModelRevision, ModelRevisionStatus

    project.model_revisions.append(
        ModelRevision(model_revision=1, schema_revision=1, status=ModelRevisionStatus.CURRENT)
    )
    project.current_model_revision = 1
    project.last_known_good_model_revision = 1
    service.repository.save(project)

    prev_revision = project.current_schema_revision

    # Update connection configuration
    from app.models.schema import ConnectionUpdateRequest

    updated_proj = service.update_connection(
        project.project_id,
        ConnectionUpdateRequest(mode=ConnectionMode.COAXIAL, length_mm=50.0),
        project_token=project.project_token,
    )

    assert updated_proj.current_schema_revision == prev_revision + 1
    assert updated_proj.model_revisions[0].status == ModelRevisionStatus.STALE
    assert updated_proj.last_known_good_model_revision == 1  # LKG model revision preserved!
