import asyncio
import json
import math
import os
import sys
import uuid
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    import msgpack
except ImportError:
    msgpack = None

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app.core.config import settings
from app.services.export_provider import parse_and_validate_stl, parse_and_validate_step, unpack_msgpack

async def build_ngon_sketch(send_cmd, plane_id: str, radius: float, n_sides: int = 16) -> str:
    """Build a smooth n-gon circle approximation on plane_id."""
    await send_cmd({"type": "enable_sketch_mode", "entity_id": plane_id, "ortho": False, "animated": False, "adjust_camera": False})
    r_start = await send_cmd({"type": "start_path"})
    path_id = r_start.get("request_id")

    pts = []
    for i in range(n_sides):
        ang = 2.0 * math.pi * i / n_sides
        pts.append((round(radius * math.cos(ang), 4), round(radius * math.sin(ang), 4)))

    await send_cmd({"type": "move_path_pen", "path": path_id, "to": {"x": pts[0][0], "y": pts[0][1], "z": 0.0}})
    for px, py in pts[1:]:
        await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": px, "y": py, "z": 0.0}, "relative": False}})
    await send_cmd({"type": "close_path", "path_id": path_id})
    await send_cmd({"type": "sketch_mode_disable"})
    return path_id

async def build_rect_sketch(send_cmd, plane_id: str, width: float, height: float) -> str:
    """Build a rectangle path on plane_id."""
    half_w = width / 2.0
    half_h = height / 2.0
    await send_cmd({"type": "enable_sketch_mode", "entity_id": plane_id, "ortho": False, "animated": False, "adjust_camera": False})
    r_start = await send_cmd({"type": "start_path"})
    path_id = r_start.get("request_id")

    await send_cmd({"type": "move_path_pen", "path": path_id, "to": {"x": -half_w, "y": -half_h, "z": 0.0}})
    await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": half_w, "y": -half_h, "z": 0.0}, "relative": False}})
    await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": half_w, "y": half_h, "z": 0.0}, "relative": False}})
    await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": -half_w, "y": half_h, "z": 0.0}, "relative": False}})
    await send_cmd({"type": "close_path", "path_id": path_id})
    await send_cmd({"type": "sketch_mode_disable"})
    return path_id

async def generate_live_adapter(case_num: int, title: str, shape_a: str, dim_a: tuple, shape_b: str, dim_b: tuple, length: float, wall: float, offset_x: float, offset_y: float, angle_deg: float):
    token = settings.zoo_api_token
    ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n==================================================")
    print(f"EXECUTING LIVE CASE {case_num}: {title}")
    print(f"==================================================")

    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        async def send_cmd(cmd_dict: dict) -> dict:
            c_id = str(uuid.uuid4())
            payload = {
                "type": "modeling_cmd_req",
                "cmd_id": c_id,
                "cmd": cmd_dict,
            }
            await ws.send(json.dumps(payload))

            while True:
                recv_msg = await asyncio.wait_for(ws.recv(), timeout=25.0)
                if isinstance(recv_msg, bytes):
                    if msgpack is not None:
                        return msgpack.unpackb(recv_msg, raw=False)
                    obj, _ = unpack_msgpack(recv_msg)
                    return obj
                data = json.loads(recv_msg)
                resp_type = data.get("resp", {}).get("type")
                if resp_type in ("modeling_session_data", "ice_server_info", "metrics_request"):
                    continue
                if resp_type == "modeling":
                    return data
                if not data.get("success", True):
                    errs = data.get("errors", [])
                    print(f"Error for cmd {cmd_dict.get('type')}: {errs}")
                    return data

        await send_cmd({"type": "set_scene_units", "unit": "mm"})

        # Plane A at origin
        await send_cmd({
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })

        # Plane B at Z=length with offset and angle rotation
        rad_a = math.radians(angle_deg)
        cos_a = math.cos(rad_a)
        sin_a = math.sin(rad_a)

        y_axis_b = {"x": 0.0, "y": cos_a, "z": sin_a}
        x_axis_b = {"x": 1.0, "y": 0.0, "z": 0.0}

        await send_cmd({
            "type": "make_plane",
            "origin": {"x": offset_x, "y": offset_y, "z": length},
            "x_axis": x_axis_b,
            "y_axis": y_axis_b,
            "size": 100,
            "clobber": False,
            "hide": True,
        })

        r_planes = await send_cmd({"type": "scene_get_entity_ids", "filter": ["plane"], "skip": 0, "take": 10})
        plane_ids = r_planes.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("entity_ids", [[]])[0]
        plane_a_id = plane_ids[0]
        plane_b_id = plane_ids[1]

        # 1. Outer Sketches
        if shape_a == "circle":
            path_outer_a = await build_ngon_sketch(send_cmd, plane_a_id, dim_a[0] / 2.0)
            path_inner_a = await build_ngon_sketch(send_cmd, plane_a_id, (dim_a[0] / 2.0) - wall)
        else:
            path_outer_a = await build_rect_sketch(send_cmd, plane_a_id, dim_a[0], dim_a[1])
            path_inner_a = await build_rect_sketch(send_cmd, plane_a_id, dim_a[0] - 2*wall, dim_a[1] - 2*wall)

        if shape_b == "circle":
            path_outer_b = await build_ngon_sketch(send_cmd, plane_b_id, dim_b[0] / 2.0)
            path_inner_b = await build_ngon_sketch(send_cmd, plane_b_id, (dim_b[0] / 2.0) - wall)
        else:
            path_outer_b = await build_rect_sketch(send_cmd, plane_b_id, dim_b[0], dim_b[1])
            path_inner_b = await build_rect_sketch(send_cmd, plane_b_id, dim_b[0] - 2*wall, dim_b[1] - 2*wall)

        # Outer Loft
        r_loft_outer = await send_cmd({
            "type": "loft",
            "section_ids": [path_outer_a, path_outer_b],
            "v_degree": 1,
            "bez_approximate_rational": False,
            "tolerance": 0.001,
        })
        outer_solid_id = r_loft_outer.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("solid_id")

        # Inner Loft
        r_loft_inner = await send_cmd({
            "type": "loft",
            "section_ids": [path_inner_a, path_inner_b],
            "v_degree": 1,
            "bez_approximate_rational": False,
            "tolerance": 0.001,
        })
        inner_solid_id = r_loft_inner.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("solid_id")

        # Boolean Subtract
        await send_cmd({
            "type": "boolean_subtract",
            "target_ids": [outer_solid_id],
            "tool_ids": [inner_solid_id],
            "tolerance": 0.001,
        })

        r_solid = await send_cmd({"type": "scene_get_entity_ids", "filter": ["solid3d"], "skip": 0, "take": 10})
        solid_ids = r_solid.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("entity_ids", [[]])[0]

        # Export STL
        stl_res = await send_cmd({
            "type": "export",
            "entity_ids": solid_ids,
            "format": {
                "type": "stl",
                "coords": {"forward": {"axis": "y", "direction": "negative"}, "up": {"axis": "z", "direction": "positive"}},
                "selection": {"type": "default_scene"},
                "storage": "binary",
                "units": "mm",
            }
        })
        files_stl = stl_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("files", [])
        if not files_stl:
            files_stl = stl_res.get("resp", {}).get("data", {}).get("files", [])
        c_stl = files_stl[0]["contents"]
        if isinstance(c_stl, str):
            import base64
            c_stl = base64.b64decode(c_stl)
        elif isinstance(c_stl, list):
            c_stl = bytes(c_stl)

        val_stl = parse_and_validate_stl(c_stl)

        # Export STEP
        step_res = await send_cmd({
            "type": "export",
            "entity_ids": solid_ids,
            "format": {
                "type": "step",
                "coords": {"forward": {"axis": "y", "direction": "negative"}, "up": {"axis": "z", "direction": "positive"}},
                "selection": {"type": "default_scene"},
            }
        })
        files_step = step_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("files", [])
        if not files_step:
            files_step = step_res.get("resp", {}).get("data", {}).get("files", [])
        c_step = files_step[0]["contents"]
        if isinstance(c_step, str):
            import base64
            c_step = base64.b64decode(c_step)
        elif isinstance(c_step, list):
            c_step = bytes(c_step)

        val_step = parse_and_validate_step(c_step)

        print(f"STL Size:      {len(c_stl)} bytes")
        print(f"STL Facets:    {val_stl['facet_count']}")
        print(f"STL Bounding:  {val_stl['bounding_box']}")
        print(f"STL Dims (mm): {val_stl['dimensions_mm']}")
        print(f"STEP Size:     {len(c_step)} bytes")
        print(f"STEP Entities: {val_step['entity_count']}")

        return {
            "case_num": case_num,
            "title": title,
            "stl_size": len(c_stl),
            "stl_facets": val_stl['facet_count'],
            "stl_bbox": val_stl['bounding_box'],
            "stl_dims": val_stl['dimensions_mm'],
            "step_size": len(c_step),
            "step_entities": val_step['entity_count'],
        }

async def main():
    cases = [
        (1, "Coaxial Adapter (Circle 60mm -> 40mm, L=50mm)", "circle", (60.0,), "circle", (40.0,), 50.0, 2.4, 0.0, 0.0, 0.0),
        (2, "Offset Adapter (Circle 60mm -> 40mm, OffX=20mm, OffY=10mm, L=80mm)", "circle", (60.0,), "circle", (40.0,), 80.0, 2.4, 20.0, 10.0, 0.0),
        (3, "Angled Adapter (Circle 60mm -> 40mm, Angle=25 deg, L=90mm)", "circle", (60.0,), "circle", (40.0,), 90.0, 2.4, 0.0, 0.0, 25.0),
        (4, "Rectangular Transition (Rectangle 60x60mm -> 40x30mm, L=60mm)", "rect", (60.0, 60.0), "rect", (40.0, 30.0), 60.0, 2.4, 0.0, 0.0, 0.0),
    ]

    results = []
    for c_num, title, sa, da, sb, db, l, w, ox, oy, ang in cases:
        res = await generate_live_adapter(c_num, title, sa, da, sb, db, l, w, ox, oy, ang)
        results.append(res)

    print("\n\n" + "=" * 80)
    print("SUMMARY OF ALL 4 LIVE ADAPTER CASES EXPORTED FROM ZOO ENGINE")
    print("=" * 80)
    for r in results:
        print(f"Case {r['case_num']}: {r['title']}")
        print(f"  STL: {r['stl_size']} bytes, {r['stl_facets']} facets, BBox: {r['stl_bbox']}, Dims: {r['stl_dims']}")
        print(f"  STEP: {r['step_size']} bytes, {r['step_entities']} entities\n")

if __name__ == "__main__":
    asyncio.run(main())
