"""Geometry Editing and Scale Consistency Validation Service for Stage S10.5B.

Provides:
- Scale confirmation gate and cross-validation against mapped dimensions.
- Geometry-linked editable dimension updates (overall width/height, hole diameter, position, etc).
- Consistency state evaluation ('valid', 'conflict', 'unmapped', 'recalculated').
- Reversion and warning on invalid/self-intersecting edits.
"""

import copy
import math
from typing import List, Optional, Tuple

from app.models.schema import (
    Dimension,
    Interface,
)
from app.services.opencv_tracer import check_self_intersection


def validate_scale_and_dimensions(interface: Interface) -> List[str]:
    """Cross-validate scale calibration against mapped dimensions and flag conflicts (> 15% error).

    Updates dim.consistency_state to 'conflict' or 'valid' in-place.
    Returns list of warning messages for conflicting dimensions.
    """
    warnings: List[str] = []
    scale_cal = interface.scale_calibration
    if not scale_cal or scale_cal.pixel_distance <= 0 or scale_cal.real_distance_mm <= 0:
        return warnings

    scale_factor = (
        (getattr(scale_cal, "scale_factor", 0.0) or (scale_cal.real_distance_mm / scale_cal.pixel_distance))
        if getattr(scale_cal, "method", "known_measurement") == "two_point_trace"
        else 1.0
    )
    outer = interface.traced_outer_contour
    outer_w_mm = 0.0
    outer_h_mm = 0.0
    if outer and outer.points:
        xs = [p.x for p in outer.points]
        ys = [p.y for p in outer.points]
        outer_w_mm = (max(xs) - min(xs)) * scale_factor
        outer_h_mm = (max(ys) - min(ys)) * scale_factor

    for dim in interface.dimensions:
        if dim.consistency_state == "unmapped" or "not mapped" in dim.label.lower():
            dim.consistency_state = "unmapped"
            continue

        expected_mm: Optional[float] = None
        dim_id_lower = dim.id.lower()
        dim_label_lower = dim.label.lower()

        if "width" in dim_id_lower or "width" in dim_label_lower:
            expected_mm = outer_w_mm
        elif "height" in dim_id_lower or "height" in dim_label_lower:
            expected_mm = outer_h_mm

        if (
            expected_mm is None
            and ("bore" in dim_id_lower or "diameter" in dim_id_lower)
            and interface.traced_hole_contours
        ):
            target_hole = None
            if dim.feature_ref:
                target_hole = next(
                    (h for h in interface.traced_hole_contours if h.id == dim.feature_ref), None
                )
            if not target_hole:
                target_hole = interface.traced_hole_contours[0]

            if target_hole and target_hole.points:
                h_xs = [p.x for p in target_hole.points]
                h_ys = [p.y for p in target_hole.points]
                cx = sum(h_xs) / len(h_xs)
                cy = sum(h_ys) / len(h_ys)
                radii = [math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2) for p in target_hole.points]
                expected_mm = (sum(radii) / len(radii)) * 2.0 * scale_factor

        if expected_mm is not None and expected_mm > 0:
            diff_pct = abs(dim.value - expected_mm) / expected_mm
            if diff_pct > 0.15:
                dim.consistency_state = "conflict"
                w_msg = (
                    f"Dimension '{dim.label}' ({dim.value:.1f}mm) conflicts with geometry scale "
                    f"(measured {expected_mm:.1f}mm)."
                )
                warnings.append(w_msg)
            else:
                if dim.consistency_state != "recalculated":
                    dim.consistency_state = "valid"

    return warnings


def apply_dimension_edits_to_geometry(
    interface: Interface, new_dimensions: List[Dimension]
) -> Tuple[bool, List[str]]:
    """Update 2D polygon contour geometry in response to dimension edits.

    Returns:
        (success: bool, warnings: List[str])
    """
    if interface.profile_type != "traced_closed" or not interface.traced_outer_contour:
        interface.dimensions = new_dimensions
        return True, []

    warnings: List[str] = []
    old_dims_by_id = {d.id: d for d in interface.dimensions}

    backup_outer = copy.deepcopy(interface.traced_outer_contour)
    backup_holes = copy.deepcopy(interface.traced_hole_contours)

    outer_pts = interface.traced_outer_contour.points
    hole_contours = interface.traced_hole_contours

    for dim in new_dimensions:
        old_dim = old_dims_by_id.get(dim.id)
        if old_dim and abs(old_dim.value - dim.value) < 1e-6:
            continue

        dim_id_lower = dim.id.lower()
        dim_label_lower = dim.label.lower()
        new_val = dim.value

        if new_val <= 0:
            dim.consistency_state = "conflict"
            warnings.append(f"Dimension '{dim.label}' must be positive. Reverting geometry change.")
            continue

        # 1. Hole Center X / Y Edit (Checked before generic hole diameter)
        if "center_x" in dim_id_lower or "center_x" in dim_label_lower:
            if hole_contours and hole_contours[0].points:
                target_hole = hole_contours[0]
                cx = sum(p.x for p in target_hole.points) / len(target_hole.points)
                dx = new_val - cx
                for p in target_hole.points:
                    p.x = round(p.x + dx, 2)
                dim.consistency_state = "recalculated"

        elif "center_y" in dim_id_lower or "center_y" in dim_label_lower:
            if hole_contours and hole_contours[0].points:
                target_hole = hole_contours[0]
                cy = sum(p.y for p in target_hole.points) / len(target_hole.points)
                dy = new_val - cy
                for p in target_hole.points:
                    p.y = round(p.y + dy, 2)
                dim.consistency_state = "recalculated"

        # 2. Overall Width Edit
        elif "width" in dim_id_lower or "width" in dim_label_lower:
            xs = [p.x for p in outer_pts]
            curr_w = max(xs) - min(xs)
            if curr_w > 0:
                sx = new_val / curr_w
                for p in outer_pts:
                    p.x = round(p.x * sx, 2)
                for h in hole_contours:
                    for p in h.points:
                        p.x = round(p.x * sx, 2)
                dim.consistency_state = "recalculated"

        # 3. Overall Height Edit
        elif "height" in dim_id_lower or "height" in dim_label_lower:
            ys = [p.y for p in outer_pts]
            curr_h = max(ys) - min(ys)
            if curr_h > 0:
                sy = new_val / curr_h
                for p in outer_pts:
                    p.y = round(p.y * sy, 2)
                for h in hole_contours:
                    for p in h.points:
                        p.y = round(p.y * sy, 2)
                dim.consistency_state = "recalculated"

        # 4. Hole / Bore Diameter Edit
        elif (
            "bore" in dim_id_lower or "diameter" in dim_id_lower or "hole" in dim_id_lower
        ) and hole_contours:
            target_hole = None
            if dim.feature_ref:
                target_hole = next((h for h in hole_contours if h.id == dim.feature_ref), None)
            if not target_hole:
                target_hole = hole_contours[0]

            if target_hole and target_hole.points:
                h_xs = [p.x for p in target_hole.points]
                h_ys = [p.y for p in target_hole.points]
                cx = sum(h_xs) / len(h_xs)
                cy = sum(h_ys) / len(h_ys)
                radii = [math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2) for p in target_hole.points]
                curr_r = sum(radii) / len(radii) if radii else 1.0
                target_r = new_val / 2.0
                if curr_r > 0:
                    sr = target_r / curr_r
                    for p in target_hole.points:
                        p.x = round(cx + (p.x - cx) * sr, 2)
                        p.y = round(cy + (p.y - cy) * sr, 2)
                    dim.consistency_state = "recalculated"

        # 5. Hole Spacing Edit
        elif "spacing" in dim_id_lower or "spacing" in dim_label_lower:
            if len(hole_contours) >= 2:
                h1_cx = sum(p.x for p in hole_contours[0].points) / len(hole_contours[0].points)
                h2_cx = sum(p.x for p in hole_contours[1].points) / len(hole_contours[1].points)
                curr_spacing = abs(h2_cx - h1_cx)
                if curr_spacing > 0:
                    sp_scale = new_val / curr_spacing
                    for h in hole_contours:
                        hcx = sum(p.x for p in h.points) / len(h.points)
                        new_hcx = hcx * sp_scale
                        shift_x = new_hcx - hcx
                        for p in h.points:
                            p.x = round(p.x + shift_x, 2)
                    dim.consistency_state = "recalculated"

        # 6. Slot Width / Depth Edit
        elif "slot" in dim_id_lower or "slot" in dim_label_lower:
            for h in hole_contours:
                if "slot" in h.classification.lower() or h.decision == "include":
                    h_xs = [p.x for p in h.points]
                    sw = max(h_xs) - min(h_xs)
                    if sw > 0:
                        sw_scale = new_val / sw
                        hcx = sum(h_xs) / len(h_xs)
                        for p in h.points:
                            p.x = round(hcx + (p.x - hcx) * sw_scale, 2)
            dim.consistency_state = "recalculated"

    intersects, budget_exceeded = check_self_intersection(interface.traced_outer_contour.points)
    if intersects or budget_exceeded:
        interface.traced_outer_contour = backup_outer
        interface.traced_hole_contours = backup_holes
        warnings.append(
            "IF-PROFILE-COMPLEXITY-BUDGET: geometry edit exceeded validation budget."
            if budget_exceeded
            else (
                "Geometry edit resulted in self-intersecting polygon. "
                "Reverted to previous geometry."
            )
        )
        for dim in new_dimensions:
            dim.consistency_state = "conflict"
        interface.dimensions = new_dimensions
        return False, warnings

    interface.dimensions = new_dimensions
    return True, warnings
