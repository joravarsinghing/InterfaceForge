import pytest

from app.models.schema import Connection, ConnectionMode, Project
from app.services.loft_plan import ensure_loft_plan


@pytest.mark.parametrize("mode", [ConnectionMode.COAXIAL, ConnectionMode.OFFSET])
def test_profile_extensions_add_straight_sections_for_all_modes(mode):
    project = Project(project_id=f"extensions-{mode.value}", project_token="test")
    project.connection = Connection(
        mode=mode, length_mm=40, offset_x_mm=8 if mode != ConnectionMode.COAXIAL else 0,
        extension_a_mm=10, extension_b_mm=12,
    )

    plan = ensure_loft_plan(project)

    assert plan.sections[0].z_mm == pytest.approx(0)
    assert plan.sections[1].z_mm == pytest.approx(10)
    assert plan.sections[-2].z_mm == pytest.approx(50)
    assert plan.sections[-1].z_mm == pytest.approx(62)
    assert plan.sections[0].outer[0] == plan.sections[1].outer[0]
    assert plan.sections[-2].outer[0] == plan.sections[-1].outer[0]


def test_zero_extensions_preserve_existing_section_layout():
    project = Project(project_id="baseline", project_token="test")
    project.connection = Connection(length_mm=40)
    plan = ensure_loft_plan(project)

    assert plan.sections[0].z_mm == pytest.approx(0)
    assert plan.sections[-1].z_mm == pytest.approx(40)
