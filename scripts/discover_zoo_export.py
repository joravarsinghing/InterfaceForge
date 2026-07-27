import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import websockets
from app.core.config import settings

async def main():
    token = settings.zoo_api_token
    ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Connecting to Zoo Modeling WebSocket...")
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        # Listen background task to print all incoming messages
        async def listen():
            try:
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, bytes):
                        print(f"[RECV BINARY] {len(msg)} bytes")
                    else:
                        print(f"[RECV TEXT] {msg[:500]}")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[RECV ENDED] {e}")

        listener = asyncio.create_task(listen())
        
        async def send(cmd):
            payload = {
                "type": "modeling_cmd_req",
                "cmd_id": "test_id_123",
                "cmd": cmd
            }
            print(f"\n[SEND] {json.dumps(cmd)}")
            await ws.send(json.dumps(payload))
            await asyncio.sleep(1.0)

        await send({"type": "set_scene_units", "unit": "mm"})
        await send({"type": "make_plane", "origin": {"x":0,"y":0,"z":0}, "x_axis":{"x":1,"y":0,"z":0}, "y_axis":{"x":0,"y":1,"z":0}, "size":100, "clobber":False, "hide":True})
        await send({"type": "start_path"})
        
        # Test candidate export commands
        candidates = [
            {"type": "export"},
            {"type": "export_scene", "format": {"type": "stl"}},
            {"type": "export_scene", "format": "stl"},
            {"type": "export_file", "format": "stl"},
            {"type": "export", "format": "stl"},
            {"type": "export_3d", "format": "stl"},
            {"type": "kcl_code", "code": "const x = 1"},
            {"type": "execute_kcl", "code": "const x = 1"},
            {"type": "kcl", "code": "const x = 1"}
        ]
        
        for cand in candidates:
            await send(cand)

        listener.cancel()

if __name__ == "__main__":
    asyncio.run(main())
