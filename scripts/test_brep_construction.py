import asyncio
import json
import sys
import os
import uuid
import base64
import msgpack

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import websockets
from app.core.config import settings
from app.services.export_provider import parse_and_validate_stl, parse_and_validate_step

async def main():
    token = settings.zoo_api_token
    ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    
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
                recv_msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                if isinstance(recv_msg, bytes):
                    return msgpack.unpackb(recv_msg, raw=False)
                data = json.loads(recv_msg)
                resp_type = data.get("resp", {}).get("type")
                if resp_type in ("modeling_session_data", "ice_server_info", "metrics_request"):
                    continue
                if resp_type == "modeling":
                    return data

        await send_cmd({"type": "set_scene_units", "unit": "mm"})
        await send_cmd({"type": "make_plane", "origin": {"x": 0, "y": 0, "z": 0}, "x_axis": {"x": 1, "y": 0, "z": 0}, "y_axis": {"x": 0, "y": 1, "z": 0}, "size": 100, "clobber": False, "hide": False})
        
        r = await send_cmd({"type": "scene_get_entity_ids", "filter": ["plane"], "skip": 0, "take": 10})
        plane_ids = r.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("entity_ids", [[]])[0]
        plane_id = plane_ids[0]
        
        await send_cmd({"type": "enable_sketch_mode", "entity_id": plane_id, "ortho": False, "animated": False, "adjust_camera": False})
        r_start = await send_cmd({"type": "start_path"})
        path_id = r_start.get("request_id")
        
        await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": 30.0, "y": 0.0, "z": 0.0}, "relative": False}})
        await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": 30.0, "y": 30.0, "z": 0.0}, "relative": False}})
        await send_cmd({"type": "extend_path", "path": path_id, "segment": {"type": "line", "end": {"x": 0.0, "y": 30.0, "z": 0.0}, "relative": False}})
        await send_cmd({"type": "close_path", "path_id": path_id})
        await send_cmd({"type": "extrude", "target": path_id, "distance": 15.0})
        await send_cmd({"type": "sketch_mode_disable"})
        
        r_solid = await send_cmd({"type": "scene_get_entity_ids", "filter": ["solid3d"], "skip": 0, "take": 10})
        solid_ids = r_solid.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("entity_ids", [[]])[0]
        
        stl_obj = await send_cmd({
            "type": "export",
            "entity_ids": solid_ids,
            "format": {
                "type": "stl",
                "coords": {
                    "forward": {"axis": "y", "direction": "negative"},
                    "up": {"axis": "z", "direction": "positive"}
                },
                "selection": {"type": "default_scene"},
                "storage": "binary",
                "units": "mm"
            }
        })
        print("stl_obj['resp']:", stl_obj.get("resp"))

        step_obj = await send_cmd({
            "type": "export",
            "entity_ids": solid_ids,
            "format": {
                "type": "step",
                "coords": {
                    "forward": {"axis": "y", "direction": "negative"},
                    "up": {"axis": "z", "direction": "positive"}
                },
                "selection": {"type": "default_scene"},
            }
        })
        print("step_obj['resp']:", step_obj.get("resp"))

        # Extract files from stl_obj
        files_stl = stl_obj.get("resp", {}).get("data", {}).get("files", [])
        for f in files_stl:
            fb = f["contents"]
            val_stl = parse_and_validate_stl(fb)
            print(f"STL File '{f['name']}': {len(fb)} bytes | Valid: {val_stl['is_valid']} | Facets: {val_stl['facet_count']} | Dim: {val_stl['dimensions_mm']}")

        files_step = step_obj.get("resp", {}).get("data", {}).get("files", [])
        for f in files_step:
            fb = f["contents"]
            val_step = parse_and_validate_step(fb)
            print(f"STEP File '{f['name']}': {len(fb)} bytes | Valid: {val_step['is_valid']} | Entities: {val_step['entity_count']} | Solid Entities: {len(val_step['solid_entities'])}")

if __name__ == "__main__":
    asyncio.run(main())
