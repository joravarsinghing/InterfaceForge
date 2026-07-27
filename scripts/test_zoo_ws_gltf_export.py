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
                    return data

        print("Setting units...")
        await send_cmd("units", {"type": "set_scene_units", "unit": "mm"})

        print("Making plane...")
        await send_cmd("plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })

        print("Starting path...")
        await send_cmd("path", {"type": "start_path"})

        print("Taking snapshot...")
        snap = await send_cmd("snap", {"type": "take_snapshot", "format": "png"})
        print("Snapshot captured.")

        print("Exporting glTF from active session...")
        exp = await send_cmd("export", {
            "type": "export",
            "entity_ids": [],
            "format": {
                "type": "gltf",
                "storage": "embedded",
                "presentation": "compact"
            }
        })
        print("Export response success:", exp.get("success"))
        print("Export response data:", json.dumps(exp)[:500])

asyncio.run(main())
