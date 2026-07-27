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
    print("=== TESTING WEBSOCKET SOLID CREATION & EXPORT3D ===")
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
        make_plane_res = await send_cmd("make_plane", {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })
        plane_id = make_plane_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("plane_id")
        print(f"[WS] plane_id: {plane_id}")

        # Start path
        start_path_res = await send_cmd("start_path", {"type": "start_path"})
        path_id = start_path_res.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {}).get("path_id")
        print(f"[WS] path_id: {path_id}")

        # Draw profile
        await send_cmd("move_to", {
            "type": "move_to",
            "path": path_id,
            "to": {"x": -20, "y": -20, "z": 0}
        })
        await send_cmd("line_to", {
            "type": "line_to",
            "path": path_id,
            "to": {"x": 20, "y": -20, "z": 0},
            "relative": False
        })
        await send_cmd("line_to", {
            "type": "line_to",
            "path": path_id,
            "to": {"x": 20, "y": 20, "z": 0},
            "relative": False
        })
        await send_cmd("line_to", {
            "type": "line_to",
            "path": path_id,
            "to": {"x": -20, "y": 20, "z": 0},
            "relative": False
        })
        await send_cmd("close_path", {
            "type": "close_path",
            "path_id": path_id
        })

        # Extrude to solid body
        extrude_res = await send_cmd("extrude", {
            "type": "extrude",
            "target": path_id,
            "distance": 40.0,
            "cap": "both"
        })
        print(f"[WS] Extrude result: {json.dumps(extrude_res)[:300]}")

        coords = {
            "forward": {"axis": "y", "direction": "positive"},
            "up": {"axis": "z", "direction": "positive"},
        }
        
        stl_binary_fmt = {
            "type": "stl",
            "storage": "binary",
            "selection": {"type": "default_scene"},
            "coords": coords,
            "units": "mm",
        }
        step_fmt = {
            "type": "step",
            "coords": coords,
            "selection": {"type": "default_scene"},
        }

        # Export STL
        res_stl = await send_cmd("export3d_stl", {
            "type": "export3d",
            "format": stl_binary_fmt,
            "entity_ids": [],
        })
        print("\n[WS EXPORT STL] keys:", res_stl.keys())
        m_resp_stl = res_stl.get("resp", {}).get("data", {}).get("modeling_response", {})
        print("[WS EXPORT STL] m_resp keys:", m_resp_stl.keys())
        data_stl = m_resp_stl.get("data", {})
        print("[WS EXPORT STL] data keys:", data_stl.keys())

        files_stl = data_stl.get("files", [])
        print(f"[WS EXPORT STL] files count: {len(files_stl)}")
        if files_stl:
            f0 = files_stl[0]
            print("  file name:", f0.get("name"))
            raw_b64 = f0.get("contents", "")
            raw_bytes = base64.b64decode(raw_b64)
            print(f"  decoded STL bytes: {len(raw_bytes)} bytes | header: {raw_bytes[:40]}")

        # Export STEP
        res_step = await send_cmd("export3d_step", {
            "type": "export3d",
            "format": step_fmt,
            "entity_ids": [],
        })
        m_resp_step = res_step.get("resp", {}).get("data", {}).get("modeling_response", {})
        data_step = m_resp_step.get("data", {})
        files_step = data_step.get("files", [])
        print(f"\n[WS EXPORT STEP] files count: {len(files_step)}")
        if files_step:
            f0 = files_step[0]
            print("  file name:", f0.get("name"))
            raw_b64 = f0.get("contents", "")
            raw_bytes = base64.b64decode(raw_b64)
            print(f"  decoded STEP bytes: {len(raw_bytes)} bytes | header: {raw_bytes[:80]}")

asyncio.run(main())
