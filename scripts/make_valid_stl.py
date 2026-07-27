import asyncio
import json
import sys
import os
import uuid
import base64
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import websockets
from app.core.config import settings
from app.services.export_provider import parse_and_validate_stl, parse_and_validate_step

def create_valid_binary_stl_box() -> bytes:
    header = b"InterfaceForge Binary STL Test Box".ljust(80, b"\x00")[:80]
    v = [
        (0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 20.0, 0.0), (0.0, 20.0, 0.0),
        (0.0, 0.0, 20.0), (20.0, 0.0, 20.0), (20.0, 20.0, 20.0), (0.0, 20.0, 20.0)
    ]
    triangles = [
        (0, 2, 1, (0.0, 0.0, -1.0)), (0, 3, 2, (0.0, 0.0, -1.0)),
        (4, 5, 6, (0.0, 0.0, 1.0)), (4, 6, 7, (0.0, 0.0, 1.0)),
        (0, 1, 5, (0.0, -1.0, 0.0)), (0, 5, 4, (0.0, -1.0, 0.0)),
        (1, 2, 6, (1.0, 0.0, 0.0)), (1, 6, 5, (1.0, 0.0, 0.0)),
        (2, 3, 7, (0.0, 1.0, 0.0)), (2, 7, 6, (0.0, 1.0, 0.0)),
        (3, 0, 4, (-1.0, 0.0, 0.0)), (3, 4, 7, (-1.0, 0.0, 0.0)),
    ]
    body = struct.pack("<I", len(triangles))
    for v1_i, v2_i, v3_i, norm in triangles:
        v1, v2, v3 = v[v1_i], v[v2_i], v[v3_i]
        tri_data = (
            norm[0], norm[1], norm[2],
            v1[0], v1[1], v1[2],
            v2[0], v2[1], v2[2],
            v3[0], v3[1], v3[2],
            0
        )
        body += struct.pack("<ffffffffffffH", *tri_data)
        
    return header + body

async def main():
    token = settings.zoo_api_token
    ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    
    stl_bytes = create_valid_binary_stl_box()
    byte_array = list(stl_bytes)
    print(f"Generated Binary STL Box ({len(stl_bytes)} bytes / {len(byte_array)} int array)...")
    
    print(f"Connecting to Zoo Modeling WebSocket...")
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        async def send_cmd(cmd_dict: dict) -> dict:
            c_id = str(uuid.uuid4())
            payload = {
                "type": "modeling_cmd_req",
                "cmd_id": c_id,
                "cmd": cmd_dict,
            }
            print(f"\n---> SENDING: {cmd_dict['type']}")
            await ws.send(json.dumps(payload))

            while True:
                recv_msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                if isinstance(recv_msg, bytes):
                    return {"binary": recv_msg}
                data = json.loads(recv_msg)
                
                resp_type = data.get("resp", {}).get("type")
                if resp_type in ("modeling_session_data", "ice_server_info", "metrics_request"):
                    continue

                if not data.get("success", True):
                    errs = data.get("errors", [])
                    print(f" !!! ENGINE ERROR: {errs}")
                    return {"error": errs}

                if resp_type == "modeling":
                    resp_data = data.get("resp", {}).get("data", {})
                    m_resp = resp_data.get("modeling_response", {})
                    return m_resp

        # Step 1: set_scene_units
        await send_cmd({"type": "set_scene_units", "unit": "mm"})
        
        # Step 2: import_files into engine session
        print("\n--- Importing valid binary STL into Zoo Engine session ---")
        imp_res = await send_cmd({
            "type": "import_files",
            "files": [{"path": "box.stl", "data": byte_array}],
            "format": {
                "type": "stl",
                "coords": {
                    "forward": {"axis": "y", "direction": "negative"},
                    "up": {"axis": "z", "direction": "positive"}
                },
                "units": "mm"
            }
        })
        print(f"Import Result: {json.dumps(imp_res)}")
        object_id = imp_res.get("data", {}).get("object_id")
        print(f"Captured object_id: {object_id}")
        
        # Step 3: Issue Zoo-native export command for STL with object_id
        print("\n--- Issuing Zoo-native export command for STL ---")
        stl_res = await send_cmd({
            "type": "export",
            "entity_ids": [object_id] if object_id else [],
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
        print(f"STL Export Response: {json.dumps(stl_res)[:600]}")
        stl_files = stl_res.get("data", {}).get("files", {})
        print(f"STL files returned: {list(stl_files.keys())}")
        for fname, fcontent in stl_files.items():
            fb = base64.b64decode(fcontent) if isinstance(fcontent, str) else bytes(fcontent)
            val = parse_and_validate_stl(fb)
            print(f"  --> File {fname}: {len(fb)} bytes | STL Val: {val}")

        # Step 4: Issue Zoo-native export command for STEP with object_id
        print("\n--- Issuing Zoo-native export command for STEP ---")
        step_res = await send_cmd({
            "type": "export",
            "entity_ids": [object_id] if object_id else [],
            "format": {
                "type": "step",
                "coords": {
                    "forward": {"axis": "y", "direction": "negative"},
                    "up": {"axis": "z", "direction": "positive"}
                },
                "selection": {"type": "default_scene"},
            }
        })
        print(f"STEP Export Response: {json.dumps(step_res)[:600]}")
        step_files = step_res.get("data", {}).get("files", {})
        print(f"STEP files returned: {list(step_files.keys())}")
        for fname, fcontent in step_files.items():
            fb = base64.b64decode(fcontent) if isinstance(fcontent, str) else bytes(fcontent)
            val = parse_and_validate_step(fb)
            print(f"  --> File {fname}: {len(fb)} bytes | STEP Val: {val}")

if __name__ == "__main__":
    asyncio.run(main())
