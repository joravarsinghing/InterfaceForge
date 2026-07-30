"""Profile structural validation logic per S4B and S10.3 specification."""

import math
from typing import List, Optional, Tuple

from app.models.schema import DimensionProvenance, Interface, Point2D, ProfileType, TracedContour

# Maximum allowed point count for traced profiles before rejecting as too dense
MAX_TRACED_POINTS = 2000
MIN_TRACED_OUTER_POINTS = 4
MAX_SEGMENT_COMPARISONS = 250_000
PRIMITIVE_DIMENSION_IDS = {
    ProfileType.CIRCLE: ("outer_diameter", "diameter"),
    ProfileType.RECTANGLE: ("width", "height"),
    ProfileType.ROUNDED_RECTANGLE: ("width", "height", "corner_radius"),
}


def _is_legacy_unmapped_dimension_id(dim_id: str) -> bool:
    return dim_id.startswith("custom_dim_") or dim_id.startswith("unmapped_")


def _is_generation_dimension(interface: Interface, dim_id: str) -> bool:
    allowed = PRIMITIVE_DIMENSION_IDS.get(interface.profile_type, ())
    return dim_id in allowed


def _validate_contour(
    contour: TracedContour, label: str, errors: List[str], warnings: List[str]
) -> None:
    """Structural validation for a single closed contour."""
    pts = contour.points

    # Minimum point count
    if len(pts) < MIN_TRACED_OUTER_POINTS:
        errors.append(
            f"{label} contour has {len(pts)} points (minimum {MIN_TRACED_OUTER_POINTS} required)."
        )
        return

    # Maximum density guard
    if len(pts) > MAX_TRACED_POINTS:
        errors.append(
            f"{label} contour is too dense ({len(pts)} points, max {MAX_TRACED_POINTS}). "
            "Simplify or re-upload a cleaner image."
        )
        return

    # No NaN/non-finite values
    for i, pt in enumerate(pts):
        if not math.isfinite(pt.x) or not math.isfinite(pt.y):
            errors.append(
                f"{label} contour point index {i} has non-finite coordinates ({pt.x}, {pt.y})."
            )
            return

    # No duplicate consecutive points
    duplicates = 0
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        if abs(a.x - b.x) < 1e-9 and abs(a.y - b.y) < 1e-9:
            duplicates += 1
    if duplicates > 0:
        warnings.append(
            f"{label} contour has {duplicates} duplicate consecutive point(s) that may indicate "
            "image noise."
        )

    # Closure check (last point approximately equals first)
    if not contour.is_closed:
        errors.append(f"{label} contour is not marked as closed.")


def _points_bbox(points: List[Point2D]) -> Tuple[float, float, float, float]:
    """Return (min_x, max_x, min_y, max_y) bounding box of a point list."""
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def _point_inside_bbox(
    px: float, py: float, min_x: float, max_x: float, min_y: float, max_y: float
) -> bool:
    """Quick bounding-box containment test."""
    return min_x <= px <= max_x and min_y <= py <= max_y


def validate_interface_profile(interface: Interface) -> Tuple[bool, List[str], List[str]]:
    """Validate interface profile structural rules.

    Returns:
        (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # --- Traced closed profile path (S10.3) ---
    if interface.profile_type in (ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED):
        return _validate_traced_profile(interface, errors, warnings)

    # --- Primitive profile path (existing logic preserved) ---
    return _validate_primitive_profile(interface, errors, warnings)


def _ccw(p1: Point2D, p2: Point2D, p3: Point2D) -> bool:
    """Check if three points are listed in counter-clockwise order."""
    return (p3.y - p1.y) * (p2.x - p1.x) > (p2.y - p1.y) * (p3.x - p1.x)


def _segments_intersect(p1: Point2D, p2: Point2D, p3: Point2D, p4: Point2D) -> bool:
    """Return True if line segment (p1, p2) intersects with (p3, p4)."""
    return _ccw(p1, p3, p4) != _ccw(p2, p3, p4) and _ccw(p1, p2, p3) != _ccw(p1, p2, p4)


def _check_self_intersection(pts: List[Point2D]) -> Tuple[bool, Optional[str]]:
    """Check if a closed polygon defined by pts intersects itself within a fixed budget."""
    n = len(pts)
    if n < 4:
        return False, None
    comparisons = 0
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        for j in range(i + 2, n):
            # Skip adjacent line segment at start/end wrap
            if i == 0 and j == n - 1:
                continue
            comparisons += 1
            if comparisons > MAX_SEGMENT_COMPARISONS:
                return (
                    False,
                    "IF-PROFILE-COMPLEXITY-BUDGET: contour validation exceeded "
                    f"{MAX_SEGMENT_COMPARISONS} segment comparisons.",
                )
            p3 = pts[j]
            p4 = pts[(j + 1) % n]
            if _segments_intersect(p1, p2, p3, p4):
                return True, None
    return False, None


def _validate_traced_profile(
    interface: Interface, errors: List[str], warnings: List[str]
) -> Tuple[bool, List[str], List[str]]:
    """Validate structural rules for traced closed profiles."""
    # Outer contour is required
    if interface.traced_outer_contour is None:
        errors.append("Traced closed profile requires an outer contour but none was provided.")
        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    outer = interface.traced_outer_contour
    _validate_contour(outer, "Outer", errors, warnings)

    # Bounding box fallback warning for complex profiles
    if getattr(interface, "is_complex", False) and outer.points and len(outer.points) == 4:
        warnings.append(
            "Profile flagged complex requires detailed non-convex perimeter; "
            "4-point bounding box is a simplified envelope."
        )

    # Check outer contour self-intersection
    if outer.points:
        intersects, complexity_error = _check_self_intersection(outer.points)
        if complexity_error:
            errors.append(complexity_error)
        elif intersects:
            errors.append("Outer contour intersects itself. Please adjust boundary points.")

    # Validate hole contours
    if interface.traced_hole_contours:
        if len(interface.traced_hole_contours) > 20:
            warnings.append(
                f"{len(interface.traced_hole_contours)} inner holes detected. "
                "Very complex profiles may not generate correctly."
            )
        outer_bbox = _points_bbox(outer.points) if outer.points else None
        for idx, hole in enumerate(interface.traced_hole_contours):
            _validate_contour(hole, f"Hole[{idx}]", errors, warnings)
            if hole.points:
                intersects, complexity_error = _check_self_intersection(hole.points)
                if complexity_error:
                    errors.append(f"Hole[{idx}] {complexity_error}")
                elif intersects:
                    errors.append(f"Hole[{idx}] contour intersects itself.")
            # Bbox containment check for holes
            if outer_bbox and hole.points:
                min_ox, max_ox, min_oy, max_oy = outer_bbox
                for pt in hole.points:
                    if not _point_inside_bbox(pt.x, pt.y, min_ox, max_ox, min_oy, max_oy):
                        warnings.append(
                            f"Hole[{idx}] contour has points outside outer bounding box. "
                            "This may indicate an invalid trace."
                        )
                        break

    # Scale calibration validation
    if interface.scale_calibration is not None:
        sc = interface.scale_calibration
        if not math.isfinite(sc.real_distance_mm) or sc.real_distance_mm <= 0:
            errors.append(
                f"Scale real_distance_mm must be positive finite (got {sc.real_distance_mm})."
            )
        if not sc.confirmed:
            warnings.append("Scale calibration is unconfirmed. Confirm scale before approval.")

    # Cross-validate scale against mapped dimensions
    from app.services.geometry_editing import validate_scale_and_dimensions

    scale_warnings = validate_scale_and_dimensions(interface)
    warnings.extend(scale_warnings)

    # Dimension validation for traced profiles. Unmapped legacy/custom rows are compatibility data only.
    for dim in interface.dimensions:
        if (
            dim.feature_ref is None
            or dim.consistency_state == "unmapped"
            or _is_legacy_unmapped_dimension_id(dim.id)
        ):
            continue
        if not math.isfinite(dim.value) or dim.value < 0:
            errors.append(
                f"Dimension '{dim.label}' must be a non-negative finite value (got {dim.value})."
            )
        if not math.isfinite(dim.confidence) or dim.confidence < 0.0 or dim.confidence > 1.0:
            errors.append(
                f"Dimension '{dim.label}' confidence must be between 0.0 and 1.0 "
                f"(got {dim.confidence})."
            )
        if dim.critical and dim.provenance == DimensionProvenance.UNRESOLVED:
            errors.append(f"Critical dimension '{dim.label}' is unresolved.")
        if dim.critical and dim.consistency_state == "conflict":
            errors.append(
                f"Fit-critical dimension '{dim.label}' has a geometry consistency conflict."
            )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def _validate_primitive_profile(
    interface: Interface, errors: List[str], warnings: List[str]
) -> Tuple[bool, List[str], List[str]]:
    """Validate primitive profile (circle, rectangle, rounded_rectangle) structural rules."""
    # 1. Supported profile type
    supported_types = {ProfileType.CIRCLE, ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE}
    if interface.profile_type not in supported_types:
        errors.append(
            f"Unsupported profile type '{interface.profile_type}'. "
            "Supported types are: circle, rectangle, rounded_rectangle, custom_closed."
        )

    # 2. Positive finite generation dimensions. Legacy unmapped/custom dimensions
    # are retained for compatibility, but they do not satisfy or block approval.
    generation_dims = {
        dim.id: dim
        for dim in interface.dimensions
        if _is_generation_dimension(interface, dim.id)
        and dim.consistency_state != "unmapped"
        and not _is_legacy_unmapped_dimension_id(dim.id)
    }
    required_groups = PRIMITIVE_DIMENSION_IDS.get(interface.profile_type, ())
    if interface.profile_type == ProfileType.CIRCLE:
        if not any(dim_id in generation_dims for dim_id in required_groups):
            errors.append("Circle profile requires a derived diameter dimension.")
    else:
        for dim_id in required_groups:
            if dim_id not in generation_dims:
                errors.append(f"{interface.profile_type.value} profile requires derived dimension '{dim_id}'.")

    for dim in generation_dims.values():
        if not math.isfinite(dim.value) or dim.value <= 0:
            errors.append(
                f"Dimension '{dim.label}' must be a positive finite value (got {dim.value})."
            )
        if not math.isfinite(dim.confidence) or dim.confidence < 0.0 or dim.confidence > 1.0:
            errors.append(
                f"Dimension '{dim.label}' confidence must be between 0.0 and 1.0 "
                f"(got {dim.confidence})."
            )
        if dim.critical and dim.provenance == DimensionProvenance.UNRESOLVED:
            errors.append(f"Critical dimension '{dim.label}' is unresolved.")
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
