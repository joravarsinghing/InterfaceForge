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


def test_unconfirmed_calibration_blocks_approval_then_confirmed_allows_it(client: TestClient) -> None:
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
    approved = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approved.status_code == 200


def test_invalid_inputs_reject_without_overwriting_last_confirmed_calibration(client: TestClient) -> None:
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


def test_reselection_and_real_distance_edit_invalidate_existing_approval(client: TestClient) -> None:
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
    assert client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers).status_code == 200
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
    approved = client.post(f"/api/projects/{pid}/interfaces/interface_a/approve", headers=headers)
    assert approved.status_code == 200, approved.json()
    dims = {d["id"]: d for d in approved.json()["data"]["interface_a"]["dimensions"]}
    assert dims["overall_width"]["value"] == 40.0
    assert dims["custom_dim_1"]["feature_ref"] is None
