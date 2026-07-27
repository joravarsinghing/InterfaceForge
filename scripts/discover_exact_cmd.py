import asyncio
import json
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import websockets
from app.core.config import settings

async def main():
    token = settings.zoo_api_token
    ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Connecting to Zoo Modeling WebSocket...")
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        async def send_cmd(cmd_dict: dict) -> dict:
            c_id = str(uuid.uuid4())
            payload = {
                "type": "modeling_cmd_req",
                "cmd_id": c_id,
                "cmd": cmd_dict,
            }
            print(f"\n---> SENDING: {cmd_dict}")
            await ws.send(json.dumps(payload))

            while True:
                recv_msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                if isinstance(recv_msg, bytes):
                    print(f"<--- RECV BINARY ({len(recv_msg)} bytes)")
                    return {"binary": recv_msg}
                data = json.loads(recv_msg)
                print(f"<--- RECV JSON: {json.dumps(data)}")

                if not data.get("success", True):
                    errs = data.get("errors", [])
                    print(f" !!! ENGINE ERROR: {errs}")
                    return {"error": errs}

                if data.get("resp", {}).get("type") == "modeling":
                    resp_data = data.get("resp", {}).get("data", {})
                    m_resp = resp_data.get("modeling_response", {})
                    print(f" ===> MATCHED MODELING RESP: {m_resp}")
                    return m_resp

        # 1. Setup scene
        r1 = await send_cmd({"type": "set_scene_units", "unit": "mm"})
        r2 = await send_cmd({
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        })
        
        # 2. Test export_scene command variations
        export_tests = [
            {"type": "export_scene"},
            {"type": "export_scene", "format": "stl"},
            {"type": "export_scene", "format": {"type": "stl"}},
            {"type": "export_scene", "format": {"type": "stl", "coords": "gltf"}},
            {"type": "export_scene", "format": {"type": "step"}},
            {"type": "export"},
            {"type": "export_file"},
            {"type": "export_geometry"},
        ]
        
        for exp in export_tests:
            await send_cmd(exp)

if __name__ == "__main__":
    asyncio.run(main())
