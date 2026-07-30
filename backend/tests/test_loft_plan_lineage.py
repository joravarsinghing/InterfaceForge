import re
import pytest

from app.models.schema import Point2D, ProfileType, TracedContour
from app.services.geometry_generator import generate_adapter_obj, mesh_bounds, mesh_volume, parse_obj_mesh
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.loft_plan import ensure_loft_plan
from tests.test_kcl_compiler import create_base_approved_project


def _points_from_sketch(code: str, name: str):
    block = re.split(r"\n(?=sketch_)", code.split(f"sketch_{name} =", 1)[1], maxsplit=1)[0]
    start = re.search(r"startProfile\(at = \[([-0-9.]+), ([-0-9.]+)\]\)", block)
    assert start
    points = [(float(start.group(1)), float(start.group(2)))]
    for dx, dy in re.findall(r"line\(end = \[([-0-9.]+), ([-0-9.]+)\]\)", block):
        points.append((points[-1][0] + float(dx), points[-1][1] + float(dy)))
    assert points[-1] == pytest.approx(points[0], abs=1e-3)
    return points[:-1]


def test_triangle_to_rounded_rectangle_uses_one_polyline_plan():
    project = create_base_approved_project(ProfileType.TRACED_CLOSED, ProfileType.ROUNDED_RECTANGLE)
    project.interface_a.traced_outer_contour = TracedContour(
        points=[Point2D(x=0, y=0), Point2D(x=60, y=0), Point2D(x=30, y=40)], is_closed=True
    )
    result = compile_project_to_kcl(project, artifacts_dir="artifacts")
    assert result.success
    plan = project.loft_plan
    assert plan is not None
    assert 3 <= len(plan.sections) <= 12
    assert "tangentialArc" not in result.kcl_code
    assert result.kcl_code.count("|> close()") == len(plan.sections) * 2
    for index, section in enumerate(plan.sections):
        actual = _points_from_sketch(result.kcl_code, f"outer_{index}")
        expected = [(p.x, p.y) for p in section.outer]
        assert len(actual) == len(expected)
        assert all(abs(ax-ex) <= 1e-3 and abs(ay-ey) <= 1e-3 for (ax,ay),(ex,ey) in zip(actual, expected))
        actual = _points_from_sketch(result.kcl_code, f"inner_{index}")
        expected = [(p.x, p.y) for p in section.inner]
        assert len(actual) == len(expected)
        assert all(abs(ax-ex) <= 1e-3 and abs(ay-ey) <= 1e-3 for (ax,ay),(ex,ey) in zip(actual, expected))


def test_mock_mesh_uses_all_plan_sections_and_is_hollow():
    project = create_base_approved_project(ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED)
    project.interface_a.traced_outer_contour = TracedContour(
        points=[Point2D(x=-20, y=-12), Point2D(x=22, y=-10), Point2D(x=28, y=18), Point2D(x=-18, y=20)], is_closed=True
    )
    project.interface_b.traced_outer_contour = TracedContour(
        points=[Point2D(x=-15, y=-10), Point2D(x=20, y=-15), Point2D(x=26, y=12), Point2D(x=0, y=22), Point2D(x=-22, y=10)], is_closed=True
    )
    plan = ensure_loft_plan(project)
    obj = generate_adapter_obj(project)
    vertices, faces = parse_obj_mesh(obj)
    assert len(vertices) == len(plan.sections) * plan.point_count * 2
    assert len(faces) > 0
    assert mesh_volume(obj) > 0
    assert mesh_bounds(obj)[2] <= min(p.y for s in plan.sections for p in s.outer) + 1e-4

    assert "LoftPlan hash=" in obj





