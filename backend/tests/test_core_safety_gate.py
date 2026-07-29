"""Compressed Core Safety Gate regression tests."""

import io
import math

from fastapi.testclient import TestClient
from PIL import Image

from app.models.schema import (
    Dimension,
    DimensionProvenance,
    Interface,
    ModelFailRequest,
    Point2D,
    ProfileType,
    ScaleCalibration,
    TracedContour,
)
from app.services.analysis_provider import AnalysisProvider
from app.services.profile_validation import validate_interface_profile


class RejectingProvider(AnalysisProvider):
    def analyze(self, image_bytes: bytes, filename: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("analysis failed after prior valid state")


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (96, 96), color=(220, 220, 220)).save(buf, format="PNG")
    return buf.getvalue()


def traced_interface(
    *, confirmed: bool = True, points: list[Point2D] | None = None, is_closed: bool = True
) -> dict:
    pts = points or [
        Point2D(x=-20, y=-20),
        Point2D(x=20, y=-20),
        Point2D(x=20, y=20),
        Point2D(x=-20, y=20),
    ]
    return {
        "source_image_ref": "artifacts/uploads/previous.png",
        "profile_type": "traced_closed",
        "traced_outer_contour": {
            "id": "outer_contour",
            "points": [p.model_dump() for p in pts],
            "is_closed": is_closed,
            "classification": "outer_contour",
            "provenance": "user_edited",
            "confidence": 1.0,
        },
        "dimensions": [
            {
                "id": "overall_width",
                "label": "Overall Width",
                "value": 40.0,
                "unit": "mm",
                "provenance": "user_entered",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
            {
                "id": "overall_height",
                "label": "Overall Height",
                "value": 40.0,
                "unit": "mm",
                "provenance": "user_entered",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
        ],
        "scale_calibration": {
            "source": "user_calibration",
            "reference_dimension": "overall_width",
            "pixel_distance": 96.0,
            "real_distance_mm": 40.0,
            "confidence": 1.0,
            "confirmed": confirmed,
        },
    }


def create_project(client: TestClient) -> tuple[str, str, dict[str, str]]:
    data = client.post("/api/projects").json()["data"]
    return data["project_id"], data["project_token"], {"X-Project-Token": data["project_token"]}


def upload_and_analyze_with_measurement(
    client: TestClient,
    pid: str,
    headers: dict[str, str],
    interface_id: str,
    measurement_type: str,
    value: float,
) -> dict:
    res = client.post(
        f"/api/projects/{pid}/interfaces/{interface_id}/upload",
        files={"file": (f"{interface_id}.png", png_bytes(), "image/png")},
        data={
            "known_measurement_type": measurement_type,
            "known_measurement_value": str(value),
            "known_measurement_unit": "mm",
        },
        headers=headers,
    )
    assert res.status_code == 201
    analysis = client.post(
        f"/api/projects/{pid}/interfaces/{interface_id}/analyze", headers=headers
    )
    assert analysis.status_code == 200
    return client.get(f"/api/projects/{pid}", headers=headers).json()["data"]


def confirm_scale(
    client: TestClient,
    pid: str,
    headers: dict[str, str],
    interface_id: str,
    measurement_type: str,
    value: float,
) -> dict:
    res = client.patch(
        f"/api/projects/{pid}/interfaces/{interface_id}",
        json={
            "scale_calibration": {
                "source": "user_calibration",
                "reference_dimension": measurement_type,
                "pixel_distance": 96.0,
                "real_distance_mm": value,
                "confidence": 1.0,
                "confirmed": True,
            }
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["data"]


def test_upload_measurement_persists_for_interface_a_and_b(client: TestClient) -> None:
    pid, _token, headers = create_project(client)

    project = upload_and_analyze_with_measurement(
        client, pid, headers, "interface_a", "overall_width", 41.5
    )
    scale_a = project["interface_a"]["scale_calibration"]
    assert scale_a["reference_dimension"] == "overall_width"
    assert scale_a["real_distance_mm"] == 41.5
    assert scale_a["confirmed"] is False
    assert any(
        d["id"] == "overall_width" and d["value"] == 41.5
        for d in project["interface_a"]["dimensions"]
    )

    confirm_scale(client, pid, headers, "interface_a", "overall_width", 41.5)
    assert (
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers
        ).status_code
        == 200
    )

    project = upload_and_analyze_with_measurement(
        client, pid, headers, "interface_b", "overall_height", 52.25
    )
    scale_b = project["interface_b"]["scale_calibration"]
    assert scale_b["reference_dimension"] == "overall_height"
    assert scale_b["real_distance_mm"] == 52.25
    assert scale_b["confirmed"] is False
    assert any(
        d["id"] == "overall_height" and d["value"] == 52.25
        for d in project["interface_b"]["dimensions"]
    )


def test_direct_approval_rejects_unconfirmed_scale_and_patch_bypass(client: TestClient) -> None:
    pid, _token, headers = create_project(client)
    upload_and_analyze_with_measurement(client, pid, headers, "interface_a", "overall_width", 40.0)

    approve = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approve.status_code == 400
    assert "Scale calibration must be confirmed" in approve.json()["error"]["message"]

    bypass = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"approved": True},
        headers=headers,
    )
    assert bypass.status_code == 400
    assert "approval endpoint" in bypass.json()["error"]["message"]


def test_confirmation_survives_refresh_and_invalidates_after_measurement_change(
    client: TestClient,
) -> None:
    pid, _token, headers = create_project(client)
    upload_and_analyze_with_measurement(client, pid, headers, "interface_a", "overall_width", 40.0)
    confirm_scale(client, pid, headers, "interface_a", "overall_width", 40.0)

    reloaded = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert reloaded["interface_a"]["scale_calibration"]["confirmed"] is True

    dims = reloaded["interface_a"]["dimensions"]
    dims[0]["value"] = dims[0]["value"] + 1.0
    changed = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"dimensions": dims},
        headers=headers,
    ).json()["data"]
    assert changed["interface_a"]["scale_calibration"]["confirmed"] is False


def test_open_self_intersecting_and_missing_profiles_reject_approval(client: TestClient) -> None:
    pid, _token, headers = create_project(client)

    missing = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"profile_type": "traced_closed"},
        headers=headers,
    )
    assert missing.status_code == 200
    assert (
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers
        ).status_code
        == 400
    )

    open_patch = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=traced_interface(is_closed=False),
        headers=headers,
    )
    assert open_patch.status_code == 200
    confirm_scale(client, pid, headers, "interface_a", "overall_width", 40.0)
    open_approve = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers
    )
    assert open_approve.status_code == 400
    assert "not marked as closed" in open_approve.json()["error"]["message"]

    bowtie = [
        Point2D(x=-20, y=-20),
        Point2D(x=20, y=20),
        Point2D(x=-20, y=20),
        Point2D(x=20, y=-20),
    ]
    client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=traced_interface(points=bowtie),
        headers=headers,
    )
    confirm_scale(client, pid, headers, "interface_a", "overall_width", 40.0)
    intersect = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert intersect.status_code == 400
    assert "intersects itself" in intersect.json()["error"]["message"]


def test_contour_point_limit_and_comparison_budget_are_bounded() -> None:
    too_many = [Point2D(x=float(i), y=0.0) for i in range(2001)]
    iface = Interface(
        id="interface_a",
        profile_type=ProfileType.TRACED_CLOSED,
        traced_outer_contour=TracedContour(points=too_many, is_closed=True),
    )
    valid, errors, _warnings = validate_interface_profile(iface)
    assert valid is False
    assert any("too dense" in e for e in errors)

    budget_pts = [
        Point2D(
            x=round(math.cos(2 * math.pi * i / 800), 6), y=round(math.sin(2 * math.pi * i / 800), 6)
        )
        for i in range(800)
    ]
    budget_iface = Interface(
        id="interface_a",
        profile_type=ProfileType.TRACED_CLOSED,
        traced_outer_contour=TracedContour(points=budget_pts, is_closed=True),
        dimensions=[
            Dimension(
                id="overall_width",
                label="Overall Width",
                value=2.0,
                provenance=DimensionProvenance.USER_ENTERED,
            ),
            Dimension(
                id="overall_height",
                label="Overall Height",
                value=2.0,
                provenance=DimensionProvenance.USER_ENTERED,
            ),
        ],
        scale_calibration=ScaleCalibration(
            source="user_calibration",
            reference_dimension="overall_width",
            pixel_distance=800,
            real_distance_mm=2.0,
            confirmed=True,
        ),
    )
    valid, errors, _warnings = validate_interface_profile(budget_iface)
    assert valid is False
    assert any("IF-PROFILE-COMPLEXITY-BUDGET" in e for e in errors)


def test_normal_clean_profile_still_approves(client: TestClient) -> None:
    pid, _token, headers = create_project(client)
    client.post(
        f"/api/projects/{pid}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes(), "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{pid}/interfaces/interface_a/analyze", headers=headers)
    approve = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approve.status_code == 200


def test_failed_reanalysis_and_invalid_update_preserve_previous_valid_state(
    client: TestClient,
) -> None:
    pid, _token, headers = create_project(client)
    valid = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=traced_interface(confirmed=True),
        headers=headers,
    )
    assert valid.status_code == 200
    confirm_scale(client, pid, headers, "interface_a", "overall_width", 40.0)
    promote = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"primitive_fallback_active": True, "primitive_promotion_confirmed": True},
        headers=headers,
    )
    assert promote.status_code == 200
    approve = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approve.status_code == 400
    assert "positive finite value" in approve.json()["error"]["message"]
    before = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    from app.services.project_service import ProjectService

    service = ProjectService()
    try:
        service.analyze_interface_image(
            pid,
            "interface_a",
            provider=RejectingProvider(),
            project_token=headers["X-Project-Token"],
        )
    except RuntimeError:
        pass
    after_failed_analysis = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert (
        after_failed_analysis["interface_a"]["traced_outer_contour"]
        == before["interface_a"]["traced_outer_contour"]
    )


def test_failed_generation_preserves_last_known_good_model(client: TestClient) -> None:
    pid, _token, headers = create_project(client)
    client.post(
        f"/api/projects/{pid}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes(), "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{pid}/interfaces/interface_a/analyze", headers=headers)
    assert (
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers
        ).status_code
        == 200
    )
    client.post(
        f"/api/projects/{pid}/interfaces/interface_b/upload",
        files={"file": ("rectangle.png", png_bytes(), "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{pid}/interfaces/interface_b/analyze", headers=headers)
    assert (
        client.post(
            f"/api/projects/{pid}/interfaces/interface_b/approve", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/projects/{pid}/connection",
            json={"mode": "coaxial", "length_mm": 80.0},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.post(f"/api/projects/{pid}/model/start", headers=headers).status_code == 200
    assert (
        client.post(
            f"/api/projects/{pid}/model/succeed", json={"model_revision": 1}, headers=headers
        ).status_code
        == 200
    )
    assert client.post(f"/api/projects/{pid}/model/start", headers=headers).status_code == 200
    failed = client.post(
        f"/api/projects/{pid}/model/fail",
        json=ModelFailRequest(
            model_revision=2, error_message="engine rejected update"
        ).model_dump(),
        headers=headers,
    ).json()["data"]
    assert failed["current_model_revision"] == 1
    assert failed["last_known_good_model_revision"] == 1
    assert failed["model_revisions"][0]["status"] == "current"
    assert failed["model_revisions"][1]["status"] == "failed"


def rounded_rectangle_trace_points() -> list[Point2D]:
    return [
        Point2D(x=10, y=0),
        Point2D(x=50, y=0),
        Point2D(x=90, y=0),
        Point2D(x=100, y=10),
        Point2D(x=100, y=30),
        Point2D(x=100, y=50),
        Point2D(x=90, y=60),
        Point2D(x=50, y=60),
        Point2D(x=10, y=60),
        Point2D(x=0, y=50),
        Point2D(x=0, y=30),
        Point2D(x=0, y=10),
    ]


def rounded_rectangle_trace_patch() -> dict:
    patch = traced_interface(points=rounded_rectangle_trace_points())
    patch.update(
        {
            "primitive_fallback_active": False,
            "primitive_promotion_confirmed": False,
            "primitive_detection_confidence": 0.9,
            "primitive_detection_reason": "corner_offsets_support_rounded_rectangle",
            "generation_unsupported": True,
            "generation_unsupported_reason": (
                "Adapter generation for arbitrary traced profiles is not yet enabled."
            ),
        }
    )
    return patch


def confirm_two_point_scale(
    client: TestClient, pid: str, headers: dict[str, str], interface_id: str
) -> dict:
    res = client.post(
        f"/api/projects/{pid}/interfaces/{interface_id}/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 30},
            "point_b": {"x": 100, "y": 30},
            "real_distance_mm": 50.0,
            "confirmed": True,
        },
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["data"]


def test_confirming_detected_rounded_rectangle_persists_supported_profile_and_scale(
    client: TestClient,
) -> None:
    pid, _token, headers = create_project(client)
    patched = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=rounded_rectangle_trace_patch(),
        headers=headers,
    )
    assert patched.status_code == 200

    calibrated = confirm_two_point_scale(client, pid, headers, "interface_a")
    assert calibrated["interface_a"]["profile_type"] == "traced_closed"
    assert calibrated["interface_a"]["scale_calibration"]["confirmed"] is True

    confirmed = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={
            "primitive_fallback_active": True,
            "primitive_promotion_confirmed": True,
        },
        headers=headers,
    )
    assert confirmed.status_code == 200
    iface = confirmed.json()["data"]["interface_a"]
    assert iface["profile_type"] == "rounded_rectangle"
    assert iface["primitive_promotion_confirmed"] is True
    assert iface["scale_calibration"]["confirmed"] is True
    assert iface["generation_unsupported"] is False
    assert {"width", "height", "corner_radius"}.issubset({d["id"] for d in iface["dimensions"]})

    refreshed = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert refreshed["interface_a"]["profile_type"] == "rounded_rectangle"
    assert refreshed["interface_a"]["scale_calibration"]["confirmed"] is True


def test_scale_update_does_not_revert_confirmed_detected_shape(client: TestClient) -> None:
    pid, _token, headers = create_project(client)
    client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=rounded_rectangle_trace_patch(),
        headers=headers,
    )
    confirm_two_point_scale(client, pid, headers, "interface_a")
    confirmed = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"primitive_fallback_active": True, "primitive_promotion_confirmed": True},
        headers=headers,
    ).json()["data"]
    assert confirmed["interface_a"]["profile_type"] == "rounded_rectangle"

    recalibrated = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 30},
            "point_b": {"x": 100, "y": 30},
            "real_distance_mm": 60.0,
            "confirmed": True,
        },
        headers=headers,
    ).json()["data"]
    assert recalibrated["interface_a"]["profile_type"] == "rounded_rectangle"
    assert recalibrated["interface_a"]["scale_calibration"]["confirmed"] is True


def test_approved_promoted_interface_reaches_step3_without_if_conn_008(
    client: TestClient,
) -> None:
    pid, _token, headers = create_project(client)
    client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=rounded_rectangle_trace_patch(),
        headers=headers,
    )
    confirm_two_point_scale(client, pid, headers, "interface_a")
    client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={"primitive_fallback_active": True, "primitive_promotion_confirmed": True},
        headers=headers,
    )
    approve_a = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approve_a.status_code == 200

    client.patch(
        f"/api/projects/{pid}/interfaces/interface_b",
        json={
            "profile_type": "circle",
            "dimensions": [
                {
                    "id": "outer_diameter",
                    "label": "Outer Diameter",
                    "value": 40.0,
                    "unit": "mm",
                    "provenance": "user_entered",
                    "confidence": 1.0,
                    "critical": True,
                    "feature_ref": "outer_contour",
                }
            ],
        },
        headers=headers,
    )
    approve_b = client.post(f"/api/projects/{pid}/interfaces/interface_b/approve", headers=headers)
    assert approve_b.status_code == 200

    validation = client.post(
        f"/api/projects/{pid}/validate-connection",
        json={
            "connection": {
                "mode": "coaxial",
                "length_mm": 60.0,
                "offset_x_mm": 0.0,
                "offset_y_mm": 0.0,
                "angle_deg": 0.0,
            },
            "manufacturing": {
                "process": "fdm",
                "material": "PETG",
                "wall_thickness_mm": 2.4,
                "clearance_a_mm": 0.3,
                "clearance_b_mm": 0.1,
            },
        },
        headers=headers,
    )
    assert validation.status_code == 200
    errors = validation.json()["data"]["blocking_errors"]
    assert all(err["id"] != "IF-CONN-008" for err in errors)
