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
