import os
import json
import uuid
import asyncio
import urllib.request
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

async def main():
    print("=== PROBING ZOO API FOR KCL EXPORT & WEBSOCKET EXPORT COMMANDS ===")
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "InterfaceForge/1.0",
        "Content-Type": "application/octet-stream",
    }
    
    kcl_code = """
fn adapter_ring(r1, r2, h) {
  return startSketchOn('XY')
    |> circle({ radius: r1 }, %)
    |> extrude(length: h, %)
}
adapter_ring(25.0, 20.0, 40.0)
"""
    kcl_bytes = kcl_code.encode("utf-8")

    # 1. Test REST endpoints for KCL
    rest_urls = [
        ("POST /file/conversion/kcl/stl", "https://api.zoo.dev/file/conversion/kcl/stl"),
        ("POST /file/conversion/kcl/step", "https://api.zoo.dev/file/conversion/kcl/step"),
        ("POST /kcl/export/stl", "https://api.zoo.dev/kcl/export/stl"),
        ("POST /kcl/export/step", "https://api.zoo.dev/kcl/export/step"),
        ("POST /file/export/stl", "https://api.zoo.dev/file/export/stl"),
        ("POST /file/export/step", "https://api.zoo.dev/file/export/step"),
    ]

    for name, url in rest_urls:
        try:
            req = urllib.request.Request(
                url,
                data=kcl_bytes,
                headers=headers,
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            res_data = resp.read()
            print(f"[REST OK] {name}: status={resp.status}, length={len(res_data)}")
            print("  Body snippet:", res_data[:200])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            print(f"[REST HTTP {e.code}] {name}: {err_body[:200]}")
        except Exception as ex:
            print(f"[REST ERR] {name}: {ex}")

    # 2. Test WebSocket commands for executing scene and exporting
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    ws_headers = {"Authorization": f"Bearer {token}"}
    
    try:
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

            print("\n--- Testing WebSocket export3d / export variants ---")
            
            # Setup scene units
            await send_cmd("set_scene_units", {"type": "set_scene_units", "unit": "mm"})

            # Get entity IDs or create a shape
            make_plane_res = await send_cmd("make_plane", {
                "type": "make_plane",
                "origin": {"x": 0, "y": 0, "z": 0},
                "x_axis": {"x": 1, "y": 0, "z": 0},
                "y_axis": {"x": 0, "y": 1, "z": 0},
                "size": 100,
                "clobber": False,
                "hide": True,
            })
            print("[WS] make_plane res:", json.dumps(make_plane_res))

            # Query scene entity IDs
            get_entities = await send_cmd("scene_get_entity_ids", {
                "type": "scene_get_entity_ids",
                "filter": [],
                "skip": 0,
                "take": 100
            })
            print("[WS] scene_get_entity_ids res:", json.dumps(get_entities))
            
            entity_ids = []
            if get_entities.get("resp", {}).get("type") == "modeling":
                m_data = get_entities.get("resp", {}).get("data", {}).get("modeling_response", {}).get("data", {})
                entity_ids = m_data.get("entity_ids", [])
            print(f"[WS] Entity IDs found: {entity_ids}")

            # Test export3d formats
            fmt_stl = {"type": "stl", "storage": "embedded", "selection": {"type": "default_scene"}}
            fmt_step = {"type": "step", "storage": "embedded", "selection": {"type": "default_scene"}}

            res_stl = await send_cmd("export3d_stl", {
                "type": "export3d",
                "format": fmt_stl,
                "entity_ids": entity_ids,
            })
            print("[WS] export3d (STL) res:", json.dumps(res_stl)[:300])

            res_step = await send_cmd("export3d_step", {
                "type": "export3d",
                "format": fmt_step,
                "entity_ids": entity_ids,
            })
            print("[WS] export3d (STEP) res:", json.dumps(res_step)[:300])

            # Test export command
            res_export_stl = await send_cmd("export_stl", {
                "type": "export",
                "format": fmt_stl,
                "entity_ids": entity_ids,
            })
            print("[WS] export (STL) res:", json.dumps(res_export_stl)[:300])

    except Exception as e:
        print(f"[WS ERR] {e}")

asyncio.run(main())
