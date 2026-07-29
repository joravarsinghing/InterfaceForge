"""Shared primitive profile geometry helpers for fit intent, calibration, and KCL."""

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from app.models.schema import (
    Dimension,
    DimensionProvenance,
    FitMode,
    Interface,
    Point2D,
    ProfileType,
)


@dataclass(frozen=True)
class PrimitiveClassification:
    profile_type: ProfileType
    confidence: float
    reason: str
    corner_radius_px: Optional[float] = None
    corner_radius_confidence: float = 0.0


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


def fitted_profile_size(
    interface: Interface, clearance: float, wall_thickness: float, *, outer: bool
) -> ProfileSize:
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
        corner_radius=max(base.corner_radius + radius_delta, 0.0)
        if base.corner_radius > 0
        else 0.0,
    )


def bbox(points: Iterable[Point2D]) -> tuple[float, float, float, float] | None:
    pts = [p for p in points if math.isfinite(p.x) and math.isfinite(p.y)]
    if not pts:
        return None
    return (
        min(p.x for p in pts),
        max(p.x for p in pts),
        min(p.y for p in pts),
        max(p.y for p in pts),
    )


def _point_side_distances(
    points: list[Point2D], box: tuple[float, float, float, float]
) -> list[float]:
    min_x, max_x, min_y, max_y = box
    return [
        min(abs(p.x - min_x), abs(p.x - max_x), abs(p.y - min_y), abs(p.y - max_y)) for p in points
    ]


def _corner_offsets(points: list[Point2D], box: tuple[float, float, float, float]) -> list[float]:
    min_x, max_x, min_y, max_y = box
    corners = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    offsets: list[float] = []
    for cx, cy in corners:
        nearby = sorted(
            (math.hypot(p.x - cx, p.y - cy) for p in points),
        )[:2]
        if nearby:
            offsets.append(sum(nearby) / len(nearby))
    return offsets


def classify_primitive_candidate(points: list[Point2D]) -> Optional[PrimitiveClassification]:
    box = bbox(points)
    if box is None or len(points) < 4:
        return None
    min_x, max_x, min_y, max_y = box
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None

    max_dim = max(width, height)
    min_dim = min(width, height)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    radii = [math.hypot(p.x - cx, p.y - cy) for p in points]
    mean_radius = sum(radii) / len(radii)
    radial_rms = math.sqrt(sum((r - mean_radius) ** 2 for r in radii) / len(radii))
    radial_max = max(abs(r - mean_radius) for r in radii)
    aspect_error = abs(width - height) / max_dim
    circle_score = 1.0 - max(aspect_error / 0.05, (radial_rms / max(mean_radius, 1e-6)) / 0.035)
    if (
        len(points) >= 12
        and aspect_error <= 0.05
        and radial_rms / max(mean_radius, 1e-6) <= 0.035
        and radial_max / max(mean_radius, 1e-6) <= 0.085
    ):
        return PrimitiveClassification(
            ProfileType.CIRCLE,
            confidence=round(max(0.85, min(0.99, 0.90 + 0.09 * circle_score)), 4),
            reason="radial_error_within_circle_threshold",
        )

    side_tol = 0.025 * max_dim
    corner_tol = 0.06 * max_dim
    side_distances = _point_side_distances(points, box)
    on_sides_ratio = sum(1 for d in side_distances if d <= side_tol) / len(points)
    near_corner_count = sum(
        1
        for p in points
        if abs(abs(p.x - cx) - width / 2.0) <= corner_tol
        and abs(abs(p.y - cy) - height / 2.0) <= corner_tol
    )
    unique_side_hits = {
        side
        for p in points
        for side, is_hit in (
            ("left", abs(p.x - min_x) <= side_tol),
            ("right", abs(p.x - max_x) <= side_tol),
            ("bottom", abs(p.y - min_y) <= side_tol),
            ("top", abs(p.y - max_y) <= side_tol),
        )
        if is_hit
    }
    if (
        len(points) <= 8
        and on_sides_ratio >= 0.95
        and near_corner_count >= 4
        and len(unique_side_hits) == 4
    ):
        return PrimitiveClassification(
            ProfileType.RECTANGLE,
            confidence=0.94,
            reason="all_points_lie_on_four_bbox_sides",
        )

    offsets = _corner_offsets(points, box)
    radius_px = sum(offsets) / len(offsets) if offsets else 0.0
    radius_ratio = radius_px / max(min_dim, 1e-6)
    radius_spread = (max(offsets) - min(offsets)) / max(radius_px, 1e-6) if offsets else 1.0
    horizontal_support = any(abs(p.y - min_y) <= side_tol for p in points) and any(
        abs(p.y - max_y) <= side_tol for p in points
    )
    vertical_support = any(abs(p.x - min_x) <= side_tol for p in points) and any(
        abs(p.x - max_x) <= side_tol for p in points
    )
    rounded_confidence = 1.0 - max(
        max(0.0, radius_spread - 0.35) / 0.65,
        0.0 if 0.03 <= radius_ratio <= 0.35 else 1.0,
        0.0 if on_sides_ratio >= 0.60 else (0.60 - on_sides_ratio) / 0.60,
    )
    if (
        len(points) >= 8
        and horizontal_support
        and vertical_support
        and 0.03 <= radius_ratio <= 0.35
        and radius_spread <= 0.65
        and on_sides_ratio >= 0.55
        and rounded_confidence >= 0.65
    ):
        return PrimitiveClassification(
            ProfileType.ROUNDED_RECTANGLE,
            confidence=round(max(0.65, min(0.90, rounded_confidence)), 4),
            reason="corner_offsets_support_rounded_rectangle",
            corner_radius_px=round(radius_px, 4),
            corner_radius_confidence=round(max(0.50, min(0.82, rounded_confidence - 0.08)), 4),
        )

    return None


def classify_primitive_from_points(points: list[Point2D]) -> ProfileType | None:
    result = classify_primitive_candidate(points)
    return result.profile_type if result else None


def set_calibrated_primitive_dimensions(interface: Interface, scale_factor: float) -> None:
    points = (
        interface.traced_outer_contour.points
        if interface.traced_outer_contour
        else interface.profile_points
    )
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
            prev = existing.get("corner_radius")
            classification = classify_primitive_candidate(points)
            if (
                classification
                and classification.profile_type == ProfileType.ROUNDED_RECTANGLE
                and classification.corner_radius_px
                and classification.corner_radius_confidence >= 0.75
            ):
                radius = classification.corner_radius_px * scale_factor
                provenance = DimensionProvenance.IMAGE_EXTRACTED
                confidence = classification.corner_radius_confidence
                consistency_state = "estimated_from_trace"
            elif prev and math.isfinite(prev.value) and prev.value > 0:
                radius = prev.value * scale_factor
                provenance = prev.provenance
                confidence = min(prev.confidence, 0.74)
                consistency_state = "requires_confirmation"
            else:
                radius = min(width, height) * 0.12
                provenance = DimensionProvenance.SYSTEM_INFERRED
                confidence = 0.45
                consistency_state = "requires_confirmation"
            existing["corner_radius"] = Dimension(
                id="corner_radius",
                label="Corner Radius",
                value=round(min(radius, min(width, height) / 2.0), 4),
                unit="mm",
                provenance=provenance,
                confidence=confidence,
                critical=False,
                feature_ref="outer_contour",
                consistency_state=consistency_state,
            )
    interface.dimensions = list(existing.values())
