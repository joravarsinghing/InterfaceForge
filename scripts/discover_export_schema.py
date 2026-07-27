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
                print(f"<--- RECV JSON: {json.dumps(data)[:500]}")

                if not data.get("success", True):
                    errs = data.get("errors", [])
                    print(f" !!! ENGINE ERROR: {errs}")
                    return {"error": errs}

                if data.get("resp", {}).get("type") == "modeling":
                    resp_data = data.get("resp", {}).get("data", {})
                    m_resp = resp_data.get("modeling_response", {})
                    print(f" ===> MATCHED MODELING RESP: {m_resp}")
                    return m_resp

        await send_cmd({"type": "set_scene_units", "unit": "mm"})
        
        print("\n--- PROBING InputFormat3d variants ---")
        await send_cmd({"type": "import_files", "files": [], "format": {"type": "dummy"}})

if __name__ == "__main__":
    asyncio.run(main())
