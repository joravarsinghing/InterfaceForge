import os
import json
import uuid
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

async def main():
    print("=== PROBING WEBSOCKET EXPORT3D WITH COORDS ===")
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

        await send_cmd("set_scene_units", {"type": "set_scene_units", "unit": "mm"})

        # Make plane
        await send_cmd("make_plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })

        coords = {
            "forward": {"axis": "y", "direction": "positive"},
            "up": {"axis": "z", "direction": "positive"},
        }
        
        stl_binary_fmt = {
            "type": "stl",
            "storage": "binary",
            "selection": {"type": "default_scene"},
            "coords": coords,
        }
        step_fmt = {
            "type": "step",
            "coords": coords,
            "selection": {"type": "default_scene"},
        }

        res_stl = await send_cmd("export3d_stl", {
            "type": "export3d",
            "format": stl_binary_fmt,
            "entity_ids": [],
        })
        print("[WS] export3d (STL) res:", json.dumps(res_stl)[:500])

        res_step = await send_cmd("export3d_step", {
            "type": "export3d",
            "format": step_fmt,
            "entity_ids": [],
        })
        print("[WS] export3d (STEP) res:", json.dumps(res_step)[:500])

asyncio.run(main())
