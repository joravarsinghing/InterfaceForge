"""Two-point trace scale calibration regression tests."""

from fastapi.testclient import TestClient


def create_project(client: TestClient) -> tuple[str, str, dict[str, str]]:
    data = client.post("/api/projects").json()["data"]
    return data["project_id"], data["project_token"], {"X-Project-Token": data["project_token"]}


def traced_payload(confirmed: bool = False) -> dict:
    return {
        "profile_type": "traced_closed",
        "traced_outer_contour": {
            "id": "outer_contour",
            "points": [
                {"x": 0, "y": 0},
                {"x": 100, "y": 0},
                {"x": 100, "y": 50},
                {"x": 0, "y": 50},
            ],
            "is_closed": True,
            "classification": "outer_contour",
            "provenance": "analysis",
            "confidence": 1.0,
        },
        "traced_hole_contours": [],
        "dimensions": [
            {
                "id": "overall_width",
                "label": "Overall Width",
                "value": 100,
                "unit": "mm",
                "provenance": "system_inferred",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
            {
                "id": "overall_height",
                "label": "Overall Height",
                "value": 50,
                "unit": "mm",
                "provenance": "system_inferred",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
        ],
        "scale_calibration": {
            "source": "user_calibration",
            "method": "two_point_trace",
            "reference_dimension": "two_point_distance",
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "pixel_distance": 100,
            "real_distance_mm": 40,
            "scale_factor": 0.4,
            "confidence": 1.0,
            "confirmed": confirmed,
        },
    }


def setup_traced(client: TestClient) -> tuple[str, dict[str, str]]:
    pid, _token, headers = create_project(client)
    res = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json=traced_payload(False),
        headers=headers,
    )
    assert res.status_code == 200
    return pid, headers



def confirm_supported_rectangle_promotion(
    client: TestClient, pid: str, headers: dict[str, str]
) -> None:
    res = client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={
            "primitive_fallback_active": True,
            "primitive_promotion_confirmed": True,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.json()

def test_snap_projects_click_to_nearest_trace_segment(client: TestClient) -> None:
    pid, headers = setup_traced(client)
    res = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/snap",
        json={"point": {"x": 42, "y": 8}},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["point"] == {"x": 42.0, "y": 0.0}
    assert data["distance_px"] == 8.0
    assert data["feature_id"] == "outer_contour"


def test_two_point_calibration_persists_and_hydrates_confirmed_scale(client: TestClient) -> None:
    pid, headers = setup_traced(client)
    res = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 50, "y": 7},
            "point_b": {"x": 90, "y": 6},
            "real_distance_mm": 45,
            "confirmed": True,
        },
        headers=headers,
    )
    assert res.status_code == 200
    iface = res.json()["data"]["interface_a"]
    scale = iface["scale_calibration"]
    assert scale["confirmed"] is True
    assert scale["method"] == "two_point_trace"
    assert scale["point_a"] == {"x": 50.0, "y": 0.0}
    assert scale["point_b"] == {"x": 90.0, "y": 0.0}
    assert scale["pixel_distance"] == 40.0
    assert scale["scale_factor"] == 1.125
    dims = {d["id"]: d for d in iface["dimensions"]}
    assert dims["overall_width"]["value"] == 112.5
    assert dims["overall_height"]["value"] == 56.25

    reloaded = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert reloaded["interface_a"]["scale_calibration"] == scale


def test_unconfirmed_calibration_blocks_approval_then_confirmed_allows_it(
    client: TestClient,
) -> None:
    pid, headers = setup_traced(client)
    draft = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 40,
            "confirmed": False,
        },
        headers=headers,
    )
    assert draft.status_code == 200
    blocked = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert blocked.status_code == 400
    assert "Scale calibration must be confirmed" in blocked.json()["error"]["message"]

    confirmed = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 40,
            "confirmed": True,
        },
        headers=headers,
    )
    assert confirmed.status_code == 200
    confirm_supported_rectangle_promotion(client, pid, headers)
    approved = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approved.status_code == 200


def test_invalid_inputs_reject_without_overwriting_last_confirmed_calibration(
    client: TestClient,
) -> None:
    pid, headers = setup_traced(client)
    good = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 40,
            "confirmed": True,
        },
        headers=headers,
    )
    assert good.status_code == 200
    before = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]

    identical = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 10, "y": 0},
            "point_b": {"x": 10.2, "y": 0},
            "real_distance_mm": 40,
            "confirmed": True,
        },
        headers=headers,
    )
    assert identical.status_code == 400
    invalid_distance = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 0,
            "confirmed": True,
        },
        headers=headers,
    )
    assert invalid_distance.status_code == 400
    out_of_bounds = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/snap",
        json={"point": {"x": 999, "y": 999}},
        headers=headers,
    )
    assert out_of_bounds.status_code == 400

    after = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert after["interface_a"]["scale_calibration"] == before["interface_a"]["scale_calibration"]


def test_reselection_and_real_distance_edit_invalidate_existing_approval(
    client: TestClient,
) -> None:
    pid, headers = setup_traced(client)
    client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 40,
            "confirmed": True,
        },
        headers=headers,
    )
    confirm_supported_rectangle_promotion(client, pid, headers)
    assert (
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers
        ).status_code
        == 200
    )
    changed = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 50, "y": 50},
            "real_distance_mm": 70,
            "confirmed": False,
        },
        headers=headers,
    )
    assert changed.status_code == 200
    data = changed.json()["data"]
    assert data["interface_a"]["approved"] is False
    assert data["interface_a"]["scale_calibration"]["confirmed"] is False


def test_legacy_unmapped_dimensions_do_not_block_or_drive_approval(client: TestClient) -> None:
    pid, headers = setup_traced(client)
    client.patch(
        f"/api/projects/{pid}/interfaces/interface_a",
        json={
            **traced_payload(False),
            "dimensions": [
                *traced_payload(False)["dimensions"],
                {
                    "id": "custom_dim_1",
                    "label": "Custom Dimension 1",
                    "value": 0,
                    "unit": "mm",
                    "provenance": "unresolved",
                    "confidence": 1.0,
                    "critical": True,
                    "feature_ref": None,
                    "consistency_state": "unmapped",
                },
            ],
        },
        headers=headers,
    )
    confirmed = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": 0, "y": 0},
            "point_b": {"x": 100, "y": 0},
            "real_distance_mm": 40,
            "confirmed": True,
        },
        headers=headers,
    )
    assert confirmed.status_code == 200
    confirm_supported_rectangle_promotion(client, pid, headers)
    approved = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approved.status_code == 200, approved.json()
    dims = {d["id"]: d for d in approved.json()["data"]["interface_a"]["dimensions"]}
    assert dims["overall_width"]["value"] == 40.0
    assert dims["custom_dim_1"]["feature_ref"] is None


def primitive_payload(profile_type: str = "circle", interface_id: str = "interface_a") -> dict:
    if profile_type == "circle":
        dims = [
            {
                "id": "outer_diameter",
                "label": "Outer Diameter",
                "value": 50,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            }
        ]
        import math

        points = [
            {
                "x": round(25 * math.cos(2 * math.pi * i / 64), 4),
                "y": round(25 * math.sin(2 * math.pi * i / 64), 4),
            }
            for i in range(64)
        ]
    elif profile_type == "rounded_rectangle":
        dims = [
            {
                "id": "width",
                "label": "Width",
                "value": 80,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
            {
                "id": "height",
                "label": "Height",
                "value": 50,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
            {
                "id": "corner_radius",
                "label": "Corner Radius",
                "value": 5,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": False,
                "feature_ref": "outer_contour",
            },
        ]
        points = [
            {"x": -35, "y": -25},
            {"x": 35, "y": -25},
            {"x": 40, "y": -20},
            {"x": 40, "y": 20},
            {"x": 35, "y": 25},
            {"x": -35, "y": 25},
            {"x": -40, "y": 20},
            {"x": -40, "y": -20},
        ]
    else:
        dims = [
            {
                "id": "width",
                "label": "Width",
                "value": 60,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
            {
                "id": "height",
                "label": "Height",
                "value": 40,
                "unit": "mm",
                "provenance": "image_extracted",
                "confidence": 1.0,
                "critical": True,
                "feature_ref": "outer_contour",
            },
        ]
        points = [
            {"x": -30, "y": -20},
            {"x": 30, "y": -20},
            {"x": 30, "y": 20},
            {"x": -30, "y": 20},
        ]
    return {
        "profile_type": profile_type,
        "profile_points": points,
        "traced_outer_contour": {
            "id": "outer_contour",
            "points": points,
            "is_closed": True,
            "classification": "outer_contour",
            "provenance": "opencv_primitive",
            "confidence": 1.0,
        },
        "traced_hole_contours": [],
        "dimensions": dims,
        "scale_calibration": {
            "source": "user_calibration",
            "method": "two_point_trace",
            "reference_dimension": "two_point_distance",
            "pixel_distance": 0,
            "real_distance_mm": 40,
            "scale_factor": 0,
            "confidence": 1.0,
            "confirmed": False,
        },
    }


def setup_primitive(
    client: TestClient, profile_type: str, interface_id: str = "interface_a"
) -> tuple[str, dict[str, str]]:
    pid, _token, headers = create_project(client)
    if interface_id == "interface_b":
        client.patch(
            f"/api/projects/{pid}/interfaces/interface_a",
            json=primitive_payload("circle"),
            headers=headers,
        )
        client.post(
            f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
            json={
                "point_a": {"x": -25, "y": 0},
                "point_b": {"x": 25, "y": 0},
                "real_distance_mm": 50,
                "confirmed": True,
            },
            headers=headers,
        )
        client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    res = client.patch(
        f"/api/projects/{pid}/interfaces/{interface_id}",
        json=primitive_payload(profile_type, interface_id),
        headers=headers,
    )
    assert res.status_code == 200, res.json()
    return pid, headers


def test_primitive_snap_supports_circle_rectangle_and_rounded_rectangle(client: TestClient) -> None:
    cases = [
        ("circle", {"x": 24, "y": 3}),
        ("rectangle", {"x": 10, "y": 18}),
        ("rounded_rectangle", {"x": 0, "y": 24}),
    ]
    for profile_type, click in cases:
        pid, headers = setup_primitive(client, profile_type)
        res = client.post(
            f"/api/projects/{pid}/interfaces/interface_a/scale/snap",
            json={"point": click},
            headers=headers,
        )
        assert res.status_code == 200, res.json()
        data = res.json()["data"]
        snapped = data["point"]
        assert data["feature_id"] == "outer_contour"
        assert data["distance_px"] <= 3.1
        assert abs(snapped["x"] - click["x"]) <= 3.1
        assert abs(snapped["y"] - click["y"]) <= 3.1


def test_primitive_two_point_calibration_derives_dimensions_and_hydrates(
    client: TestClient,
) -> None:
    pid, headers = setup_primitive(client, "rectangle")
    res = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/calibrate",
        json={
            "point_a": {"x": -30, "y": 20},
            "point_b": {"x": 30, "y": 20},
            "real_distance_mm": 120,
            "confirmed": True,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.json()
    iface = res.json()["data"]["interface_a"]
    assert iface["scale_calibration"]["point_a"] == {"x": -30.0, "y": 20.0}
    assert iface["scale_calibration"]["point_b"] == {"x": 30.0, "y": 20.0}
    dims = {d["id"]: d for d in iface["dimensions"]}
    assert dims["width"]["value"] == 120.0
    assert dims["height"]["value"] == 80.0
    reloaded = client.get(f"/api/projects/{pid}", headers=headers).json()["data"]
    assert reloaded["interface_a"]["scale_calibration"] == iface["scale_calibration"]


def test_primitive_snap_rejects_click_far_from_boundary(client: TestClient) -> None:
    pid, headers = setup_primitive(client, "circle")
    res = client.post(
        f"/api/projects/{pid}/interfaces/interface_a/scale/snap",
        json={"point": {"x": 0, "y": 0}},
        headers=headers,
    )
    assert res.status_code == 400
    assert "too far from the visible profile boundary" in res.json()["error"]["message"]


def test_primitive_calibration_supports_interface_b(client: TestClient) -> None:
    pid, headers = setup_primitive(client, "rectangle", interface_id="interface_b")
    res = client.post(
        f"/api/projects/{pid}/interfaces/interface_b/scale/snap",
        json={"point": {"x": 0, "y": -18}},
        headers=headers,
    )
    assert res.status_code == 200, res.json()
    assert res.json()["data"]["point"] == {"x": 0.0, "y": -20.0}
