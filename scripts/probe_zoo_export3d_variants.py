import os
import json
import uuid
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

async def main():
    print("=== PROBING WEBSOCKET EXPORT3D VARIANTS ===")
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

        # Test export3d formats with binary / ascii storage
        stl_binary_fmt = {"type": "stl", "storage": "binary", "selection": {"type": "default_scene"}}
        stl_ascii_fmt = {"type": "stl", "storage": "ascii", "selection": {"type": "default_scene"}}
        step_fmt = {"type": "step", "storage": "header", "selection": {"type": "default_scene"}}
        step_fmt_simple = {"type": "step", "selection": {"type": "default_scene"}}

        res_stl_bin = await send_cmd("export3d_stl_binary", {
            "type": "export3d",
            "format": stl_binary_fmt,
            "entity_ids": [],
        })
        print("[WS] export3d (STL Binary) res:", json.dumps(res_stl_bin)[:500])

        res_stl_asc = await send_cmd("export3d_stl_ascii", {
            "type": "export3d",
            "format": stl_ascii_fmt,
            "entity_ids": [],
        })
        print("[WS] export3d (STL ASCII) res:", json.dumps(res_stl_asc)[:500])

        res_step = await send_cmd("export3d_step", {
            "type": "export3d",
            "format": step_fmt_simple,
            "entity_ids": [],
        })
        print("[WS] export3d (STEP Simple) res:", json.dumps(res_step)[:500])

        # Test export command variants
        res_exp_stl = await send_cmd("export_stl", {
            "type": "export",
            "format": stl_binary_fmt,
            "entity_ids": [],
        })
        print("[WS] export (STL) res:", json.dumps(res_exp_stl)[:500])

        res_exp_step = await send_cmd("export_step", {
            "type": "export",
            "format": step_fmt_simple,
            "entity_ids": [],
        })
        print("[WS] export (STEP) res:", json.dumps(res_exp_step)[:500])

asyncio.run(main())
