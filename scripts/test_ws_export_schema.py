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
                print(f"[{name}] RECV:", json.dumps(data))
                if data.get("resp", {}).get("type") == "modeling" or not data.get("success", True):
                    return data

        await send_cmd("1", {"type": "set_scene_units", "unit": "mm"})
        # Create a sketch plane and extrude geometry
        r = await send_cmd("plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })
        # Probe primitive modeling commands
        cmds = [
            {"name": "box", "cmd": {"type": "box", "x": 10, "y": 20, "z": 30}},
            {"name": "cube", "cmd": {"type": "cube", "size": 10}},
            {"name": "cylinder", "cmd": {"type": "cylinder", "radius": 10, "length": 20}},
            {"name": "eval_kcl", "cmd": {"type": "engine_util_eval_kcl", "kcl": "const p = 1"}},
            {"name": "kcl_code", "cmd": {"type": "kcl_code", "code": "const p = 1"}},
        ]
        for c in cmds:
            res = await send_cmd(c["name"], c["cmd"])

        # Probe export3d command
        tests = [
            {"name": "export3d_empty", "cmd": {"type": "export3d"}},
            {"name": "export3d_format", "cmd": {"type": "export3d", "format": "stl"}},
            {"name": "export3d_fmt_obj", "cmd": {"type": "export3d", "format": {"type": "stl"}}},
        ]
        for t in tests:
            res = await send_cmd(t["name"], t["cmd"])

asyncio.run(main())
