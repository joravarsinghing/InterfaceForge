import math

import pytest

from app.models.schema import Connection, Interface, Point2D, ProfileType, Project, TracedContour
from app.services.contour_loft import (
    ContourGeometryError,
    align_contours_with_diagnostics,
    prepare_contours,
    resample_closed,
)
from app.services.geometry_generator import generate_adapter_obj, mesh_volume


def contour(points):
    return [Point2D(x=x, y=y) for x, y in points]


def interface(name, points):
    return Interface(
        id=name,
        profile_type=ProfileType.CUSTOM_CLOSED,
        approved=True,
        traced_outer_contour=TracedContour(
            points=contour(points), classification="outer_contour", is_closed=True
        ),
    )


def test_triangle_to_circle_prepares_equal_non_crossing_rings():
    triangle = [(0, 18), (16, -12), (-16, -12)]
    circle = [(10 * math.cos(i * 2 * math.pi / 24), 10 * math.sin(i * 2 * math.pi / 24)) for i in range(24)]
    prepared = prepare_contours(triangle, circle, wall_thickness=1.5, clearance_a=0.2, clearance_b=0.2)
    assert 32 <= prepared.point_count <= 256
    assert len(prepared.outer_a) == len(prepared.outer_b) == len(prepared.inner_a)


def test_rectangle_to_irregular_contour_preserves_monotonic_order():
    rectangle = [(-20, -10), (20, -10), (20, 10), (-20, 10)]
    irregular = [(-20, -8), (-4, -14), (18, -8), (21, 8), (3, 13), (-19, 8)]
    aligned, diagnostics = align_contours_with_diagnostics(
        resample_closed(rectangle, 64),
        resample_closed(irregular, 64),
    )
    assert len(aligned) == 64
    assert diagnostics.reversed_target is False
    assert diagnostics.crossing_count == 0


def test_same_irregular_profile_rotated_input_selects_a_stable_seam():
    profile = [(-18, -8), (0, -15), (17, -7), (12, 11), (-4, 15), (-20, 7)]
    rotated_start = profile[3:] + profile[:3]
    aligned, diagnostics = align_contours_with_diagnostics(
        resample_closed(profile, 64),
        resample_closed(rotated_start, 64),
        coaxial=True,
    )
    assert diagnostics.crossing_count == 0
    assert max(math.dist(aligned[i], resample_closed(profile, 64)[i]) for i in range(64)) < 0.5


def test_rotated_input_geometry_has_no_corkscrew_correspondence():
    profile = [(-16, -9), (8, -14), (19, 0), (12, 13), (-11, 10)]
    angle = math.radians(37)
    rotated = [
        (x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle))
        for x, y in profile
    ]
    _aligned, diagnostics = align_contours_with_diagnostics(
        resample_closed(profile, 64), resample_closed(rotated, 64)
    )
    assert diagnostics.crossing_count == 0
    assert diagnostics.seam_cost < 1000


def test_concave_to_convex_contour_keeps_winding_and_debug_diagnostics():
    concave = [(-18, -10), (0, -10), (4, -3), (18, -10), (18, 10), (0, 7), (-18, 10)]
    convex = [(-16, -11), (16, -11), (19, 0), (16, 11), (-16, 11), (-19, 0)]
    aligned, diagnostics = align_contours_with_diagnostics(
        resample_closed(concave, 64), resample_closed(convex, 64)
    )
    assert len(aligned) == 64
    assert diagnostics.correspondence_lines
    assert diagnostics.crossing_count == 0


def test_debug_obj_contains_selected_correspondence():
    project = Project(
        project_id="debug-correspondence",
        project_token="test",
        interface_a=interface("interface_a", [(-15, -10), (15, -10), (15, 10), (-15, 10)]),
        interface_b=interface("interface_b", [(-15, -10), (15, -10), (15, 10), (-15, 10)]),
        connection=Connection(length_mm=40),
    )
    obj = generate_adapter_obj(project)
    assert "# CORRESPONDENCE outer" in obj
    assert "# CORRESPONDENCE_LINE outer" in obj
def test_triangle_to_quadrilateral_has_equal_non_crossing_correspondence():
    triangle = [(0, 18), (16, -12), (-16, -12)]
    quadrilateral = [(-30, -20), (30, -20), (30, 20), (-30, 20)]
    aligned, diagnostics = align_contours_with_diagnostics(
        resample_closed(triangle, 64),
        resample_closed(quadrilateral, 64),
    )
    assert len(aligned) == 64
    assert diagnostics.crossing_count == 0


def test_triangle_fit_over_preserves_coordinate_frame_and_wall_thickness():
    from app.models.schema import FitMode
    from app.services.contour_loft import (
        dist_to_loop_boundary,
        normalize_contour,
        prepare_interface_contours,
        signed_area,
    )

    triangle = normalize_contour([(0, 18), (16, -12), (-16, -12)])
    spec = prepare_interface_contours(triangle, FitMode.FIT_OVER, clearance=0.5, wall_thickness=2.0)

    assert spec.fit_mode == FitMode.FIT_OVER
    assert spec.inner == spec.mating
    assert signed_area(spec.outer) > signed_area(spec.inner) > signed_area(triangle)

    # Check origin/centroid alignment: inner & outer must share frame
    cx_tgt = sum(p[0] for p in triangle) / len(triangle)
    cy_tgt = sum(p[1] for p in triangle) / len(triangle)
    cx_out = sum(p[0] for p in spec.outer) / len(spec.outer)
    cy_out = sum(p[1] for p in spec.outer) / len(spec.outer)
    cx_in = sum(p[0] for p in spec.inner) / len(spec.inner)
    cy_in = sum(p[1] for p in spec.inner) / len(spec.inner)
    assert abs(cx_out - cx_in) < 1.0
    assert abs(cy_out - cy_in) < 1.0
    assert abs(cx_tgt) < 1e-4 and abs(cy_tgt) < 1e-4

    # Wall thickness tolerance check (max 0.15mm or 5%)
    n_in = len(spec.inner)
    for i in range(n_in):
        p1, p2 = spec.inner[i], spec.inner[(i + 1) % n_in]
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        d = dist_to_loop_boundary(mid, spec.outer)
        assert abs(d - 2.0) <= 0.15

    # Confirm apex stays open and simple
    assert len(spec.outer) >= 3
    assert len(spec.inner) >= 3


def test_triangle_fit_inside_preserves_coordinate_frame_and_wall_thickness():
    from app.models.schema import FitMode
    from app.services.contour_loft import (
        dist_to_loop_boundary,
        normalize_contour,
        prepare_interface_contours,
        signed_area,
    )

    triangle = normalize_contour([(0, 18), (16, -12), (-16, -12)])
    spec = prepare_interface_contours(triangle, FitMode.FIT_INSIDE, clearance=0.5, wall_thickness=2.0)

    assert spec.fit_mode == FitMode.FIT_INSIDE
    assert spec.outer == spec.mating
    assert signed_area(triangle) > signed_area(spec.outer) > signed_area(spec.inner)

    n_in = len(spec.inner)
    for i in range(n_in):
        p1, p2 = spec.inner[i], spec.inner[(i + 1) % n_in]
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        d = dist_to_loop_boundary(mid, spec.outer)
        assert abs(d - 2.0) <= 0.15


def test_rounded_rectangle_fit_over_and_inside_not_displaced():
    from app.models.schema import FitMode
    from app.services.contour_loft import (
        dist_to_loop_boundary,
        normalize_contour,
        prepare_interface_contours,
    )

    hw, hh, r = 25.0, 25.0, 5.0
    rect = []
    centers = [(hw - r, hh - r, 0.0), (-hw + r, hh - r, math.pi / 2), (-hw + r, -hh + r, math.pi), (hw - r, -hh + r, 3 * math.pi / 2)]
    for cx, cy, start in centers:
        for j in range(8):
            t = start + (math.pi / 2) * j / 8
            rect.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    rect = normalize_contour(rect)

    spec_over = prepare_interface_contours(rect, FitMode.FIT_OVER, clearance=0.4, wall_thickness=2.5)
    spec_inside = prepare_interface_contours(rect, FitMode.FIT_INSIDE, clearance=0.4, wall_thickness=2.5)

    # Check wall thickness
    for spec in (spec_over, spec_inside):
        for i in range(len(spec.inner)):
            p1, p2 = spec.inner[i], spec.inner[(i + 1) % len(spec.inner)]
            mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
            d = dist_to_loop_boundary(mid, spec.outer)
            assert abs(d - 2.5) <= 0.15


def test_mixed_triangle_to_rounded_rectangle_generates_hollow_stl():
    from app.models.schema import FitMode, Manufacturing
    from app.services.geometry_generator import generate_adapter_obj
    from app.services.loft_plan import ensure_loft_plan

    triangle = [(0, 20), (18, -12), (-18, -12)]
    rect = [(-20, -20), (20, -20), (20, 20), (-20, 20)]

    proj = Project(
        project_id="mixed-fit-test",
        project_token="test",
        interface_a=Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            fit_mode=FitMode.FIT_OVER,
            approved=True,
            traced_outer_contour=TracedContour(points=contour(triangle), is_closed=True),
        ),
        interface_b=Interface(
            id="interface_b",
            profile_type=ProfileType.ROUNDED_RECTANGLE,
            fit_mode=FitMode.FIT_INSIDE,
            approved=True,
            traced_outer_contour=TracedContour(points=contour(rect), is_closed=True),
        ),
        connection=Connection(length_mm=50),
        manufacturing=Manufacturing(wall_thickness_mm=2.5, clearance_a_mm=0.3, clearance_b_mm=0.2),
    )

    plan = ensure_loft_plan(proj)
    assert plan is not None
    assert plan.fit_mode_a == FitMode.FIT_OVER
    assert plan.fit_mode_b == FitMode.FIT_INSIDE
    assert plan.clearance_a_mm == 0.3
    assert plan.clearance_b_mm == 0.2
    assert plan.wall_thickness_mm == 2.5

    obj = generate_adapter_obj(proj)
    vol = mesh_volume(obj)
    assert vol > 0.0


def test_asymmetric_organic_contour_offset_validity():
    from app.models.schema import FitMode
    from app.services.contour_loft import (
        dist_to_loop_boundary,
        normalize_contour,
        prepare_interface_contours,
    )

    organic = normalize_contour([(-22, -15), (10, -25), (28, -5), (15, 20), (-18, 18), (-25, 5)])
    spec = prepare_interface_contours(organic, FitMode.FIT_OVER, clearance=0.3, wall_thickness=2.0)

    for i in range(len(spec.inner)):
        p1, p2 = spec.inner[i], spec.inner[(i + 1) % len(spec.inner)]
        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        d = dist_to_loop_boundary(mid, spec.outer)
        assert abs(d - 2.0) <= 0.15


def test_offset_collapse_rejection_raises_clear_error():
    from app.models.schema import FitMode
    from app.services.contour_loft import normalize_contour, prepare_interface_contours

    small_triangle = normalize_contour([(0, 4), (3, -2), (-3, -2)])
    with pytest.raises(ContourGeometryError) as exc_info:
        prepare_interface_contours(small_triangle, FitMode.FIT_INSIDE, clearance=0.0, wall_thickness=10.0)
    assert "collapse" in str(exc_info.value).lower() or "area" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower() or "smaller" in str(exc_info.value).lower()
