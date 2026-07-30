import math

import pytest

from app.models.schema import Connection, Interface, Point2D, ProfileType, Project, TracedContour
from app.services.contour_loft import (
    ContourGeometryError,
    align_contours,
    align_contours_with_diagnostics,
    inward_offset,
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
