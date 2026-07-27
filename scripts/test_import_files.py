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
            print(f"\n---> SENDING: {cmd_dict['type']}")
            await ws.send(json.dumps(payload))

            while True:
                recv_msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
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
                    print(f"FULL RESP_DATA: {json.dumps(resp_data)[:500]}")
                    return resp_data

        await send_cmd({"type": "set_scene_units", "unit": "mm"})
        
        print("\n--- Probing import_files data type ---")
        await send_cmd({
            "type": "import_files",
            "files": [{"path": "box.stl", "data": 123}],
            "format": {"type": "stl", "coords": {"forward": {"axis": "y", "direction": "negative"}, "up": {"axis": "z", "direction": "positive"}}, "units": "mm"}
        })

if __name__ == "__main__":
    asyncio.run(main())
