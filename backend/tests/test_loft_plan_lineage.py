import re
import pytest

from app.models.schema import Point2D, ProfileType, TracedContour
from app.services.geometry_generator import generate_adapter_obj, mesh_bounds, mesh_volume, parse_obj_mesh
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.loft_plan import ensure_loft_plan
from tests.test_kcl_compiler import create_base_approved_project


def _points_from_sketch(code: str, name: str):
    target = "sketch" + "".join(part[:1].upper() + part[1:] for part in name.split("_"))
    block = re.split(r"\n(?=sketch[A-Z])", code.split(f"{target} =", 1)[1], maxsplit=1)[0]
    start = re.search(r"startProfile\(at = \[([-0-9.]+), ([-0-9.]+)\]\)", block)
    assert start
    points = [(float(start.group(1)), float(start.group(2)))]
    for dx, dy in re.findall(r"line\(end = \[([-0-9.]+), ([-0-9.]+)\]\)", block):
        points.append((points[-1][0] + float(dx), points[-1][1] + float(dy)))
    assert points[-1] == pytest.approx(points[0], abs=1e-3)
    return points[:-1]





