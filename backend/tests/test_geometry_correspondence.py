import math

from app.models.schema import ProfileType, Project
from app.services.export_provider import _obj_to_mock_stl_bytes, parse_and_validate_stl
from app.services.geometry_generator import (
    _sample_profile_2d,
    align_ring_correspondence,
    generate_adapter_obj,
    parse_obj_mesh,
    ring_signed_area,
)


def _project() -> Project:
    project = Project(
        project_id="circle-rounded-regression", project_token="tok", current_schema_revision=1
    )
    project.interface_a.profile_type = ProfileType.CIRCLE
    project.interface_b.profile_type = ProfileType.ROUNDED_RECTANGLE
    project.connection.length_mm = 40.0
    return project


def test_rounded_rectangle_is_one_continuous_uniform_perimeter() -> None:
    project = _project()
    ring = _sample_profile_2d(project.interface_b, True, 2.4, 0.1, 32)
    distances = [math.dist(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]
    assert len(ring) == 32
    assert all(distance > 0 for distance in distances)
    assert max(distances) / min(distances) < 1.35
    assert ring_signed_area(ring) > 0


def test_correspondence_uses_minimum_twist_cyclic_shift() -> None:
    source = [(math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i in range(8)]
    shifted = source[3:] + source[:3]
    assert align_ring_correspondence(source, shifted) == source


def test_coaxial_circle_to_rounded_loft_preserves_zero_seam_and_is_closed() -> None:
    obj = generate_adapter_obj(_project())
    vertices, faces = parse_obj_mesh(obj)
    assert len(vertices) == 64
    assert len(faces) == 128
    validation = parse_and_validate_stl(_obj_to_mock_stl_bytes(obj, 1))
    assert validation["is_valid"] is True
    assert validation["error"] == ""
    assert validation["dimensions_mm"] == (50.6, 50.6, 40.0)
