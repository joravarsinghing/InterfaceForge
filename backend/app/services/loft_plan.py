"""Single source of truth for aligned hollow loft geometry."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Sequence

from app.models.schema import (
    ConnectionMode,
    FitMode,
    Interface,
    LoftPlan,
    LoftSection,
    Point2D,
    ProfileType,
    Project,
)
from app.services.contour_loft import (
    align_contours,
    align_contours_with_diagnostics,
    choose_point_count,
    normalize_contour,
    prepare_interface_contours,
    resample_closed,
)

Point = tuple[float, float]
def _resample(points: Sequence[Point], count: int) -> list[Point]:
    clean = list(points)
    lengths = [math.dist(clean[i], clean[(i+1) % len(clean)]) for i in range(len(clean))]
    total = sum(lengths)
    result = []
    for sample in range(count):
        distance = total * sample / count
        walked = 0.0
        for i, length in enumerate(lengths):
            if distance <= walked + length or i == len(lengths) - 1:
                t = (distance - walked) / length if length else 0.0
                a, b = clean[i], clean[(i+1) % len(clean)]
                result.append((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t))
                break
            walked += length
    return result


def _dim(iface: Interface, name: str, default: float) -> float:
    for item in iface.dimensions:
        if item.id == name and math.isfinite(item.value) and item.value > 0:
            return float(item.value)
    return default


def _primitive(iface: Interface, count: int) -> list[Point]:
    if iface.traced_outer_contour is not None:
        return normalize_contour([(p.x, p.y) for p in iface.traced_outer_contour.points])
    if iface.profile_type == ProfileType.CIRCLE:
        r = _dim(iface, "outer_diameter", 50.0) / 2.0
        return normalize_contour([(r * math.cos(2 * math.pi * i / count), r * math.sin(2 * math.pi * i / count)) for i in range(count)])
    hw, hh = _dim(iface, "width", 50.0) / 2.0, _dim(iface, "height", 50.0) / 2.0
    if iface.profile_type == ProfileType.ROUNDED_RECTANGLE:
        r = min(_dim(iface, "corner_radius", 5.0), hw * 0.8, hh * 0.8)
        path: list[Point] = []
        centers = ((hw-r, hh-r, 0.0), (-hw+r, hh-r, math.pi/2), (-hw+r, -hh+r, math.pi), (hw-r, -hh+r, 3*math.pi/2))
        for cx, cy, start_angle in centers:
            for j in range(8):
                t = start_angle + (math.pi/2) * j / 8
                path.append((cx + r*math.cos(t), cy + r*math.sin(t)))
        return normalize_contour(path)
    return normalize_contour([(hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)])


def _interp(a: Sequence[Point], b: Sequence[Point], t: float) -> list[Point]:
    return [(x + (bx - x) * t, y + (by - y) * t) for (x, y), (bx, by) in zip(a, b)]


def _adaptive_count(a: Sequence[Point], b: Sequence[Point], length: float, ox: float, oy: float, angle: float) -> int:
    difference = sum(math.dist(x, y) for x, y in zip(a, b)) / max(len(a), 1)
    distortion = max(math.dist(a[i], a[(i + 1) % len(a)]) for i in range(len(a)))
    score = difference / max(distortion, 1.0) + math.hypot(ox, oy) / 25.0 + abs(angle) / 15.0 + length / 100.0
    return max(3, min(12, 3 + int(score)))


def build_loft_plan(project: Project) -> LoftPlan:
    a, b, c, m = project.interface_a, project.interface_b, project.connection, project.manufacturing
    seed_a = _primitive(a, 64)
    seed_b = _primitive(b, 64)
    count = min(128, max(32, choose_point_count(seed_a, seed_b)))

    target_a = resample_closed(_primitive(a, count), count)
    target_b_raw = resample_closed(_primitive(b, count), count)
    is_coaxial = c.mode == ConnectionMode.COAXIAL or c.mode == "coaxial"
    target_b = align_contours(target_a, target_b_raw, coaxial=is_coaxial)

    fit_mode_a = getattr(a, "fit_mode", FitMode.FIT_OVER) or FitMode.FIT_OVER
    fit_mode_b = getattr(b, "fit_mode", FitMode.FIT_OVER) or FitMode.FIT_OVER

    spec_a = prepare_interface_contours(target_a, fit_mode_a, m.clearance_a_mm, m.wall_thickness_mm)
    spec_b = prepare_interface_contours(target_b, fit_mode_b, m.clearance_b_mm, m.wall_thickness_mm)

    outer_a = spec_a.outer
    outer_b, od = align_contours_with_diagnostics(outer_a, spec_b.outer, coaxial=is_coaxial)

    inner_a = spec_a.inner
    inner_b, idg = align_contours_with_diagnostics(inner_a, spec_b.inner, coaxial=is_coaxial)

    section_count = _adaptive_count(outer_a, outer_b, c.length_mm, c.offset_x_mm, c.offset_y_mm, c.angle_deg)
    sections = []
    for k in range(section_count):
        t = k / (section_count - 1)
        sections.append(
            LoftSection(
                z_mm=c.length_mm * t,
                outer=[Point2D(x=x + c.offset_x_mm * t, y=y + c.offset_y_mm * t) for x, y in _interp(outer_a, outer_b, t)],
                inner=[Point2D(x=x + c.offset_x_mm * t, y=y + c.offset_y_mm * t) for x, y in _interp(inner_a, inner_b, t)],
            )
        )
    payload = {
        "schema_revision": "loft-plan-v1",
        "point_count": count,
        "outer_a": outer_a,
        "outer_b": outer_b,
        "inner_a": inner_a,
        "inner_b": inner_b,
        "sections": [s.model_dump() for s in sections],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return LoftPlan(
        geometry_hash=digest,
        point_count=count,
        outer_a=[Point2D(x=x, y=y) for x, y in outer_a],
        outer_b=[Point2D(x=x, y=y) for x, y in outer_b],
        inner_a=[Point2D(x=x, y=y) for x, y in inner_a],
        inner_b=[Point2D(x=x, y=y) for x, y in inner_b],
        target_a=[Point2D(x=x, y=y) for x, y in spec_a.target],
        target_b=[Point2D(x=x, y=y) for x, y in spec_b.target],
        mating_a=[Point2D(x=x, y=y) for x, y in spec_a.mating],
        mating_b=[Point2D(x=x, y=y) for x, y in spec_b.mating],
        fit_mode_a=fit_mode_a,
        fit_mode_b=fit_mode_b,
        clearance_a_mm=m.clearance_a_mm,
        clearance_b_mm=m.clearance_b_mm,
        wall_thickness_mm=m.wall_thickness_mm,
        outer_shift=od.shift,
        outer_reversed=od.reversed_target,
        inner_shift=idg.shift,
        inner_reversed=idg.reversed_target,
        sections=sections,
    )



def ensure_loft_plan(project: Project) -> LoftPlan:
    if project.loft_plan is None:
        project.loft_plan = build_loft_plan(project)
    return project.loft_plan




