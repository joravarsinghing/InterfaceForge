"""Shared primitive profile geometry helpers for fit intent, calibration, and KCL."""

import math
from dataclasses import dataclass
from typing import Iterable

from app.models.schema import Dimension, DimensionProvenance, FitMode, Interface, Point2D, ProfileType


@dataclass(frozen=True)
class ProfileSize:
    width: float
    height: float
    corner_radius: float = 0.0


def dimension_value(interface: Interface, dim_id: str, default: float = 0.0) -> float:
    for dim in interface.dimensions:
        if dim.id == dim_id and math.isfinite(dim.value) and dim.value > 0:
            return float(dim.value)
    return default


def primitive_size(interface: Interface) -> ProfileSize:
    if interface.profile_type == ProfileType.CIRCLE:
        dia = dimension_value(interface, "outer_diameter", 50.0)
        return ProfileSize(width=dia, height=dia)
    width = dimension_value(interface, "width", 50.0)
    height = dimension_value(interface, "height", 50.0)
    radius = dimension_value(interface, "corner_radius", 0.0)
    return ProfileSize(width=width, height=height, corner_radius=radius)


def fitted_profile_size(interface: Interface, clearance: float, wall_thickness: float, *, outer: bool) -> ProfileSize:
    base = primitive_size(interface)
    fit_mode = getattr(interface, "fit_mode", FitMode.FIT_OVER)
    if fit_mode == FitMode.FIT_OVER:
        delta = 2.0 * (clearance + (wall_thickness if outer else 0.0))
    else:
        delta = -2.0 * (clearance + (0.0 if outer else wall_thickness))
    radius_delta = delta / 2.0
    return ProfileSize(
        width=base.width + delta,
        height=base.height + delta,
        corner_radius=max(base.corner_radius + radius_delta, 0.0) if base.corner_radius > 0 else 0.0,
    )


def bbox(points: Iterable[Point2D]) -> tuple[float, float, float, float] | None:
    pts = [p for p in points if math.isfinite(p.x) and math.isfinite(p.y)]
    if not pts:
        return None
    return min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts), max(p.y for p in pts)


def classify_primitive_from_points(points: list[Point2D]) -> ProfileType | None:
    box = bbox(points)
    if box is None or len(points) < 4:
        return None
    min_x, max_x, min_y, max_y = box
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    mean_radius = sum(math.hypot(p.x - cx, p.y - cy) for p in points) / len(points)
    radial_dev = max(abs(math.hypot(p.x - cx, p.y - cy) - mean_radius) for p in points)
    aspect_error = abs(width - height) / max(width, height)
    if aspect_error <= 0.10 and radial_dev / max(mean_radius, 1e-6) <= 0.12:
        return ProfileType.CIRCLE

    near_corners = 0
    corner_tol = 0.08 * max(width, height)
    for p in points:
        if (abs(abs(p.x - cx) - width / 2.0) <= corner_tol and abs(abs(p.y - cy) - height / 2.0) <= corner_tol):
            near_corners += 1
    if near_corners >= 4 and len(points) <= 6:
        return ProfileType.RECTANGLE
    return ProfileType.ROUNDED_RECTANGLE


def set_calibrated_primitive_dimensions(interface: Interface, scale_factor: float) -> None:
    points = interface.traced_outer_contour.points if interface.traced_outer_contour else interface.profile_points
    box = bbox(points)
    if box is None:
        return
    min_x, max_x, min_y, max_y = box
    width = (max_x - min_x) * scale_factor
    height = (max_y - min_y) * scale_factor
    existing = {dim.id: dim for dim in interface.dimensions}

    def upsert(dim_id: str, label: str, value: float, critical: bool = True) -> None:
        existing[dim_id] = Dimension(
            id=dim_id,
            label=label,
            value=round(value, 4),
            unit="mm",
            provenance=DimensionProvenance.USER_ENTERED,
            confidence=1.0,
            critical=critical,
            feature_ref="outer_contour",
            consistency_state="recalculated",
        )

    if interface.profile_type == ProfileType.CIRCLE:
        upsert("outer_diameter", "Outer Diameter", (width + height) / 2.0)
        upsert("overall_width", "Overall Width", width)
    elif interface.profile_type in (ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE):
        upsert("width", "Width", width)
        upsert("height", "Height", height)
        if interface.profile_type == ProfileType.ROUNDED_RECTANGLE:
            default_radius = min(width, height) * 0.12
            prev = existing.get("corner_radius")
            radius = prev.value * scale_factor if prev and math.isfinite(prev.value) and prev.value > 0 else default_radius
            upsert("corner_radius", "Corner Radius", min(radius, min(width, height) / 2.0), critical=False)
    interface.dimensions = list(existing.values())
