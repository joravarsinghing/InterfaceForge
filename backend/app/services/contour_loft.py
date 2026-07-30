"""Deterministic arbitrary closed-contour preparation and hollow loft helpers.

The module deliberately has no primitive classifier.  It operates on the approved
outer loop only; holes remain a deferred capability for this experiment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from shapely.geometry import Polygon
except ImportError:  # pragma: no cover - exercised only in minimal installs
    Polygon = None  # type: ignore[assignment,misc]

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
class PreparedContours:
    outer_a: list[Point]
    outer_b: list[Point]
    inner_a: list[Point]
    inner_b: list[Point]
    point_count: int


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


def normalize_contour(points: Iterable[Point]) -> list[Point]:
    """Center a contour without changing its scale or shape."""
    clean = clean_contour(points)
    cx = sum(p[0] for p in clean) / len(clean)
    cy = sum(p[1] for p in clean) / len(clean)
    result = [(x - cx, y - cy) for x, y in clean]
    if signed_area(result) < 0:
        result.reverse()
    return result


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
    return result


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
            # Prefer zero-crossing candidates. If two dissimilar valid profiles
            # have no zero-crossing straight-line map, retain the least-crossing
            # monotonic map so generation remains possible and diagnostics expose it.
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

def inward_offset(points: Sequence[Point], distance: float) -> list[Point]:
    if distance <= 0:
        raise ContourGeometryError("Wall thickness and clearance leave no positive offset distance.")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if distance >= min(max(xs) - min(xs), max(ys) - min(ys)) / 2.0:
        raise ContourGeometryError("Inner offset collapses at this wall thickness.")
    if Polygon is not None:
        polygon = Polygon(points)
        inner = polygon.buffer(-distance, join_style=2, mitre_limit=2.0)
        if inner.is_empty or inner.geom_type != "Polygon":
            raise ContourGeometryError("Inner offset collapses or becomes disconnected at this wall thickness.")
        if not inner.is_valid or inner.area <= 1e-8:
            raise ContourGeometryError("Inner offset is invalid or has insufficient area.")
        coords = list(inner.exterior.coords)[:-1]
        return normalize_contour(coords)

    # Dependency-free fallback: intersect adjacent inward-shifted edge lines.
    # It is exact for convex profiles and rejects concave cases that become unsafe.
    clean = normalize_contour(points)
    reduced: list[Point] = []
    for point in clean:
        while len(reduced) >= 2 and abs(_orientation(reduced[-2], reduced[-1], point)) <= 0.5:
            reduced.pop()
        reduced.append(point)
    if len(reduced) >= 3 and abs(_orientation(reduced[-2], reduced[-1], reduced[0])) <= 0.5:
        reduced.pop()
    clean = reduced
    if signed_area(clean) < 0:
        clean.reverse()
    shifted: list[tuple[Point, Point]] = []
    for i, start in enumerate(clean):
        end = clean[(i + 1) % len(clean)]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-8:
            raise ContourGeometryError("Inner offset contains a zero-length edge.")
        nx, ny = -dy / length, dx / length
        shifted.append(((start[0] + distance * nx, start[1] + distance * ny),
                        (end[0] + distance * nx, end[1] + distance * ny)))
    result: list[Point] = []
    for i, (_, edge_end) in enumerate(shifted):
        prev_start, prev_end = shifted[i - 1]
        ax, ay = prev_start; bx, by = prev_end
        cx, cy = shifted[i][0]; dx, dy = edge_end
        cross = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
        if abs(cross) <= 1e-8:
            raise ContourGeometryError("Inner offset has parallel adjacent edges and collapses.")
        t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / cross
        result.append((ax + t * (bx - ax), ay + t * (by - ay)))
    if not is_simple(result) or abs(signed_area(result)) <= 1e-8:
        cx = sum(point[0] for point in clean) / len(clean)
        cy = sum(point[1] for point in clean) / len(clean)
        mean_radius = sum(math.dist((cx, cy), point) for point in clean) / len(clean)
        if mean_radius <= distance:
            raise ContourGeometryError("Inner offset self-intersects or collapses at this wall thickness.")
        factor = (mean_radius - distance) / mean_radius
        radial = [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in clean]
        if not is_simple(radial) or abs(signed_area(radial)) <= 1e-8:
            raise ContourGeometryError("Inner offset self-intersects or collapses at this wall thickness.")
        return normalize_contour(radial)
    return normalize_contour(result)


def prepare_contours(
    contour_a: Iterable[Point], contour_b: Iterable[Point],
    *, wall_thickness: float, clearance_a: float, clearance_b: float,
    tolerance_mm: float = 0.2, coaxial: bool = False,
) -> PreparedContours:
    outer_a = normalize_contour(contour_a)
    outer_b = normalize_contour(contour_b)
    count = choose_point_count(outer_a, outer_b, tolerance_mm)
    outer_a = resample_closed(outer_a, count)
    outer_b = resample_closed(outer_b, count)
    outer_b = align_contours(outer_a, outer_b, coaxial=coaxial)
    inner_a = inward_offset(outer_a, wall_thickness + clearance_a)
    inner_b = inward_offset(outer_b, wall_thickness + clearance_b)
    inner_a = resample_closed(inner_a, count)
    inner_b = align_contours(inner_a, resample_closed(inner_b, count), coaxial=coaxial)
    return PreparedContours(outer_a, outer_b, inner_a, inner_b, count)


