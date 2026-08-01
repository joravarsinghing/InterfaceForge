import math

import pytest

from app.models.schema import Connection, ConnectionMode, Project
from app.services.geometry_generator import generate_adapter_obj, get_geometry_hash
from app.services.loft_plan import ensure_loft_plan


def test_limited_angle_changes_loft_sections_and_mesh_geometry():
    straight = Project(project_id="straight", project_token="test")
    straight.connection = Connection(length_mm=80, mode=ConnectionMode.ANGLED, angle_deg=0)
    angled = straight.model_copy(deep=True)
    angled.project_id = "angled"
    angled.connection.angle_deg = 20

    straight_plan = ensure_loft_plan(straight)
    angled_plan = ensure_loft_plan(angled)
    straight_top = straight_plan.sections[-1].outer[0]
    angled_top = angled_plan.sections[-1].outer[0]

    assert angled_top.y - straight_top.y == pytest.approx(80 * math.tan(math.radians(20)))
    assert angled_plan.geometry_hash != straight_plan.geometry_hash
    assert get_geometry_hash(generate_adapter_obj(angled)) != get_geometry_hash(
        generate_adapter_obj(straight)
    )
