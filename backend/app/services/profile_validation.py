"""Profile structural validation logic per S4B specification."""

import math
from typing import List, Tuple

from app.models.schema import DimensionProvenance, Interface, ProfileType


def validate_interface_profile(interface: Interface) -> Tuple[bool, List[str], List[str]]:
    """Validate interface profile structural rules.

    Returns:
        (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Supported profile type
    supported_types = {ProfileType.CIRCLE, ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE}
    if interface.profile_type not in supported_types:
        errors.append(
            f"Unsupported profile type '{interface.profile_type}'. "
            "Supported types are: circle, rectangle, rounded_rectangle."
        )

    # 2. Positive finite dimension values and confidence ranges
    known_dimensions_count = 0
    for dim in interface.dimensions:
        # Check finite & positive value
        if not math.isfinite(dim.value) or dim.value <= 0:
            errors.append(
                f"Dimension '{dim.label}' must be a positive finite value (got {dim.value})."
            )

        # Check valid confidence range [0.0, 1.0]
        if not math.isfinite(dim.confidence) or dim.confidence < 0.0 or dim.confidence > 1.0:
            errors.append(
                f"Dimension '{dim.label}' confidence must be between 0.0 and 1.0 "
                f"(got {dim.confidence})."
            )

        # Count known dimensions (not UNRESOLVED, positive finite value)
        if (
            dim.provenance != DimensionProvenance.UNRESOLVED
            and math.isfinite(dim.value)
            and dim.value > 0
        ):
            known_dimensions_count += 1

        # Check unresolved critical dimensions
        if dim.critical and dim.provenance == DimensionProvenance.UNRESOLVED:
            errors.append(f"Critical dimension '{dim.label}' is unresolved.")

    # 3. Minimum two known dimensions
    if known_dimensions_count < 2:
        errors.append(
            f"Profile requires at least two known dimensions (found {known_dimensions_count})."
        )

    # 4. Basic point validity
    if interface.profile_points:
        for i, pt in enumerate(interface.profile_points):
            if not math.isfinite(pt.x) or not math.isfinite(pt.y):
                errors.append(f"Point index {i} has non-finite coordinates ({pt.x}, {pt.y}).")
                break

    # 5. Profile-specific shape constraints
    if interface.profile_type == ProfileType.ROUNDED_RECTANGLE:
        width_dim = next((d for d in interface.dimensions if d.id == "width"), None)
        height_dim = next((d for d in interface.dimensions if d.id == "height"), None)
        radius_dim = next((d for d in interface.dimensions if d.id == "corner_radius"), None)

        if width_dim and height_dim and radius_dim:
            if (
                math.isfinite(width_dim.value)
                and math.isfinite(height_dim.value)
                and math.isfinite(radius_dim.value)
            ):
                min_side = min(width_dim.value, height_dim.value)
                if radius_dim.value > min_side / 2.0:
                    warnings.append(
                        f"Corner radius ({radius_dim.value}mm) exceeds half the shortest side "
                        f"({min_side / 2.0}mm)."
                    )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings
