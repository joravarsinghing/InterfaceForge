import re

import pytest

from app.models.schema import (
    Connection,
    Dimension,
    Interface,
    Manufacturing,
    Point2D,
    ProfileType,
    Project,
    ScaleCalibration,
    TracedContour,
)
from app.services.connection_validation import validate_connection_and_manufacturing
from app.services.geometry_generator import generate_adapter_obj, mesh_bounds
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.loft_plan import calibrated_contour_mm, ensure_loft_plan


def square(size=100):
    return [Point2D(x=0, y=0), Point2D(x=size, y=0), Point2D(x=size, y=size), Point2D(x=0, y=size)]


def traced(name, scale, *, source=True):
    return Interface(
        id=name,
        source_image_ref=f"{name}.png" if source else None,
        profile_type=ProfileType.CUSTOM_CLOSED,
        approved=True,
        traced_outer_contour=TracedContour(points=square(), is_closed=True),
        scale_calibration=ScaleCalibration(
            source="user_calibration",
            method="two_point_trace",
            pixel_distance=100,
            real_distance_mm=100 * scale,
            scale_factor=scale,
            confirmed=True,
        ),
    )


def project(a, b):
    return Project(
        project_id="calibrated-scale",
        project_token="test",
        interface_a=a,
        interface_b=b,
        connection=Connection(length_mm=40),
        manufacturing=Manufacturing(wall_thickness_mm=1, clearance_a_mm=0, clearance_b_mm=0),
    )


def width(points):
    return max(p.x for p in points) - min(p.x for p in points)


def test_recalibration_rebuilds_every_derived_geometry():
    p = project(traced("interface_a", 0.4), traced("interface_b", 0.4))
    first = ensure_loft_plan(p)
    first_width = width(first.target_a)
    first_bounds = mesh_bounds(generate_adapter_obj(p))

    p.interface_a.scale_calibration.scale_factor = 0.8
    p.interface_a.scale_calibration.real_distance_mm = 80
    p.interface_b.scale_calibration.scale_factor = 0.8
    p.interface_b.scale_calibration.real_distance_mm = 80
    second = ensure_loft_plan(p)
    second_bounds = mesh_bounds(generate_adapter_obj(p))

    assert first_width == pytest.approx(40)
    assert width(second.target_a) == pytest.approx(80)
    assert second.geometry_hash != first.geometry_hash
    # Fixed 1 mm walls remain in mm, so the scaled opening span doubles.
    assert (second_bounds[1] - second_bounds[0] - 2) == pytest.approx(
        2 * (first_bounds[1] - first_bounds[0] - 2), abs=0.1
    )


def test_identical_traces_with_40_and_80_mm_calibration_are_two_to_one():
    p = project(traced("interface_a", 0.4), traced("interface_b", 0.8))
    plan = ensure_loft_plan(p)
    assert width(plan.target_b) == pytest.approx(2 * width(plan.target_a))


def test_invalid_image_calibration_blocks_generation_with_clear_message():
    a = traced("interface_a", 0.0)
    a.scale_calibration.confirmed = False
    b = traced("interface_b", 0.4)
    validation = validate_connection_and_manufacturing(
        a, b, Connection(length_mm=40), Manufacturing()
    )
    assert any(error.id == "IF-CAL-001" for error in validation.blocking_errors)
    with pytest.raises(ValueError, match="Confirm one known distance for this outline"):
        calibrated_contour_mm(a)


def test_primitive_promotion_uses_calibrated_dimensions_once():
    primitive = Interface(
        id="interface_a",
        source_image_ref="circle.png",
        profile_type=ProfileType.CIRCLE,
        approved=True,
        traced_outer_contour=TracedContour(
            points=square(), is_closed=True, provenance="opencv_primitive"
        ),
        dimensions=[
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=40,
                feature_ref="outer_contour",
            )
        ],
        scale_calibration=ScaleCalibration(
            scale_factor=0.4, real_distance_mm=40, pixel_distance=100, confirmed=True
        ),
    )
    contour = calibrated_contour_mm(primitive, 64)
    assert max(x for x, _ in contour) - min(x for x, _ in contour) == pytest.approx(40, abs=0.2)
