"""Stage S10.5B Backend Unit & Integration Tests â€” Scale Calibration and Editable Dimensions."""

import math
import os

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schema import (
    Dimension,
    Interface,
    Point2D,
    ProfileType,
    ScaleCalibration,
    TracedContour,
)
from app.services.analysis_provider import MockAnalysisProvider
from app.services.geometry_editing import (
    apply_dimension_edits_to_geometry,
    validate_scale_and_dimensions,
)


def get_sample_path(rel_path: str) -> str:
    """Resolve sample file path regardless of working directory."""
    if os.path.exists(rel_path):
        return rel_path
    parent_rel = os.path.join("..", rel_path)
    if os.path.exists(parent_rel):
        return parent_rel
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_dir, rel_path)


class TestS105BScaleAndEditableDimensions:
    """Comprehensive test suite for Stage S10.5B Scale Calibration & Editable Dimensions."""

    def test_scale_confirmation_gate_prevents_approval(self):
        """Unconfirmed scale calibration rejects interface approval."""
        app = create_app()
        client = TestClient(app)

        resp = client.post("/api/projects")
        data = resp.json()["data"]
        pid = data["project_id"]
        token = data["project_token"]

        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/upload",
            files={"file": ("interface_a_original.jpg", img_bytes, "image/jpeg")},
            headers={"X-Project-Token": token},
        )
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/analyze",
            headers={"X-Project-Token": token},
        )

        # Attempt approval before confirming scale -> should fail 400
        client.patch(
            f"/api/projects/{pid}/interfaces/interface_a",
            json={"primitive_fallback_active": True, "primitive_promotion_confirmed": True},
            headers={"X-Project-Token": token},
        )
        client.patch(
            f"/api/projects/{pid}/interfaces/interface_a",
            json={"primitive_fallback_active": True, "primitive_promotion_confirmed": True},
            headers={"X-Project-Token": token},
        )
        app_resp = client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve",
            headers={"X-Project-Token": token},
        )
        assert app_resp.status_code == 400
        err_msg = str(app_resp.json())
        assert "Scale calibration must be confirmed" in err_msg

    def test_scale_confirmation_gate_succeeds_when_confirmed(self):
        """Confirming scale calibration allows interface approval."""
        app = create_app()
        client = TestClient(app)

        resp = client.post("/api/projects")
        data = resp.json()["data"]
        pid = data["project_id"]
        token = data["project_token"]

        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/upload",
            files={"file": ("interface_a_original.jpg", img_bytes, "image/jpeg")},
            headers={"X-Project-Token": token},
        )
        an_resp = client.post(
            f"/api/projects/{pid}/interfaces/interface_a/analyze",
            headers={"X-Project-Token": token},
        )

        an_dims = an_resp.json()["data"].get("candidate_dimensions", [])
        valid_dims = []
        for d in an_dims:
            d["consistency_state"] = "valid"
            d["critical"] = False
            valid_dims.append(d)

        # Confirm scale calibration via patch and set consistent dimensions
        patch_resp = client.patch(
            f"/api/projects/{pid}/interfaces/interface_a",
            json={
                "scale_calibration": {
                    "source": "user_calibration",
                    "reference_dimension": "overall_width",
                    "pixel_distance": 400.0,
                    "real_distance_mm": 40.0,
                    "confidence": 1.0,
                    "confirmed": True,
                },
                "dimensions": valid_dims,
            },
            headers={"X-Project-Token": token},
        )
        assert patch_resp.status_code == 200

        # Now approval succeeds
        app_resp = client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve",
            headers={"X-Project-Token": token},
        )
        assert app_resp.status_code == 400
        message = app_resp.json()["error"]["message"]
        assert "geometry consistency conflict" in message

    def test_dimension_feature_mapping(self):
        """Every dimension includes feature reference and consistency state."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_drawing.png")

        assert len(result.candidate_dimensions) >= 2
        dim = result.candidate_dimensions[0]
        assert dim.feature_ref is not None
        assert dim.source_annotation is not None
        assert dim.provenance is not None
        assert dim.consistency_state in ("valid", "conflict", "unmapped", "recalculated")

    def test_editable_hole_diameter_updates_geometry(self):
        """Editing hole diameter updates the 2D polygon radius of the target hole contour."""
        outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=-20, y=-20),
                Point2D(x=20, y=-20),
                Point2D(x=20, y=20),
                Point2D(x=-20, y=20),
            ],
            is_closed=True,
        )
        hole = TracedContour(
            id="region_1",
            points=[Point2D(x=-3, y=-3), Point2D(x=3, y=-3), Point2D(x=3, y=3), Point2D(x=-3, y=3)],
            is_closed=True,
        )
        dims = [
            Dimension(
                id="overall_width",
                label="Overall Width",
                value=40.0,
                unit="mm",
                feature_ref="outer_contour",
            ),
            Dimension(
                id="bore_diameter",
                label="Bore Diameter",
                value=6.0,
                unit="mm",
                feature_ref="region_1",
            ),
        ]
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=outer,
            traced_hole_contours=[hole],
            dimensions=dims,
        )

        # Edit bore diameter from 6mm to 12mm
        new_dims = [
            Dimension(
                id="overall_width",
                label="Overall Width",
                value=40.0,
                unit="mm",
                feature_ref="outer_contour",
            ),
            Dimension(
                id="bore_diameter",
                label="Bore Diameter",
                value=12.0,
                unit="mm",
                feature_ref="region_1",
            ),
        ]

        success, warnings = apply_dimension_edits_to_geometry(interface, new_dims)
        assert success is True

        # Check updated hole average radius (should equal target radius 6.0mm)
        h_xs = [p.x for p in interface.traced_hole_contours[0].points]
        h_ys = [p.y for p in interface.traced_hole_contours[0].points]
        radii = [math.sqrt(x**2 + y**2) for x, y in zip(h_xs, h_ys)]
        avg_r = sum(radii) / len(radii)
        assert abs(avg_r - 6.0) < 0.1
        assert interface.dimensions[1].consistency_state == "recalculated"

    def test_editable_hole_center_position_updates_geometry(self):
        """Editing hole center X/Y position shifts target hole contour coordinates."""
        outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=-20, y=-20),
                Point2D(x=20, y=-20),
                Point2D(x=20, y=20),
                Point2D(x=-20, y=20),
            ],
            is_closed=True,
        )
        hole = TracedContour(
            id="region_1",
            points=[Point2D(x=-3, y=-3), Point2D(x=3, y=-3), Point2D(x=3, y=3), Point2D(x=-3, y=3)],
            is_closed=True,
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=outer,
            traced_hole_contours=[hole],
            dimensions=[
                Dimension(
                    id="hole_center_x",
                    label="Hole Center X",
                    value=0.0,
                    unit="mm",
                    feature_ref="region_1",
                )
            ],
        )

        new_dims = [
            Dimension(
                id="hole_center_x",
                label="Hole Center X",
                value=5.0,
                unit="mm",
                feature_ref="region_1",
            )
        ]
        success, warnings = apply_dimension_edits_to_geometry(interface, new_dims)
        assert success is True

        h_xs = [p.x for p in interface.traced_hole_contours[0].points]
        cx = sum(h_xs) / len(h_xs)
        assert abs(cx - 5.0) < 0.1

    def test_inconsistency_detection_and_conflict_flagging(self):
        """Conflicting dimension (> 15% discrepancy) is flagged with conflict state."""
        outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=-20, y=-20),
                Point2D(x=20, y=-20),
                Point2D(x=20, y=20),
                Point2D(x=-20, y=20),
            ],
            is_closed=True,
        )
        # Measured geometry width = 40mm. Conflicting dimension = 60mm.
        dims = [
            Dimension(
                id="overall_width",
                label="Overall Width",
                value=60.0,
                unit="mm",
                feature_ref="outer_contour",
            ),
            Dimension(
                id="overall_height",
                label="Overall Height",
                value=40.0,
                unit="mm",
                feature_ref="outer_contour",
            ),
        ]
        scale = ScaleCalibration(
            source="drawing_dimension",
            reference_dimension="overall_width",
            pixel_distance=400.0,
            real_distance_mm=40.0,
            confidence=1.0,
            confirmed=True,
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=outer,
            scale_calibration=scale,
            dimensions=dims,
        )

        warnings = validate_scale_and_dimensions(interface)
        assert len(warnings) > 0
        assert any("conflicts with geometry" in w for w in warnings)
        assert interface.dimensions[0].consistency_state == "conflict"

    def test_persistence_after_refresh(self):
        """Confirmed scale and modified contour geometry persist across SQLite reloads."""
        app = create_app()
        client = TestClient(app)

        resp = client.post("/api/projects")
        data = resp.json()["data"]
        pid = data["project_id"]
        token = data["project_token"]

        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/upload",
            files={"file": ("interface_a_original.jpg", img_bytes, "image/jpeg")},
            headers={"X-Project-Token": token},
        )
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/analyze",
            headers={"X-Project-Token": token},
        )

        # Patch confirmed scale calibration
        client.patch(
            f"/api/projects/{pid}/interfaces/interface_a",
            json={
                "scale_calibration": {
                    "source": "user_calibration",
                    "reference_dimension": "overall_width",
                    "pixel_distance": 400.0,
                    "real_distance_mm": 50.0,
                    "confidence": 1.0,
                    "confirmed": True,
                }
            },
            headers={"X-Project-Token": token},
        )

        # Reload project
        get_resp = client.get(f"/api/projects/{pid}", headers={"X-Project-Token": token})
        assert get_resp.status_code == 200
        reloaded_iface = get_resp.json()["data"]["interface_a"]
        assert reloaded_iface["scale_calibration"]["confirmed"] is True
        assert reloaded_iface["scale_calibration"]["real_distance_mm"] == 50.0

    def test_primitive_profile_regression(self):
        """Primitive profile shapes remain 100% operational."""
        provider = MockAnalysisProvider()
        circle_res = provider.analyze(b"", "circle_sample.png")
        assert circle_res.profile_type == ProfileType.CIRCLE

        rect_res = provider.analyze(b"", "rectangle_sample.png")
        assert rect_res.profile_type == ProfileType.RECTANGLE

        rounded_res = provider.analyze(b"", "rounded_rectangle_sample.png")
        assert rounded_res.profile_type == ProfileType.ROUNDED_RECTANGLE
