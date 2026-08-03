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
from app.services.loft_plan import (
    CALIBRATION_REQUIRED_MESSAGE,
    has_valid_confirmed_calibration,
    uses_calibrated_trace,
)
from app.services.profile_geometry import fitted_profile_size


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
        "length_mm": 10.0,
        "wall_thickness_mm": 2.4,
        "clearance_a_mm": 0.1,
        "clearance_b_mm": 0.1,
        "offset_x_mm": 0.0,
        "offset_y_mm": 0.0,
        "angle_deg": 0.0,
    }

    for iface_name, iface in (("Interface A", interface_a), ("Interface B", interface_b)):
        if uses_calibrated_trace(iface) and not has_valid_confirmed_calibration(iface):
            errors.append(
                ValidationIssue(
                    id="IF-CAL-001",
                    message=CALIBRATION_REQUIRED_MESSAGE,
                    field=iface_name.lower().replace(" ", "_"),
                    recovery_steps=[
                        "Select two trace points and confirm their known distance in millimetres."
                    ],
                )
            )


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
    supported_modes = {ConnectionMode.COAXIAL, ConnectionMode.OFFSET}
    if connection.mode not in supported_modes:
        msg = f"Unsupported connection mode '{connection.mode}'. Must be coaxial or offset."
        errors.append(
            ValidationIssue(
                id="IF-CONN-002",
                message=msg,
                field="mode",
                recovery_steps=["Select a supported connection mode: coaxial or offset."],
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

    # 3a. Optional straight vertical profile extensions
    for ext_field, ext_value, ext_label in [
        ("extension_a_mm", connection.extension_a_mm, "Interface A vertical extension"),
        ("extension_b_mm", connection.extension_b_mm, "Interface B vertical extension"),
    ]:
        if not math.isfinite(ext_value) or ext_value < 0.0:
            errors.append(ValidationIssue(
                id="IF-CONN-008",
                message=f"{ext_label} must be a finite value of 0 mm or greater.",
                field=ext_field,
                recovery_steps=[f"Set {ext_label.lower()} to 0 mm or greater."],
            ))
        elif ext_value > 300.0:
            warnings.append(ValidationIssue(
                id="IF-CONN-W005",
                message=f"{ext_label} is long (> 300 mm), increasing print volume.",
                field=ext_field,
                recovery_steps=[f"Verify {ext_label.lower()} against physical enclosure bounds."],
            ))

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
        ("clearance_a_mm", manufacturing.clearance_a_mm, "Tolerance A"),
        ("clearance_b_mm", manufacturing.clearance_b_mm, "Tolerance B"),
    ]:
        if not math.isfinite(clr_val) or clr_val < 0.0 or clr_val > 5.0:
            errors.append(
                ValidationIssue(
                    id="IF-MFG-003",
                    message=f"{clr_label} must be a finite value between 0.0 mm and 5.0 mm.",
                    field=clr_field,
                    recovery_steps=["Set tolerance between 0.0 mm and 5.0 mm."],
                )
            )
        elif clr_val < 0.1:
            warnings.append(
                ValidationIssue(
                    id="IF-MFG-W003",
                    message=f"{clr_label} is below 0.1 mm, which may result in tight interference.",
                    field=clr_field,
                    recovery_steps=["Increase tolerance to 0.2 mm - 0.4 mm for slip-fit."],
                )
            )

    # 6. Mode-specific parameter rules
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
        if iface.profile_type in (ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED) and iface.traced_outer_contour is None:
            errors.append(
                ValidationIssue(
                    id="IF-CONN-008",
                    message=f"{iface_name} has no approved outer contour.",
                    field=iface_name.lower().replace(" ", "_"),
                    recovery_steps=["Review and approve one valid closed outer contour."],
                )
            )

    # 9. Per-interface fit intent collapse checks
    for iface_name, iface, clearance, field in [
        ("Interface A", interface_a, manufacturing.clearance_a_mm, "clearance_a_mm"),
        ("Interface B", interface_b, manufacturing.clearance_b_mm, "clearance_b_mm"),
    ]:
        if iface.profile_type in (ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED):
            continue
        outer_size = fitted_profile_size(iface, clearance, manufacturing.wall_thickness_mm, outer=True)
        inner_size = fitted_profile_size(iface, clearance, manufacturing.wall_thickness_mm, outer=False)
        if outer_size.width <= 0 or outer_size.height <= 0:
            errors.append(
                ValidationIssue(
                    id="IF-MFG-005",
                    message=f"{iface_name} fit intent and tolerance collapse the adapter outer boundary.",
                    field=field,
                    recovery_steps=["Reduce tolerance or choose Fit over the outside for this interface."],
                )
            )
        if inner_size.width <= 0 or inner_size.height <= 0:
            errors.append(
                ValidationIssue(
                    id="IF-MFG-004",
                    message=f"{iface_name} wall thickness closes the adapter passage.",
                    field="wall_thickness_mm",
                    recovery_steps=["Reduce wall thickness or tolerance so the inner boundary remains positive."],
                )
            )
        if iface.profile_type == ProfileType.ROUNDED_RECTANGLE and outer_size.corner_radius > min(outer_size.width, outer_size.height) / 2.0:
            errors.append(
                ValidationIssue(
                    id="IF-MFG-006",
                    message=f"{iface_name} rounded-rectangle radius is larger than the fitted boundary can support.",
                    field=field,
                    recovery_steps=["Reduce tolerance or corner radius before generation."],
                )
            )

    # 10. Self-intersection & internal void checks
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

    lateral_shift = math.hypot(connection.offset_x_mm, connection.offset_y_mm)
    has_transition_motion = lateral_shift > 0.0 or abs(connection.angle_deg) > 0.0
    if connection.length_mm > 0 and math.isfinite(connection.angle_deg) and has_transition_motion:
        abs_rad = math.radians(abs(connection.angle_deg))
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
