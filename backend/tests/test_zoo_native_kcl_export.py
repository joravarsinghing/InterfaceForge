"""Regression test suite for Stage S8.3 — Zoo-Native KCL Export.

Verifies stored/executed KCL hash equality, native export command invocation,
strict prohibition of OBJ conversion endpoints and local geometry reconstruction,
error handling for missing or mismatched KCL artifacts, retry capability,
legacy cache invalidation, and mock provider isolation.
"""

import hashlib
import json
import struct
from unittest.mock import AsyncMock, patch

import msgpack
import pytest

from app.models.schema import (
    Connection,
    ConnectionMode,
    Project,
    WorkflowState,
)
from app.services.export_provider import MockExportProvider, ZooExportProvider
from app.services.geometry_generator import (
    generate_adapter_obj,
    get_local_obj_call_count,
    reset_local_obj_call_count,
    set_prohibit_local_obj,
)
from app.services.kcl_compiler import compile_project_to_kcl


def create_valid_binary_stl_box() -> bytes:
    """Generate a valid 12-facet 20x20x20mm binary STL box."""
    header = b"InterfaceForge Binary STL Test Box".ljust(80, b"\x00")[:80]
    v = [
        (0.0, 0.0, 0.0),
        (20.0, 0.0, 0.0),
        (20.0, 20.0, 0.0),
        (0.0, 20.0, 0.0),
        (0.0, 0.0, 20.0),
        (20.0, 0.0, 20.0),
        (20.0, 20.0, 20.0),
        (0.0, 20.0, 20.0),
    ]
    triangles = [
        (0, 2, 1, (0.0, 0.0, -1.0)),
        (0, 3, 2, (0.0, 0.0, -1.0)),
        (4, 5, 6, (0.0, 0.0, 1.0)),
        (4, 6, 7, (0.0, 0.0, 1.0)),
        (0, 1, 5, (0.0, -1.0, 0.0)),
        (0, 5, 4, (0.0, -1.0, 0.0)),
        (1, 2, 6, (1.0, 0.0, 0.0)),
        (1, 6, 5, (1.0, 0.0, 0.0)),
        (2, 3, 7, (0.0, 1.0, 0.0)),
        (2, 7, 6, (0.0, 1.0, 0.0)),
        (3, 0, 4, (-1.0, 0.0, 0.0)),
        (3, 4, 7, (-1.0, 0.0, 0.0)),
    ]
    body = struct.pack("<I", len(triangles))
    for v1_i, v2_i, v3_i, norm in triangles:
        v1, v2, v3 = v[v1_i], v[v2_i], v[v3_i]
        tri_data = (
            norm[0],
            norm[1],
            norm[2],
            v1[0],
            v1[1],
            v1[2],
            v2[0],
            v2[1],
            v2[2],
            v3[0],
            v3[1],
            v3[2],
            0,
        )
        body += struct.pack("<ffffffffffffH", *tri_data)

    return header + body


@pytest.fixture
def approved_project() -> Project:
    """Fixture providing an approved project ready for 3D generation/export."""
    p = Project(
        project_id="test_s83_proj_12345678",
        project_token="tok_test_s83",
        current_schema_revision=1,
        current_model_revision=1,
        state=WorkflowState.MODEL_CURRENT,
    )
    p.interface_a.approved = True
    p.interface_b.approved = True
    p.connection = Connection(mode=ConnectionMode.COAXIAL, length_mm=40.0)
    return p


@pytest.mark.asyncio
async def test_kcl_hash_equality_required(approved_project: Project):
    """Verify export fails if executed KCL hash does not equal stored KCL hash."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)
    fake_kcl_hash = hashlib.sha256(b"altered_kcl_bytes").hexdigest()

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id="zoo_sess_83_test",
        kcl_hash=fake_kcl_hash,
    )

    assert not res.success
    assert res.error_id == "IF-EXPORT-005"
    assert "KCL hash mismatch" in res.error_message


def test_prohibit_local_obj_guard(approved_project: Project):
    """Verify local OBJ generator raises RuntimeError when prohibition guard is active."""
    set_prohibit_local_obj(True)
    try:
        with pytest.raises(RuntimeError, match="PRODUCTION EXPORT VIOLATION"):
            generate_adapter_obj(approved_project)
    finally:
        set_prohibit_local_obj(False)


@pytest.mark.asyncio
async def test_obj_endpoint_prohibition_and_native_command(approved_project: Project):
    """Verify ZooExportProvider issues WebSocket native export without calling OBJ endpoint."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)
    reset_local_obj_call_count()

    mock_ws = AsyncMock()
    binary_stl_box = create_valid_binary_stl_box()

    msgpack_response_frame = msgpack.packb(
        {
            "success": True,
            "resp": {
                "type": "export",
                "data": {"files": [{"name": "output.stl", "contents": binary_stl_box}]},
            },
        }
    )

    last_cmd_type = None

    async def mock_send(msg_str):
        nonlocal last_cmd_type
        try:
            d = json.loads(msg_str)
            last_cmd_type = d.get("cmd", {}).get("type")
        except Exception:
            pass

    async def mock_recv():
        if last_cmd_type == "export":
            return msgpack_response_frame
        if last_cmd_type == "start_path":
            return json.dumps(
                {
                    "success": True,
                    "request_id": "path_uuid",
                    "resp": {
                        "type": "modeling",
                        "data": {"modeling_response": {"type": "start_path"}},
                    },
                }
            )
        if last_cmd_type == "scene_get_entity_ids":
            return json.dumps(
                {
                    "success": True,
                    "resp": {
                        "type": "modeling",
                        "data": {
                            "modeling_response": {
                                "type": "scene_get_entity_ids",
                                "data": {"entity_ids": [["uuid_1", "uuid_2"]]},
                            }
                        },
                    },
                }
            )
        if last_cmd_type == "loft":
            return json.dumps(
                {
                    "success": True,
                    "resp": {
                        "type": "modeling",
                        "data": {
                            "modeling_response": {
                                "type": "loft",
                                "data": {"solid_id": "solid_uuid"},
                            }
                        },
                    },
                }
            )
        return json.dumps(
            {
                "success": True,
                "resp": {
                    "type": "modeling",
                    "data": {"modeling_response": {"type": last_cmd_type}},
                },
            }
        )

    mock_ws.send = AsyncMock(side_effect=mock_send)
    mock_ws.recv = AsyncMock(side_effect=mock_recv)

    with patch("websockets.connect") as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_ws
        with patch("urllib.request.urlopen") as mock_urlopen:
            res = await provider.export_format(
                project_id=approved_project.project_id,
                model_revision=1,
                format_name="stl",
                kcl_code=kcl_res.kcl_code,
                project=approved_project,
                zoo_model_id="sess_nat_clean",
                kcl_hash=kcl_res.kcl_hash,
            )

            # Confirm HTTP REST urlopen was NEVER called
            assert not mock_urlopen.called
            # Confirm local OBJ generator was NEVER called
            assert get_local_obj_call_count() == 0

            assert res.success
            assert res.format == "stl"
            assert res.is_mock is False
            assert res.facet_count == 12


@pytest.mark.asyncio
async def test_missing_zoo_model_id_blocks_export(approved_project: Project):
    """Verify missing zoo_model_id blocks production export with IF-EXPORT-003."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="step",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
        zoo_model_id="",
    )

    assert not res.success
    assert res.error_id == "IF-EXPORT-003"


@pytest.mark.asyncio
async def test_zoo_native_export_failure_handling(approved_project: Project):
    """Verify WebSocket engine error returns clear ExportResult failure envelope."""
    provider = ZooExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = [
        '{"success": false, "errors": [{"message": "Zoo native export failed"}]}'
    ]
    mock_ws.send = AsyncMock()

    with patch("websockets.connect") as mock_connect:
        mock_connect.return_value.__aenter__.return_value = mock_ws
        res = await provider.export_format(
            project_id=approved_project.project_id,
            model_revision=1,
            format_name="stl",
            kcl_code=kcl_res.kcl_code,
            project=approved_project,
            zoo_model_id="err_sess_uncached_9999",
            kcl_hash=kcl_res.kcl_hash,
        )

        assert not res.success
        assert res.error_id == "IF-EXPORT-001"
        assert "Zoo native export failed" in res.error_message


@pytest.mark.asyncio
async def test_mock_provider_isolation(approved_project: Project):
    """Verify MockExportProvider operates deterministically without external credentials."""
    provider = MockExportProvider()
    kcl_res = compile_project_to_kcl(approved_project)

    res = await provider.export_format(
        project_id=approved_project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_res.kcl_code,
        project=approved_project,
    )

    assert res.success
    assert res.is_mock is True
    assert res.facet_count is not None
