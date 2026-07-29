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
    TracedContour,
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


def primitive_boundary_points(
    profile_type: ProfileType,
    dimensions: list[Dimension],
    candidate_points: list[Point2D] | None = None,
) -> list[Point2D]:
    """Return canonical profile-space boundary points for primitive calibration."""
    finite_candidates = [
        p for p in (candidate_points or []) if math.isfinite(p.x) and math.isfinite(p.y)
    ]
    if len(finite_candidates) >= 4:
        return finite_candidates

    temp = Interface(id="primitive_boundary", profile_type=profile_type, dimensions=dimensions)
    size = primitive_size(temp)
    half_w = size.width / 2.0
    half_h = size.height / 2.0

    if profile_type == ProfileType.CIRCLE:
        radius = max(size.width, 1.0) / 2.0
        return [
            Point2D(
                x=round(radius * math.cos(2.0 * math.pi * i / 64), 4),
                y=round(radius * math.sin(2.0 * math.pi * i / 64), 4),
            )
            for i in range(64)
        ]

    if profile_type == ProfileType.RECTANGLE:
        return [
            Point2D(x=-half_w, y=-half_h),
            Point2D(x=half_w, y=-half_h),
            Point2D(x=half_w, y=half_h),
            Point2D(x=-half_w, y=half_h),
        ]

    if profile_type == ProfileType.ROUNDED_RECTANGLE:
        radius = min(max(size.corner_radius, 0.0), half_w, half_h)
        if radius <= 0:
            return [
                Point2D(x=-half_w, y=-half_h),
                Point2D(x=half_w, y=-half_h),
                Point2D(x=half_w, y=half_h),
                Point2D(x=-half_w, y=half_h),
            ]
        points: list[Point2D] = []
        centers = [
            (half_w - radius, half_h - radius, 0.0, math.pi / 2.0),
            (-half_w + radius, half_h - radius, math.pi / 2.0, math.pi),
            (-half_w + radius, -half_h + radius, math.pi, 3.0 * math.pi / 2.0),
            (half_w - radius, -half_h + radius, 3.0 * math.pi / 2.0, 2.0 * math.pi),
        ]
        for cx, cy, start, end in centers:
            for i in range(9):
                angle = start + (end - start) * i / 8.0
                points.append(
                    Point2D(
                        x=round(cx + radius * math.cos(angle), 4),
                        y=round(cy + radius * math.sin(angle), 4),
                    )
                )
        return points

    return finite_candidates


def primitive_boundary_contour(
    profile_type: ProfileType,
    dimensions: list[Dimension],
    candidate_points: list[Point2D] | None = None,
) -> TracedContour | None:
    points = primitive_boundary_points(profile_type, dimensions, candidate_points)
    if len(points) < 4:
        return None
    return TracedContour(
        id="outer_contour",
        points=points,
        is_closed=True,
        classification="outer_contour",
        provenance="opencv_primitive",
        confidence=1.0,
    )


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



def _segments_cross(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    def orient(p: Point2D, q: Point2D, r: Point2D) -> float:
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)

    return orient(a, c, d) * orient(b, c, d) < 0 and orient(a, b, c) * orient(a, b, d) < 0


def _self_intersects(points: list[Point2D]) -> bool:
    count = len(points)
    if count < 4:
        return False
    for idx in range(count):
        a = points[idx]
        b = points[(idx + 1) % count]
        for other in range(idx + 2, count):
            if idx == 0 and other == count - 1:
                continue
            c = points[other]
            d = points[(other + 1) % count]
            if _segments_cross(a, b, c, d):
                return True
    return False


def _perimeter(points: list[Point2D]) -> float:
    return sum(
        math.hypot(
            points[(idx + 1) % len(points)].x - points[idx].x,
            points[(idx + 1) % len(points)].y - points[idx].y,
        )
        for idx in range(len(points))
    )


def _polygon_area(points: list[Point2D]) -> float:
    return abs(
        sum(
            points[idx].x * points[(idx + 1) % len(points)].y
            - points[(idx + 1) % len(points)].x * points[idx].y
            for idx in range(len(points))
        )
    ) / 2.0


def _sharp_corner_count(points: list[Point2D], threshold_degrees: float = 38.0) -> int:
    count = 0
    for idx, point in enumerate(points):
        prev = points[idx - 1]
        nxt = points[(idx + 1) % len(points)]
        v1 = (prev.x - point.x, prev.y - point.y)
        v2 = (nxt.x - point.x, nxt.y - point.y)
        len1 = math.hypot(*v1)
        len2 = math.hypot(*v2)
        if len1 <= 1e-6 or len2 <= 1e-6:
            continue
        dot = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)))
        angle = math.degrees(math.acos(dot))
        turn = abs(180.0 - angle)
        if turn >= threshold_degrees:
            count += 1
    return count


def classify_primitive_candidate(points: list[Point2D]) -> Optional[PrimitiveClassification]:
    finite_points = [p for p in points if math.isfinite(p.x) and math.isfinite(p.y)]
    box = bbox(finite_points)
    if box is None or len(finite_points) < 4 or _self_intersects(finite_points):
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

    area = _polygon_area(finite_points)
    perimeter = _perimeter(finite_points)
    circularity = (4.0 * math.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
    sharp_corners = _sharp_corner_count(finite_points)

    radii = [math.hypot(p.x - cx, p.y - cy) for p in finite_points]
    mean_radius = sum(radii) / len(radii)
    radial_rms = math.sqrt(sum((r - mean_radius) ** 2 for r in radii) / len(radii))
    radial_max = max(abs(r - mean_radius) for r in radii)
    aspect_error = abs(width - height) / max_dim
    radial_rms_ratio = radial_rms / max(mean_radius, 1e-6)
    radial_max_ratio = radial_max / max(mean_radius, 1e-6)
    circle_score = 1.0 - max(
        aspect_error / 0.05,
        radial_rms_ratio / 0.035,
        max(0.0, 0.88 - circularity) / 0.12,
        max(0, sharp_corners - 2) / 4.0,
    )
    if (
        len(finite_points) >= 12
        and aspect_error <= 0.05
        and radial_rms_ratio <= 0.035
        and radial_max_ratio <= 0.085
        and circularity >= 0.88
        and sharp_corners <= 2
    ):
        return PrimitiveClassification(
            ProfileType.CIRCLE,
            confidence=round(max(0.85, min(0.99, 0.90 + 0.09 * circle_score)), 4),
            reason="radial_error_within_circle_threshold",
        )

    side_tol = 0.025 * max_dim
    corner_tol = 0.06 * max_dim
    side_distances = _point_side_distances(finite_points, box)
    on_sides_ratio = sum(1 for d in side_distances if d <= side_tol) / len(finite_points)
    near_corner_count = sum(
        1
        for p in finite_points
        if abs(abs(p.x - cx) - width / 2.0) <= corner_tol
        and abs(abs(p.y - cy) - height / 2.0) <= corner_tol
    )
    unique_side_hits = {
        side
        for p in finite_points
        for side, is_hit in (
            ("left", abs(p.x - min_x) <= side_tol),
            ("right", abs(p.x - max_x) <= side_tol),
            ("bottom", abs(p.y - min_y) <= side_tol),
            ("top", abs(p.y - max_y) <= side_tol),
        )
        if is_hit
    }
    if (
        len(finite_points) <= 8
        and on_sides_ratio >= 0.95
        and near_corner_count >= 4
        and len(unique_side_hits) == 4
        and sharp_corners >= 4
    ):
        return PrimitiveClassification(
            ProfileType.RECTANGLE,
            confidence=0.94,
            reason="all_points_lie_on_four_bbox_sides",
        )

    offsets = _corner_offsets(finite_points, box)
    radius_px = sum(offsets) / len(offsets) if offsets else 0.0
    radius_ratio = radius_px / max(min_dim, 1e-6)
    radius_spread = (max(offsets) - min(offsets)) / max(radius_px, 1e-6) if offsets else 1.0
    horizontal_support = any(abs(p.y - min_y) <= side_tol for p in finite_points) and any(
        abs(p.y - max_y) <= side_tol for p in finite_points
    )
    vertical_support = any(abs(p.x - min_x) <= side_tol for p in finite_points) and any(
        abs(p.x - max_x) <= side_tol for p in finite_points
    )
    rounded_confidence = 1.0 - max(
        max(0.0, radius_spread - 0.35) / 0.65,
        0.0 if 0.03 <= radius_ratio <= 0.35 else 1.0,
        0.0 if on_sides_ratio >= 0.60 else (0.60 - on_sides_ratio) / 0.60,
    )
    if (
        len(finite_points) >= 8
        and horizontal_support
        and vertical_support
        and 0.03 <= radius_ratio <= 0.35
        and radius_spread <= 0.65
        and on_sides_ratio >= 0.55
        and 2 <= sharp_corners <= 8
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
