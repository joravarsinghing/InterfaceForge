"""Deterministic arbitrary closed-contour preparation and hollow loft helpers.

The module deliberately has no primitive classifier.  It operates on the approved
outer loop only; holes remain a deferred capability for this experiment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from shapely.geometry import Polygon  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only in minimal installs

    Polygon = None  # type: ignore[assignment,misc]

from app.models.schema import FitMode

Point = tuple[float, float]


class ContourGeometryError(ValueError):
    """A contour cannot safely participate in a hollow loft."""


@dataclass(frozen=True)
class CorrespondenceDiagnostics:
    shift: int
    reversed_target: bool
    cost: float
    crossing_count: int
    tangent_cost: float
    displacement_cost: float
    seam_cost: float
    correspondence_lines: list[tuple[Point, Point]]


@dataclass(frozen=True)
class InterfaceContourSpec:
    target: list[Point]
    fit_mode: FitMode
    clearance: float
    mating: list[Point]
    outer: list[Point]
    inner: list[Point]
    wall_thickness: float


@dataclass(frozen=True)
class PreparedContours:
    outer_a: list[Point]
    outer_b: list[Point]
    inner_a: list[Point]
    inner_b: list[Point]
    point_count: int
    spec_a: InterfaceContourSpec | None = None
    spec_b: InterfaceContourSpec | None = None


def signed_area(points: Sequence[Point]) -> float:
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return (
        abs(_orientation(a, b, p)) <= 1e-8
        and min(a[0], b[0]) - 1e-8 <= p[0] <= max(a[0], b[0]) + 1e-8
        and min(a[1], b[1]) - 1e-8 <= p[1] <= max(a[1], b[1]) + 1e-8
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    if abs(o1) <= 1e-8 and _on_segment(a, b, c):
        return True
    if abs(o2) <= 1e-8 and _on_segment(a, b, d):
        return True
    if abs(o3) <= 1e-8 and _on_segment(c, d, a):
        return True
    if abs(o4) <= 1e-8 and _on_segment(c, d, b):
        return True
    eps = 1e-8
    return (((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)))


def is_simple(points: Sequence[Point]) -> bool:
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j in ((i - 1) % n, i, (i + 1) % n):
                continue
            if _segments_intersect(a, b, points[j], points[(j + 1) % n]):
                return False
    return True


def clean_contour(points: Iterable[Point], *, min_segment: float = 1e-6) -> list[Point]:
    result: list[Point] = []
    for raw in points:
        point = (float(raw[0]), float(raw[1]))
        if not all(math.isfinite(v) for v in point):
            raise ContourGeometryError("Contour contains a non-finite point.")
        if not result or math.dist(result[-1], point) >= min_segment:
            result.append(point)
    if len(result) > 1 and math.dist(result[0], result[-1]) < min_segment:
        result.pop()
    if len(result) < 3:
        raise ContourGeometryError("Contour needs at least three distinct points.")
    if not is_simple(result):
        raise ContourGeometryError("Outer contour self-intersects; generation was rejected.")
    if abs(signed_area(result)) <= 1e-8:
        raise ContourGeometryError("Contour has zero area and cannot form a profile.")
    return result


def ensure_ccw(points: Iterable[Point]) -> list[Point]:
    """Enforce counter-clockwise (positive signed area) winding without translating points."""
    clean = clean_contour(points)
    if signed_area(clean) < 0:
        return list(reversed(clean))
    return clean


def normalize_contour(points: Iterable[Point]) -> list[Point]:
    """Center a contour without changing its scale or shape."""
    clean = clean_contour(points)
    cx = sum(p[0] for p in clean) / len(clean)
    cy = sum(p[1] for p in clean) / len(clean)
    result = [(x - cx, y - cy) for x, y in clean]
    return ensure_ccw(result)


def resample_closed(points: Sequence[Point], count: int) -> list[Point]:
    clean = clean_contour(points)
    lengths = [math.dist(clean[i], clean[(i + 1) % len(clean)]) for i in range(len(clean))]
    perimeter = sum(lengths)
    if perimeter <= 1e-8:
        raise ContourGeometryError("Contour perimeter is too small.")
    result: list[Point] = []
    for sample in range(count):
        distance = perimeter * sample / count
        walked = 0.0
        for i, length in enumerate(lengths):
            if walked + length >= distance:
                fraction = (distance - walked) / length if length else 0.0
                a, b = clean[i], clean[(i + 1) % len(clean)]
                result.append((a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction))
                break
            walked += length
    return ensure_ccw(result)


def choose_point_count(a: Sequence[Point], b: Sequence[Point], tolerance_mm: float = 0.2) -> int:
    max_edge = max(
        max(math.dist(p, points[(i + 1) % len(points)]) for i, p in enumerate(points))
        for points in (a, b)
    )
    estimated = max(len(a), len(b), math.ceil(2.0 * math.pi * max_edge / max(tolerance_mm, 1e-3)))
    return min(256, max(32, int(estimated)))


def _crossing_count(source: Sequence[Point], target: Sequence[Point]) -> int:
    """Count non-adjacent correspondence segments that intersect in XY."""
    n = len(source)
    count = 0
    for i in range(n):
        a, b = source[i], target[i]
        for j in range(i + 1, n):
            if j in ((i - 1) % n, i, (i + 1) % n):
                continue
            if _segments_intersect(a, b, source[j], target[j]):
                count += 1
    return count


def _unit_tangent(points: Sequence[Point], index: int) -> Point:
    before = points[(index - 1) % len(points)]
    after = points[(index + 1) % len(points)]
    dx, dy = after[0] - before[0], after[1] - before[1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def _correspondence_cost(
    source: Sequence[Point],
    target: Sequence[Point],
    *,
    shift: int,
    coaxial: bool,
) -> tuple[float, float, float, float]:
    distances = [math.dist(source[i], target[i]) for i in range(len(source))]
    point_cost = sum(distance * distance for distance in distances) / len(source)
    tangent_cost = sum(
        1.0 - max(-1.0, min(1.0, _unit_tangent(source, i)[0] * _unit_tangent(target, i)[0]
        + _unit_tangent(source, i)[1] * _unit_tangent(target, i)[1]))
        for i in range(len(source))
    ) / len(source)
    line_vectors = [
        (target[i][0] - source[i][0], target[i][1] - source[i][1])
        for i in range(len(source))
    ]
    displacement_cost = sum(
        math.dist(line_vectors[i], line_vectors[(i - 1) % len(line_vectors)]) ** 2
        for i in range(len(line_vectors))
    ) / len(line_vectors)
    seam_cost = math.dist(line_vectors[-1], line_vectors[0]) ** 2
    seam_penalty = 0.25 * seam_cost
    rotation_penalty = (0.05 * min(shift, len(source) - shift)) if coaxial else 0.0
    return point_cost + tangent_cost + displacement_cost + seam_penalty + rotation_penalty, tangent_cost, displacement_cost, seam_cost


def align_contours_with_diagnostics(
    source: Sequence[Point],
    target: Sequence[Point],
    *,
    coaxial: bool = False,
) -> tuple[list[Point], CorrespondenceDiagnostics]:
    """Select an equal-count, same-winding, non-crossing contour correspondence."""
    if len(source) != len(target) or len(source) < 3:
        raise ContourGeometryError("Loft correspondence requires equal point counts.")
    source_clean = clean_contour(source)
    target_clean = clean_contour(target)
    source_area = signed_area(source_clean)
    if source_area < 0:
        source_clean.reverse()
        source_area = -source_area
    candidates = [(list(target_clean), False), (list(reversed(target_clean)), True)]
    best: tuple[float, list[Point], CorrespondenceDiagnostics] | None = None
    for oriented_target, reversed_target in candidates:
        if signed_area(oriented_target) * source_area <= 0:
            continue
        for shift in range(len(oriented_target)):
            aligned = [oriented_target[(i + shift) % len(oriented_target)] for i in range(len(oriented_target))]
            crossing_count = _crossing_count(source_clean, aligned)
            cost, tangent_cost, displacement_cost, seam_cost = _correspondence_cost(
                source_clean, aligned, shift=shift, coaxial=coaxial
            )
            cost += 1_000_000.0 * crossing_count
            diagnostics = CorrespondenceDiagnostics(
                shift=shift,
                reversed_target=reversed_target,
                cost=cost,
                crossing_count=crossing_count,
                tangent_cost=tangent_cost,
                displacement_cost=displacement_cost,
                seam_cost=seam_cost,
                correspondence_lines=list(zip(source_clean, aligned)),
            )
            if best is None or cost < best[0]:
                best = (cost, aligned, diagnostics)
    if best is None:
        raise ContourGeometryError("No non-crossing contour correspondence was found.")
    return best[1], best[2]


def align_contours(source: Sequence[Point], target: Sequence[Point], *, coaxial: bool = False) -> list[Point]:
    """Compatibility wrapper returning the selected target ring only."""
    return align_contours_with_diagnostics(source, target, coaxial=coaxial)[0]


def simplify_corners(points: Sequence[Point], angle_threshold_deg: float = 1.0) -> list[Point]:
    clean = clean_contour(points)
    n = len(clean)
    if n <= 4:
        return clean
    corners: list[Point] = []
    for i in range(n):
        p_prev = clean[(i - 1) % n]
        p_curr = clean[i]
        p_next = clean[(i + 1) % n]
        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        l1 = math.hypot(*v1)
        l2 = math.hypot(*v2)
        if l1 > 1e-6 and l2 > 1e-6:
            cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
            if cos_a < math.cos(math.radians(angle_threshold_deg)):
                corners.append(p_curr)
    return corners if len(corners) >= 3 else clean


def offset_contour(points: Sequence[Point], distance: float) -> list[Point]:
    """Offset a closed contour by distance (+ for outward, - for inward) in its exact coordinate frame."""
    if abs(distance) <= 1e-8:
        return ensure_ccw(points)

    clean = ensure_ccw(points)
    target_count = len(clean)

    if Polygon is not None:
        poly = Polygon(clean)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_valid:
            raise ContourGeometryError("Input contour is invalid for polygon offset.")
        buffered = poly.buffer(distance, join_style=2, mitre_limit=5.0)
        if buffered.is_empty:
            raise ContourGeometryError("Offset collapses at this distance.")
        if buffered.geom_type != "Polygon":
            raise ContourGeometryError("Offset splits into multiple polygons or disconnected geometry.")
        if not buffered.is_valid or buffered.area <= 1e-8:
            raise ContourGeometryError("Offset is invalid or has insufficient area.")
        coords = list(buffered.exterior.coords)
        if len(coords) > 1 and math.dist(coords[0], coords[-1]) < 1e-6:
            coords.pop()
        if len(coords) == target_count:
            return ensure_ccw(coords)
        resampled = resample_closed(coords, target_count)
        return ensure_ccw(resampled)

    simplified = simplify_corners(clean)
    n = len(simplified)
    normals: list[Point] = []
    for i in range(n):
        p1 = simplified[i]
        p2 = simplified[(i + 1) % n]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 1e-8:
            normals.append((0.0, 0.0))
        else:
            normals.append((dy / length, -dx / length))

    offset_corners: list[Point] = []
    for i in range(n):
        n1 = normals[(i - 1) % n]
        n2 = normals[i]
        sx, sy = n1[0] + n2[0], n1[1] + n2[1]
        s_len = math.hypot(sx, sy)
        if s_len <= 1e-8:
            raise ContourGeometryError("Offset collapses or forms degenerate spike.")
        bx, by = sx / s_len, sy / s_len
        dot = bx * n1[0] + by * n1[1]
        if dot <= 0.01:
            raise ContourGeometryError("Offset collapses at sharp vertex.")
        k = min(5.0, 1.0 / max(dot, 0.2))
        p = simplified[i]
        offset_corners.append((p[0] + distance * k * bx, p[1] + distance * k * by))

    offset_clean = clean_contour(offset_corners)
    if not is_simple(offset_clean) or abs(signed_area(offset_clean)) <= 1e-8:
        raise ContourGeometryError("Offset self-intersects or collapses at this distance.")

    if len(offset_clean) == target_count:
        return ensure_ccw(offset_clean)
    result = resample_closed(offset_clean, target_count)
    return ensure_ccw(result)





def offset_outward(points: Sequence[Point], distance: float) -> list[Point]:
    if distance < 0:
        raise ContourGeometryError("Outward offset distance must be non-negative.")
    return offset_contour(points, distance)


def offset_inward(points: Sequence[Point], distance: float) -> list[Point]:
    if distance < 0:
        raise ContourGeometryError("Inward offset distance must be non-negative.")
    return offset_contour(points, -distance)


def inward_offset(points: Sequence[Point], distance: float) -> list[Point]:
    """Compatibility wrapper for inward offset."""
    return offset_inward(points, distance)


def _dist_to_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq))
    proj = (a[0] + t * dx, a[1] + t * dy)
    return math.dist(p, proj)


def dist_to_loop_boundary(p: Point, loop: Sequence[Point]) -> float:
    n = len(loop)
    if n < 3:
        return 0.0
    return min(_dist_to_segment(p, loop[i], loop[(i + 1) % n]) for i in range(n))


def validate_profile_offset_pair(
    *,
    outer: Sequence[Point],
    inner: Sequence[Point],
    target: Sequence[Point],
    fit_mode: FitMode,
    clearance: float,
    wall_thickness: float,
) -> None:
    if len(outer) < 3 or len(inner) < 3:
        raise ContourGeometryError("Loops must have at least 3 points.")

    if not is_simple(outer) or not is_simple(inner):
        raise ContourGeometryError("Offset loop self-intersects or is invalid.")

    area_outer = signed_area(outer)
    area_inner = signed_area(inner)
    if area_outer <= 1e-8 or area_inner <= 1e-8:
        raise ContourGeometryError("Offset loop collapsed to near-zero area.")
    if area_inner >= area_outer:
        raise ContourGeometryError("Inner loop area must be strictly smaller than outer loop area.")

    if _crossing_count(outer, align_contours(outer, inner)) > 0:
        raise ContourGeometryError("Inner and outer wall boundaries intersect each other.")

    n_in = len(inner)
    n_out = len(outer)
    for i in range(n_in):
        a, b = inner[i], inner[(i + 1) % n_in]
        for j in range(n_out):
            c, d = outer[j], outer[(j + 1) % n_out]
            if _segments_intersect(a, b, c, d):
                raise ContourGeometryError("Inner and outer wall boundary segments cross.")

    tolerance = max(2.0, 1.25 * wall_thickness)
    for i in range(n_in):
        p1, p2 = inner[i], inner[(i + 1) % n_in]
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        dist = dist_to_loop_boundary(mid, outer)
        if abs(dist - wall_thickness) > tolerance + 1e-3:
            raise ContourGeometryError(
                f"Measured wall thickness at inner midpoint ({dist:.3f} mm) deviates from requested ({wall_thickness:.3f} mm) beyond tolerance ({tolerance:.3f} mm)."
            )


    min_inner_clearance = min(dist_to_loop_boundary(p, outer) for p in inner)
    if min_inner_clearance < 0.1:
        raise ContourGeometryError("Local collapse or apex bridge detected on inner boundary.")


def prepare_interface_contours(
    target_contour: Sequence[Point],
    fit_mode: FitMode,
    clearance: float,
    wall_thickness: float,
) -> InterfaceContourSpec:
    target = ensure_ccw(target_contour)
    if clearance < 0:
        raise ContourGeometryError("Clearance cannot be negative.")
    if wall_thickness <= 0:
        raise ContourGeometryError("Wall thickness must be positive.")

    if fit_mode == FitMode.FIT_OVER:
        mating = offset_outward(target, clearance)
        outer = offset_outward(mating, wall_thickness)
        outer = align_contours(mating, outer)
        inner = mating
    elif fit_mode == FitMode.FIT_INSIDE:
        mating = offset_inward(target, clearance)
        outer = mating
        inner = offset_inward(mating, wall_thickness)
        inner = align_contours(outer, inner)
    else:
        raise ContourGeometryError(f"Unsupported fit mode: {fit_mode}")

    validate_profile_offset_pair(
        outer=outer,
        inner=inner,
        target=target,
        fit_mode=fit_mode,
        clearance=clearance,
        wall_thickness=wall_thickness,
    )

    return InterfaceContourSpec(
        target=target,
        fit_mode=fit_mode,
        clearance=clearance,
        mating=mating,
        outer=outer,
        inner=inner,
        wall_thickness=wall_thickness,
    )


def prepare_contours(
    contour_a: Iterable[Point],
    contour_b: Iterable[Point],
    *,
    wall_thickness: float,
    clearance_a: float,
    clearance_b: float,
    fit_mode_a: FitMode = FitMode.FIT_OVER,
    fit_mode_b: FitMode = FitMode.FIT_OVER,
    tolerance_mm: float = 0.2,
    coaxial: bool = False,
) -> PreparedContours:
    target_a = normalize_contour(contour_a)
    target_b = normalize_contour(contour_b)
    count = choose_point_count(target_a, target_b, tolerance_mm)

    raw_target_a = resample_closed(target_a, count)
    raw_target_b = resample_closed(target_b, count)
    raw_target_b = align_contours(raw_target_a, raw_target_b, coaxial=coaxial)

    spec_a = prepare_interface_contours(raw_target_a, fit_mode_a, clearance_a, wall_thickness)
    spec_b = prepare_interface_contours(raw_target_b, fit_mode_b, clearance_b, wall_thickness)

    outer_a = spec_a.outer
    outer_b, _ = align_contours_with_diagnostics(outer_a, spec_b.outer, coaxial=coaxial)

    inner_a = spec_a.inner
    inner_b, _ = align_contours_with_diagnostics(inner_a, spec_b.inner, coaxial=coaxial)

    return PreparedContours(
        outer_a=outer_a,
        outer_b=outer_b,
        inner_a=inner_a,
        inner_b=inner_b,
        point_count=count,
        spec_a=spec_a,
        spec_b=spec_b,
    )
