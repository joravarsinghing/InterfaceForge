"""P0 golden-path primitive detection and per-interface fit intent tests."""

import pytest

from app.core.exceptions import InvalidInterfaceApprovalError
from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    DimensionProvenance,
    FitMode,
    Interface,
    Manufacturing,
    ManufacturingProcess,
    Point2D,
    ProfileType,
    Project,
    ScaleCalibration,
    TracedContour,
    TwoPointScaleCalibrationRequest,
)
from app.services.connection_validation import validate_connection_and_manufacturing
from app.services.kcl_compiler import compile_project_to_kcl
from app.services.profile_geometry import (
    classify_primitive_candidate,
    classify_primitive_from_points,
    fitted_profile_size,
    set_calibrated_primitive_dimensions,
)
from app.services.project_service import ProjectService


def circle_points(radius: float = 50.0, count: int = 32) -> list[Point2D]:
    import math

    return [
        Point2D(
            x=round(radius * math.cos(2 * math.pi * idx / count), 4),
            y=round(radius * math.sin(2 * math.pi * idx / count), 4),
        )
        for idx in range(count)
    ]


def rounded_rect_points(width: float = 120.0, height: float = 80.0) -> list[Point2D]:
    return [
        Point2D(x=-48, y=-40),
        Point2D(x=48, y=-40),
        Point2D(x=60, y=-28),
        Point2D(x=60, y=28),
        Point2D(x=48, y=40),
        Point2D(x=-48, y=40),
        Point2D(x=-60, y=28),
        Point2D(x=-60, y=-28),
    ]


def rectangle_points(width: float = 120.0, height: float = 80.0) -> list[Point2D]:
    return [
        Point2D(x=-width / 2, y=-height / 2),
        Point2D(x=width / 2, y=-height / 2),
        Point2D(x=width / 2, y=height / 2),
        Point2D(x=-width / 2, y=height / 2),
    ]


def irregular_points() -> list[Point2D]:
    return [
        Point2D(x=-52, y=-36),
        Point2D(x=44, y=-42),
        Point2D(x=67, y=-19),
        Point2D(x=58, y=31),
        Point2D(x=12, y=47),
        Point2D(x=-43, y=33),
        Point2D(x=-71, y=4),
        Point2D(x=-59, y=-24),
    ]


def approved_interface(
    interface_id: str, profile_type: ProfileType, fit_mode: FitMode
) -> Interface:
    if profile_type == ProfileType.CIRCLE:
        dims = [
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=50.0,
                provenance=DimensionProvenance.USER_ENTERED,
            ),
            Dimension(
                id="overall_width",
                label="Overall Width",
                value=50.0,
                provenance=DimensionProvenance.USER_ENTERED,
            ),
        ]
    else:
        dims = [
            Dimension(
                id="width", label="Width", value=80.0, provenance=DimensionProvenance.USER_ENTERED
            ),
            Dimension(
                id="height", label="Height", value=50.0, provenance=DimensionProvenance.USER_ENTERED
            ),
            Dimension(
                id="corner_radius",
                label="Corner Radius",
                value=6.0,
                provenance=DimensionProvenance.USER_ENTERED,
                critical=False,
            ),
        ]
    return Interface(
        id=interface_id,
        profile_type=profile_type,
        dimensions=dims,
        fit_mode=fit_mode,
        approved=True,
        approved_at="2026-07-29T00:00:00Z",
    )


def project_for_modes(mode_a: FitMode, mode_b: FitMode) -> Project:
    return Project(
        project_id=f"fit-{mode_a.value}-{mode_b.value}",
        project_token="tok_fit",
        current_schema_revision=4,
        interface_a=approved_interface("interface_a", ProfileType.CIRCLE, mode_a),
        interface_b=approved_interface("interface_b", ProfileType.ROUNDED_RECTANGLE, mode_b),
        connection=Connection(mode=ConnectionMode.COAXIAL, length_mm=60.0),
        manufacturing=Manufacturing(
            process=ManufacturingProcess.FDM,
            material="PETG",
            wall_thickness_mm=2.0,
            clearance_a_mm=0.5,
            clearance_b_mm=0.25,
        ),
    )


def test_primitive_recognition_requires_explicit_confidence_thresholds() -> None:
    circle = classify_primitive_candidate(circle_points())
    rectangle = classify_primitive_candidate(rectangle_points())
    rounded = classify_primitive_candidate(rounded_rect_points())

    assert circle is not None
    assert circle.profile_type == ProfileType.CIRCLE
    assert circle.confidence >= 0.85
    assert circle.reason == "radial_error_within_circle_threshold"

    assert rectangle is not None
    assert rectangle.profile_type == ProfileType.RECTANGLE
    assert rectangle.confidence >= 0.90
    assert rectangle.reason == "all_points_lie_on_four_bbox_sides"

    assert rounded is not None
    assert rounded.profile_type == ProfileType.ROUNDED_RECTANGLE
    assert rounded.confidence >= 0.65
    assert rounded.corner_radius_px is not None
    assert rounded.corner_radius_confidence >= 0.75
    assert rounded.reason == "corner_offsets_support_rounded_rectangle"


def test_irregular_contour_stays_traced_closed() -> None:
    assert classify_primitive_candidate(irregular_points()) is None
    assert classify_primitive_from_points(irregular_points()) is None


def test_rounded_rectangle_radius_estimated_from_trace_when_confident() -> None:
    interface = Interface(
        id="interface_a",
        profile_type=ProfileType.ROUNDED_RECTANGLE,
        traced_outer_contour=TracedContour(
            id="outer_contour",
            points=rounded_rect_points(),
            classification="outer_contour",
            provenance="analysis",
        ),
    )

    set_calibrated_primitive_dimensions(interface, 0.5)
    radius = next(dim for dim in interface.dimensions if dim.id == "corner_radius")

    assert radius.provenance == DimensionProvenance.IMAGE_EXTRACTED
    assert radius.confidence >= 0.75
    assert radius.consistency_state == "estimated_from_trace"
    assert radius.value > 0


def test_rounded_rectangle_uncertain_radius_requires_confirmation() -> None:
    interface = Interface(
        id="interface_a",
        profile_type=ProfileType.ROUNDED_RECTANGLE,
        traced_outer_contour=TracedContour(
            id="outer_contour",
            points=irregular_points(),
            classification="outer_contour",
            provenance="analysis",
        ),
    )

    set_calibrated_primitive_dimensions(interface, 0.5)
    radius = next(dim for dim in interface.dimensions if dim.id == "corner_radius")

    assert radius.provenance == DimensionProvenance.SYSTEM_INFERRED
    assert radius.confidence == 0.45
    assert radius.consistency_state == "requires_confirmation"


def test_confirmed_primitive_two_point_calibration_derives_dimensions() -> None:
    service = ProjectService()
    project = service.create_project()
    project.interface_a.profile_type = ProfileType.CIRCLE
    project.interface_a.traced_outer_contour = TracedContour(
        id="outer_contour",
        points=circle_points(50.0),
        classification="outer_contour",
        provenance="analysis",
    )
    project.interface_a.scale_calibration = ScaleCalibration(
        confirmed=False, pixel_distance=100.0, real_distance_mm=40.0
    )
    service.repository.save(project)

    updated = service.calibrate_interface_scale(
        project.project_id,
        "interface_a",
        TwoPointScaleCalibrationRequest(
            point_a=Point2D(x=-50, y=0),
            point_b=Point2D(x=50, y=0),
            real_distance_mm=40.0,
            confirmed=True,
        ),
        project.project_token,
    )
    dims = {dim.id: dim.value for dim in updated.interface_a.dimensions}
    assert updated.interface_a.scale_calibration.confirmed is True
    assert dims["outer_diameter"] == 40.0


def test_fit_mode_persists_and_hydrates_without_clearing_approval() -> None:
    service = ProjectService()
    project = service.create_project()
    project.interface_a = approved_interface("interface_a", ProfileType.CIRCLE, FitMode.FIT_OVER)
    service.repository.save(project)

    from app.models.schema import InterfacePatchRequest

    updated = service.patch_interface(
        project.project_id,
        "interface_a",
        InterfacePatchRequest(fit_mode=FitMode.FIT_INSIDE),
        project.project_token,
    )
    reloaded = service.get_project(project.project_id, project.project_token)
    assert updated.interface_a.approved is True
    assert reloaded.interface_a.fit_mode == FitMode.FIT_INSIDE


def test_all_four_fit_combinations_validate_and_compile(tmp_path) -> None:
    for mode_a in (FitMode.FIT_OVER, FitMode.FIT_INSIDE):
        for mode_b in (FitMode.FIT_OVER, FitMode.FIT_INSIDE):
            project = project_for_modes(mode_a, mode_b)
            validation = validate_connection_and_manufacturing(
                project.interface_a, project.interface_b, project.connection, project.manufacturing
            )
            assert validation.is_valid is True, (mode_a, mode_b, validation.blocking_errors)
            result = compile_project_to_kcl(project, artifacts_dir=str(tmp_path))
            assert result.success is True
            assert 'const interface_a_type = "circle"' in result.kcl_code
            assert 'const interface_b_type = "rounded_rectangle"' in result.kcl_code


def test_clearance_formulas_for_fit_modes() -> None:
    iface = approved_interface("interface_a", ProfileType.CIRCLE, FitMode.FIT_OVER)
    assert fitted_profile_size(iface, 0.5, 2.0, outer=False).width == 51.0
    assert fitted_profile_size(iface, 0.5, 2.0, outer=True).width == 55.0
    iface.fit_mode = FitMode.FIT_INSIDE
    assert fitted_profile_size(iface, 0.5, 2.0, outer=True).width == 49.0
    assert fitted_profile_size(iface, 0.5, 2.0, outer=False).width == 45.0


def test_invalid_fit_inside_geometry_blocks_generation() -> None:
    project = project_for_modes(FitMode.FIT_INSIDE, FitMode.FIT_OVER)
    project.interface_a.dimensions = [
        Dimension(
            id="outer_diameter",
            label="Outer Diameter",
            value=4.0,
            provenance=DimensionProvenance.USER_ENTERED,
        ),
        Dimension(
            id="overall_width",
            label="Overall Width",
            value=4.0,
            provenance=DimensionProvenance.USER_ENTERED,
        ),
    ]
    project.manufacturing.wall_thickness_mm = 2.0
    project.manufacturing.clearance_a_mm = 0.5
    validation = validate_connection_and_manufacturing(
        project.interface_a, project.interface_b, project.connection, project.manufacturing
    )
    assert validation.is_valid is False
    assert any(issue.id == "IF-MFG-004" for issue in validation.blocking_errors)


def test_primitive_promotion_requires_confirmation_before_approval() -> None:
    service = ProjectService()
    project = service.create_project()
    project.interface_a.profile_type = ProfileType.ROUNDED_RECTANGLE
    project.interface_a.traced_outer_contour = TracedContour(
        id="outer_contour",
        points=rounded_rect_points(),
        classification="outer_contour",
        provenance="analysis",
    )
    project.interface_a.scale_calibration = ScaleCalibration(
        confirmed=True,
        pixel_distance=120.0,
        real_distance_mm=60.0,
        scale_factor=0.5,
    )
    project.interface_a.dimensions = [
        Dimension(
            id="width", label="Width", value=60.0, provenance=DimensionProvenance.USER_ENTERED
        ),
        Dimension(
            id="height", label="Height", value=40.0, provenance=DimensionProvenance.USER_ENTERED
        ),
        Dimension(
            id="corner_radius",
            label="Corner Radius",
            value=7.0,
            provenance=DimensionProvenance.USER_ENTERED,
            critical=False,
        ),
    ]
    project.interface_a.primitive_fallback_active = True
    project.interface_a.primitive_promotion_confirmed = False
    service.repository.save(project)

    with pytest.raises(
        InvalidInterfaceApprovalError, match="primitive promotion must be confirmed"
    ):
        service.approve_interface(project.project_id, "interface_a", project.project_token)

    from app.models.schema import InterfacePatchRequest

    updated = service.patch_interface(
        project.project_id,
        "interface_a",
        InterfacePatchRequest(primitive_promotion_confirmed=True),
        project.project_token,
    )
    assert updated.interface_a.primitive_promotion_confirmed is True

    approved = service.approve_interface(project.project_id, "interface_a", project.project_token)
    assert approved.interface_a.approved is True


def test_inferred_rounded_rectangle_radius_blocks_approval_until_user_confirmed() -> None:
    service = ProjectService()
    project = service.create_project()
    project.interface_a.profile_type = ProfileType.ROUNDED_RECTANGLE
    project.interface_a.scale_calibration = ScaleCalibration(
        confirmed=True, pixel_distance=100.0, real_distance_mm=50.0
    )
    project.interface_a.primitive_fallback_active = True
    project.interface_a.primitive_promotion_confirmed = True
    project.interface_a.dimensions = [
        Dimension(
            id="width", label="Width", value=60.0, provenance=DimensionProvenance.USER_ENTERED
        ),
        Dimension(
            id="height", label="Height", value=40.0, provenance=DimensionProvenance.USER_ENTERED
        ),
        Dimension(
            id="corner_radius",
            label="Corner Radius",
            value=4.8,
            provenance=DimensionProvenance.SYSTEM_INFERRED,
            confidence=0.45,
            critical=False,
            consistency_state="requires_confirmation",
        ),
    ]
    service.repository.save(project)

    with pytest.raises(InvalidInterfaceApprovalError, match="corner radius must be confirmed"):
        service.approve_interface(project.project_id, "interface_a", project.project_token)

    from app.models.schema import InterfacePatchRequest

    confirmed_dims = list(project.interface_a.dimensions)
    confirmed_dims[2] = confirmed_dims[2].model_copy(
        update={
            "provenance": DimensionProvenance.USER_ENTERED,
            "confidence": 1.0,
            "consistency_state": "valid",
        }
    )
    service.patch_interface(
        project.project_id,
        "interface_a",
        InterfacePatchRequest(
            dimensions=confirmed_dims,
            scale_calibration=ScaleCalibration(
                confirmed=True,
                pixel_distance=100.0,
                real_distance_mm=50.0,
                scale_factor=0.5,
            ),
        ),
        project.project_token,
    )
    approved = service.approve_interface(project.project_id, "interface_a", project.project_token)
    assert approved.interface_a.approved is True
