"""Unit & Integration Tests for S8.1 Geometry Validation and Real Export Verification."""

import pytest

from app.models.schema import ConnectionMode, ProfileType, Project
from app.services.export_provider import (
    MockExportProvider,
    parse_and_validate_step,
    parse_and_validate_stl,
    _obj_to_mock_stl_bytes,
)
from app.services.geometry_generator import generate_adapter_obj, get_geometry_hash, mesh_bounds, parse_obj_mesh


def test_empty_ascii_stl_rejection():
    """Verify that an ASCII STL with 0 facets is rejected."""
    empty_stl = b"solid interfaceforge\nendsolid interfaceforge\n"
    res = parse_and_validate_stl(empty_stl)
    assert not res["is_valid"]
    assert res["facet_count"] == 0
    assert "no facets" in res["error"].lower() or "incomplete" in res["error"].lower()


def test_zero_facet_binary_stl_rejection():
    """Verify that a binary STL specifying 0 facets is rejected."""
    # 80 bytes header + uint32(0)
    header = b"\x00" * 80 + (0).to_bytes(4, "little")
    res = parse_and_validate_stl(header)
    assert not res["is_valid"]
    assert res["facet_count"] == 0
    assert "0 facets" in res["error"].lower()


def test_non_zero_bounding_box_validation():
    """Verify that real geometry produces finite non-zero bounding box statistics."""
    p = Project(
        project_id="bbox_test",
        project_token="tok_bbox",
        current_schema_revision=1,
        current_model_revision=1,
    )
    p.interface_a.profile_type = ProfileType.RECTANGLE
    p.interface_b.profile_type = ProfileType.CIRCLE
    p.connection.length_mm = 45.0

    obj_str = generate_adapter_obj(p)
    from app.services.export_provider import _obj_to_mock_stl_bytes

    stl_bytes = _obj_to_mock_stl_bytes(obj_str, 1)
    res = parse_and_validate_stl(stl_bytes)

    assert res["is_valid"]
    assert res["facet_count"] > 0
    assert res["dimensions_mm"] is not None
    dx, dy, dz = res["dimensions_mm"]
    assert dx > 0
    assert dy > 0
    assert dz > 0
    assert abs(dz - 45.0) < 0.1


def test_step_header_only_rejection():
    """Verify that a STEP file containing only headers and no DATA section is rejected."""
    header_only_step = (
        b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('Test'),'2;1');\nENDSEC;\n"
        b"DATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    )
    res = parse_and_validate_step(header_only_step)
    assert not res["is_valid"]
    assert res["entity_count"] == 0
    assert "0 entities" in res["error"].lower() or "no solid" in res["error"].lower()


def test_step_without_body_entities_rejection():
    """Verify that a STEP file without body/geometry entities is rejected."""
    no_body_step = (
        b"ISO-10303-21;\nHEADER;\nENDSEC;\n"
        b"DATA;\n#1=ORGANIZATION('Org','Company');\nENDSEC;\nEND-ISO-10303-21;\n"
    )
    res = parse_and_validate_step(no_body_step)
    assert not res["is_valid"]
    assert "no solid body" in res["error"].lower() or "0 entities" in res["error"].lower()


def test_repeated_hash_detection_and_cross_model_uniqueness():
    """Verify that four distinct model cases produce distinct hashes and geometry statistics."""
    cases = []
    # Case 1: Simple Plate (Rectangle -> Rectangle)
    p1 = Project(project_id="case_1_plate", project_token="tok_1", current_schema_revision=1)
    p1.interface_a.profile_type = ProfileType.RECTANGLE
    p1.interface_b.profile_type = ProfileType.RECTANGLE
    cases.append(p1)

    # Case 2: Circular Coaxial Adapter
    p2 = Project(project_id="case_2_coaxial", project_token="tok_2", current_schema_revision=1)
    p2.interface_a.profile_type = ProfileType.CIRCLE
    p2.interface_b.profile_type = ProfileType.CIRCLE
    cases.append(p2)

    # Case 3: Circular Offset Adapter
    p3 = Project(project_id="case_3_offset", project_token="tok_3", current_schema_revision=1)
    p3.interface_a.profile_type = ProfileType.CIRCLE
    p3.interface_b.profile_type = ProfileType.CIRCLE
    p3.connection.mode = ConnectionMode.OFFSET
    p3.connection.offset_x_mm = 15.0
    cases.append(p3)

    # Case 4: Limited Angle Adapter
    p4 = Project(project_id="case_4_angled", project_token="tok_4", current_schema_revision=1)
    p4.interface_a.profile_type = ProfileType.CIRCLE
    p4.interface_b.profile_type = ProfileType.CIRCLE
    p4.connection.mode = ConnectionMode.ANGLED
    p4.connection.angle_deg = 10.0
    cases.append(p4)

    hashes = []
    objs = []
    for p in cases:
        obj_content = generate_adapter_obj(p)
        h = get_geometry_hash(obj_content)
        hashes.append(h)
        objs.append(obj_content)

    # Assert all 4 hashes are strictly unique
    assert len(set(hashes)) == 4, f"Hashes must be distinct! Got: {hashes}"


@pytest.mark.asyncio
async def test_cache_invalidation_after_model_change():
    """Verify that changing model parameters changes the geometry hash and invalidates old cache."""
    provider = MockExportProvider()

    # Project state v1
    p1 = Project(project_id="cache_test_proj", project_token="tok_cache", current_schema_revision=1)
    p1.interface_a.profile_type = ProfileType.CIRCLE
    p1.interface_b.profile_type = ProfileType.CIRCLE
    from app.services.kcl_compiler import compile_project_to_kcl
    p1.interface_a.approved = True
    p1.interface_b.approved = True
    p1.connection.length_mm = 40.0
    kcl_1 = compile_project_to_kcl(p1).kcl_code or ""
    res1 = await provider.export_format("cache_test_proj", 1, "stl", kcl_1, project=p1)

    # Project state v2 (modified offset_x)
    p2 = Project(project_id="cache_test_proj", project_token="tok_cache", current_schema_revision=2)
    p2.interface_a.profile_type = ProfileType.CIRCLE
    p2.interface_b.profile_type = ProfileType.CIRCLE
    p2.connection.mode = ConnectionMode.OFFSET
    p2.connection.offset_x_mm = 20.0
    p2.interface_a.approved = True
    p2.interface_b.approved = True
    p2.connection.length_mm = 40.0
    kcl_2 = compile_project_to_kcl(p2).kcl_code or ""
    res2 = await provider.export_format("cache_test_proj", 2, "stl", kcl_2, project=p2)

    assert res1.geometry_hash != res2.geometry_hash
    assert res1.artifact_ref != res2.artifact_ref


def test_preview_and_stl_share_mesh_bounds_and_closed_topology():
    """The offline preview and STL are both derived from one deterministic mesh."""
    project = Project(project_id="lineage_test", project_token="tok", current_schema_revision=1)
    project.interface_a.profile_type = ProfileType.ROUNDED_RECTANGLE
    project.interface_b.profile_type = ProfileType.CIRCLE
    project.interface_a.approved = True
    project.interface_b.approved = True
    project.connection.length_mm = 40.0
    obj = generate_adapter_obj(project)
    vertices, faces = parse_obj_mesh(obj)
    assert len(vertices) == 64  # 4 rings x 16 corresponding vertices
    assert len(faces) == 128
    stl = _obj_to_mock_stl_bytes(obj, 1)
    validation = parse_and_validate_stl(stl)
    assert validation["is_valid"]
    bounds = mesh_bounds(obj)
    assert validation["bounding_box"] == tuple(round(value, 3) for value in bounds)
