"""Geometry and manufacturing validation service for connection configuration (S4C)."""

import math
from typing import Dict, List

from app.models.schema import (
    Connection,
    ConnectionMode,
    ConnectionValidationResult,
    Interface,
    Manufacturing,
    ProfileType,
    ValidationIssue,
)


def get_interface_outer_bounding_dim(interface: Interface) -> float:
    """Helper to calculate outer bounding extent of an interface profile."""
    dims = {d.id: d.value for d in interface.dimensions if d.value > 0}
    if interface.profile_type == ProfileType.CIRCLE:
        return dims.get("outer_diameter", 50.0)
    elif interface.profile_type in (ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE):
        w = dims.get("width", 50.0)
        h = dims.get("height", 50.0)
        return math.hypot(w, h)
    return 50.0


def validate_connection_and_manufacturing(
    interface_a: Interface,
    interface_b: Interface,
    connection: Connection,
    manufacturing: Manufacturing,
) -> ConnectionValidationResult:
    """Validates connection parameters and manufacturing rules.

    Returns blocking errors, non-blocking warnings, and recommended values with stable error IDs.
    """
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    recommended: Dict[str, float] = {
        "length_mm": 40.0,
        "wall_thickness_mm": 2.4,
        "clearance_a_mm": 0.3,
        "clearance_b_mm": 0.1,
        "offset_x_mm": 0.0,
        "offset_y_mm": 0.0,
        "angle_deg": 0.0,
    }

    # 1. Prerequisite approval check
    if not interface_a.approved:
        errors.append(
            ValidationIssue(
                id="IF-CONN-001",
                message="Interface A must be approved before configuring connection.",
                field="interface_a",
                recovery_steps=["Return to Interface A review and approve its profile."],
            )
        )
    if not interface_b.approved:
        errors.append(
            ValidationIssue(
                id="IF-CONN-001",
                message="Interface B must be approved before configuring connection.",
                field="interface_b",
                recovery_steps=["Return to Interface B review and approve its profile."],
            )
        )

    # 2. Supported connection mode check
    supported_modes = {ConnectionMode.COAXIAL, ConnectionMode.OFFSET, ConnectionMode.ANGLED}
    if connection.mode not in supported_modes:
        msg = f"Unsupported connection mode '{connection.mode}'. Must be coaxial/offset/angled."
        errors.append(
            ValidationIssue(
                id="IF-CONN-002",
                message=msg,
                field="mode",
                recovery_steps=["Select a supported connection mode: coaxial, offset, or angled."],
            )
        )

    # 3. Positive finite transition length check
    if not math.isfinite(connection.length_mm) or connection.length_mm <= 0:
        errors.append(
            ValidationIssue(
                id="IF-CONN-003",
                message="Transition length must be a positive finite number greater than 0 mm.",
                field="length_mm",
                recovery_steps=["Enter a transition length greater than 0 mm."],
            )
        )
    else:
        if connection.length_mm < 10.0:
            warnings.append(
                ValidationIssue(
                    id="IF-CONN-W001",
                    message="Transition length is short (< 10 mm), causing steep loft angles.",
                    field="length_mm",
                    recovery_steps=["Consider increasing transition length to at least 20 mm."],
                )
            )
        elif connection.length_mm > 300.0:
            warnings.append(
                ValidationIssue(
                    id="IF-CONN-W002",
                    message="Transition length is long (> 300 mm), increasing print volume.",
                    field="length_mm",
                    recovery_steps=["Verify transition length against physical enclosure bounds."],
                )
            )

    # 4. Positive finite wall thickness check
    if not math.isfinite(manufacturing.wall_thickness_mm) or manufacturing.wall_thickness_mm <= 0:
        errors.append(
            ValidationIssue(
                id="IF-MFG-001",
                message="Wall thickness must be a positive finite number greater than 0 mm.",
                field="wall_thickness_mm",
                recovery_steps=["Set wall thickness to a positive value (recommended 2.4 mm)."],
            )
        )
    elif manufacturing.wall_thickness_mm < 0.4:
        errors.append(
            ValidationIssue(
                id="IF-MFG-002",
                message="Wall thickness is below absolute minimum printable limit (0.4 mm).",
                field="wall_thickness_mm",
                recovery_steps=["Increase wall thickness to at least 0.8 mm (recommended 2.4 mm)."],
            )
        )
    else:
        if manufacturing.wall_thickness_mm < 1.2:
            warnings.append(
                ValidationIssue(
                    id="IF-MFG-W001",
                    message="Wall thickness is below FDM recommended minimum (1.2 mm).",
                    field="wall_thickness_mm",
                    recovery_steps=["Increase wall thickness to 1.2 mm or higher."],
                )
            )
        elif manufacturing.wall_thickness_mm > 15.0:
            warnings.append(
                ValidationIssue(
                    id="IF-MFG-W002",
                    message="Wall thickness is thick (> 15 mm), increasing warping risk.",
                    field="wall_thickness_mm",
                    recovery_steps=["Consider reducing wall thickness unless structural."],
                )
            )

    # 5. Clearance bounds check (0.0 mm to 5.0 mm)
    for clr_field, clr_val, clr_label in [
        ("clearance_a_mm", manufacturing.clearance_a_mm, "Clearance A"),
        ("clearance_b_mm", manufacturing.clearance_b_mm, "Clearance B"),
    ]:
        if not math.isfinite(clr_val) or clr_val < 0.0 or clr_val > 5.0:
            errors.append(
                ValidationIssue(
                    id="IF-MFG-003",
                    message=f"{clr_label} must be a finite value between 0.0 mm and 5.0 mm.",
                    field=clr_field,
                    recovery_steps=["Set clearance between 0.0 mm and 5.0 mm."],
                )
            )
        elif clr_val < 0.1:
            warnings.append(
                ValidationIssue(
                    id="IF-MFG-W003",
                    message=f"{clr_label} is below 0.1 mm, which may result in tight interference.",
                    field=clr_field,
                    recovery_steps=["Increase clearance to 0.2 mm - 0.4 mm for slip-fit."],
                )
            )

    # 6. Angle check (0.0 to 45.0 degrees)
    if not math.isfinite(connection.angle_deg):
        errors.append(
            ValidationIssue(
                id="IF-CONN-004",
                message="Angle must be a finite numerical value in degrees.",
                field="angle_deg",
                recovery_steps=["Enter a numerical angle in degrees between 0° and 45°."],
            )
        )
    else:
        abs_angle = abs(connection.angle_deg)
        if abs_angle > 45.0:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-004",
                    message=f"Angle ({abs_angle:.1f}°) exceeds maximum MVP limit of 45.0°.",
                    field="angle_deg",
                    recovery_steps=["Reduce connection angle to 45.0° or less."],
                )
            )
        elif abs_angle > 30.0:
            warnings.append(
                ValidationIssue(
                    id="IF-CONN-W003",
                    message=f"Angle ({abs_angle:.1f}°) > 30.0°. Overhang supports required.",
                    field="angle_deg",
                    recovery_steps=["Keep angle under 30.0° if supportless printing is preferred."],
                )
            )

    # Mode-specific parameter rules
    if connection.mode == ConnectionMode.COAXIAL:
        if connection.offset_x_mm != 0.0 or connection.offset_y_mm != 0.0:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-007",
                    message="X and Y offsets must be 0 mm for Coaxial connection mode.",
                    field="offset_x_mm",
                    recovery_steps=["Reset X and Y offsets to 0 mm, or switch to Offset mode."],
                )
            )
        if connection.angle_deg != 0.0:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-005",
                    message="Angle must be 0° for Coaxial connection mode.",
                    field="angle_deg",
                    recovery_steps=["Reset angle to 0°, or switch to Angled connection mode."],
                )
            )
    elif connection.mode == ConnectionMode.OFFSET:
        if connection.angle_deg != 0.0:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-005",
                    message="Angle must be 0° for Offset connection mode.",
                    field="angle_deg",
                    recovery_steps=["Reset angle to 0°, or switch to Angled connection mode."],
                )
            )

    # 7. Offset-to-length ratio check
    if (
        math.isfinite(connection.offset_x_mm)
        and math.isfinite(connection.offset_y_mm)
        and connection.length_mm > 0
    ):
        offset_dist = math.hypot(connection.offset_x_mm, connection.offset_y_mm)
        ratio = offset_dist / connection.length_mm
        if ratio > 1.5:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-006",
                    message=f"Offset-to-length ratio ({ratio:.2f}) exceeds limit of 1.5.",
                    field="offset_x_mm",
                    recovery_steps=[
                        "Increase transition length or reduce X/Y offset to ratio <= 1.5."
                    ],
                )
            )
        elif ratio > 1.0:
            warnings.append(
                ValidationIssue(
                    id="IF-CONN-W004",
                    message=f"High offset-to-length ratio ({ratio:.2f} > 1.0) causes skew.",
                    field="offset_x_mm",
                    recovery_steps=["Consider increasing transition length relative to offset."],
                )
            )

    # 8. Unsupported profile combinations check
    for iface_name, iface in [("Interface A", interface_a), ("Interface B", interface_b)]:
        if iface.profile_type == ProfileType.TRACED_CLOSED:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-008",
                    message=f"{iface_name} uses unsupported profile 'traced_closed'.",
                    field=iface_name.lower().replace(" ", "_"),
                    recovery_steps=["Re-edit profile to circle, rectangle, or rounded rectangle."],
                )
            )

    # 9. Self-intersection & internal void checks
    bound_a = get_interface_outer_bounding_dim(interface_a)
    bound_b = get_interface_outer_bounding_dim(interface_b)
    min_dim = min(bound_a, bound_b)

    if manufacturing.wall_thickness_mm >= min_dim / 2.0:
        errors.append(
            ValidationIssue(
                id="IF-MFG-004",
                message=f"Wall ({manufacturing.wall_thickness_mm:.1f}mm) closes inner passage.",
                field="wall_thickness_mm",
                recovery_steps=["Reduce wall thickness to under half of smallest profile size."],
            )
        )

    if connection.length_mm > 0 and math.isfinite(connection.angle_deg):
        abs_rad = math.radians(abs(connection.angle_deg))
        lateral_shift = math.hypot(connection.offset_x_mm, connection.offset_y_mm)
        angular_shift = connection.length_mm * math.sin(abs_rad) + bound_b * math.cos(abs_rad)
        total_span = lateral_shift + angular_shift

        if total_span > (1.8 * connection.length_mm + min_dim):
            errors.append(
                ValidationIssue(
                    id="IF-CONN-009",
                    message="High geometric self-intersection risk detected.",
                    field="angle_deg",
                    recovery_steps=["Reduce angle or offset, or increase transition length."],
                )
            )

    is_valid = len(errors) == 0

    return ConnectionValidationResult(
        is_valid=is_valid,
        blocking_errors=errors,
        warnings=warnings,
        recommended_values=recommended,
    )
