import os
import json
import uuid
import asyncio
import base64
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

async def main():
    print("=== TESTING ZOO ENGINE WEBSOCKET EXPORT3D FULL FLOW ===")
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    ws_headers = {"Authorization": f"Bearer {token}"}
    
    async with websockets.connect(ws_url, additional_headers=ws_headers) as ws:
        async def send_cmd(name, cmd_dict):
            cmd_id = str(uuid.uuid4())
            payload = {
                "type": "modeling_cmd_req",
                "cmd_id": cmd_id,
                "cmd": cmd_dict
            }
            await ws.send(json.dumps(payload))
            while True:
                recv_msg = await ws.recv()
                if isinstance(recv_msg, bytes):
                    continue
                data = json.loads(recv_msg)
                if data.get("resp", {}).get("type") == "modeling" or not data.get("success", True):
                    return data

        # 1. Set scene units
        r_units = await send_cmd("units", {"type": "set_scene_units", "unit": "mm"})
        print("[WS] set_scene_units:", r_units.get("success"))

        # 2. Make plane
        r_plane = await send_cmd("make_plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })
        print("[WS] make_plane:", r_plane.get("success"))

        # 3. Start path
        r_path = await send_cmd("start_path", {"type": "start_path"})
        print("[WS] start_path:", r_path.get("success"))

        # 4. Probe scene entity IDs
        r_entities = await send_cmd("scene_get_entity_ids", {
            "type": "scene_get_entity_ids",
            "filter": [],
            "skip": 0,
            "take": 100
        })
        print("[WS] scene_get_entity_ids:", r_entities.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}))

        # 5. Take snapshot
        r_snap = await send_cmd("take_snapshot", {"type": "take_snapshot", "format": "png"})
        print("[WS] take_snapshot:", r_snap.get("success"))

        # 6. Test export3d for gltf / stl / step
        coords = {
            "forward": {"axis": "y", "direction": "positive"},
            "up": {"axis": "z", "direction": "positive"},
        }
        
        # Test GLTF export
        gltf_fmt = {
            "type": "gltf",
            "storage": "embedded",
            "presentation": "compact",
        }
        r_gltf = await send_cmd("export3d_gltf", {
            "type": "export3d",
            "format": gltf_fmt,
            "entity_ids": [],
        })
        print("[WS EXPORT GLTF] success:", r_gltf.get("success"))
        if not r_gltf.get("success"):
            print("  error:", r_gltf.get("errors"))
        else:
            files = r_gltf.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("files", [])
            print(f"  files count: {len(files)}")
            if files:
                print(f"  file[0] length: {len(files[0].get('contents', ''))} base64 chars")

asyncio.run(main())
