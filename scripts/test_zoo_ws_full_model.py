import os
import json
import uuid
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

async def main():
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
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
                    print(f"[{name}] -> success={data.get('success')}, resp={json.dumps(data)}")
                    return data

        print("1. Setting units...")
        await send_cmd("units", {"type": "set_scene_units", "unit": "mm"})

        plane_id = str(uuid.uuid4())
        print(f"Making plane {plane_id}...")
        p_res = await send_cmd("plane", {
            "type": "make_plane",
            "plane_id": plane_id,
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })
        await send_cmd("get_ids_1", {"type": "scene_get_entity_ids", "filter": [], "skip": 0, "take": 100})

        path_id = str(uuid.uuid4())
        print(f"Starting path {path_id}...")
        path_res = await send_cmd("start_path", {"type": "start_path", "path_id": path_id})

        print("5. Extending path segments...")
        await send_cmd("line1", {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": 50, "y": 0, "z": 0},
                "relative": False
            }
        })
        await send_cmd("line2", {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": 50, "y": 50, "z": 0},
                "relative": False
            }
        })
        await send_cmd("line3", {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": 0, "y": 50, "z": 0},
                "relative": False
            }
        })
        await send_cmd("close", {
            "type": "close_path",
            "path_id": path_id
        })

        target_id = str(uuid.uuid4())
        print(f"6. Extruding path {path_id}...")
        ext_res = await send_cmd("extrude", {
            "type": "extrude",
            "target": path_id,
            "distance": 25.0
        })
        print("Extrude output:", json.dumps(ext_res)[:300])

        print("7. Exporting glTF...")
        exp_res = await send_cmd("export", {
            "type": "export",
            "entity_ids": [],
            "format": {
                "type": "gltf",
                "storage": "embedded",
                "presentation": "compact"
            }
        })
        print("Export glTF output:", json.dumps(exp_res)[:400])

asyncio.run(main())
