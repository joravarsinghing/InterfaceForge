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
    print("=== TESTING ZOO-NATIVE KCL -> WEBSOCKET EXPORT3D FLOW ===")
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
        await send_cmd("units", {"type": "set_scene_units", "unit": "mm"})

        # 2. Make plane
        plane_res = await send_cmd("make_plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })

        # 3. Start path & draw circular coaxial profile geometry
        import math
        segments = 16
        path_id = str(uuid.uuid4())
        await send_cmd("start_path", {"type": "start_path"})

        r = 25.0
        for i in range(segments):
            theta = (2 * math.pi * i) / segments
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            if i == 0:
                await send_cmd("move_to", {"type": "move_to", "path": path_id, "to": {"x": x, "y": y, "z": 0}})
            else:
                await send_cmd("line_to", {"type": "line_to", "path": path_id, "to": {"x": x, "y": y, "z": 0}, "relative": False})

        await send_cmd("close_path", {"type": "close_path", "path_id": path_id})

        # 4. Extrude to solid 3D body
        extrude_res = await send_cmd("extrude", {
            "type": "extrude",
            "target": path_id,
            "distance": 40.0,
            "cap": "both"
        })
        print(f"[WS] Extrude result: {json.dumps(extrude_res)}")

        # 5. Execute export3d for STL
        coords = {
            "forward": {"axis": "y", "direction": "positive"},
            "up": {"axis": "z", "direction": "positive"},
        }
        stl_fmt = {
            "type": "stl",
            "storage": "binary",
            "selection": {"type": "default_scene"},
            "coords": coords,
            "units": "mm",
        }

        stl_export_res = await send_cmd("export3d_stl", {
            "type": "export3d",
            "format": stl_fmt,
            "entity_ids": [],
        })
        print("[WS EXPORT STL] success:", stl_export_res.get("success"))
        stl_files = stl_export_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("files", [])
        if stl_files:
            stl_bytes = base64.b64decode(stl_files[0].get("contents", ""))
            print(f"[WS EXPORT STL] Received {len(stl_bytes)} STL bytes!")
            print("  STL header:", stl_bytes[:80])

        # 6. Execute export3d for STEP
        step_fmt = {
            "type": "step",
            "coords": coords,
            "selection": {"type": "default_scene"},
        }
        step_export_res = await send_cmd("export3d_step", {
            "type": "export3d",
            "format": step_fmt,
            "entity_ids": [],
        })
        print("[WS EXPORT STEP] success:", step_export_res.get("success"))
        step_files = step_export_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("files", [])
        if step_files:
            step_bytes = base64.b64decode(step_files[0].get("contents", ""))
            print(f"[WS EXPORT STEP] Received {len(step_bytes)} STEP bytes!")
            print("  STEP header:", step_bytes[:100].decode("utf-8", errors="ignore"))

asyncio.run(main())
