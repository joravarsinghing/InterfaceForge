import os
import json
import urllib.request
import urllib.error
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

endpoints = [
    ("/kcl/compile", "POST", json.dumps({"code": "const p = 1"}).encode()),
    ("/kcl/execute", "POST", json.dumps({"code": "const p = 1"}).encode()),
    ("/modeling/commands", "POST", json.dumps({}).encode()),
    ("/file/conversion/stl/step", "POST", b"solid test\nendsolid test\n"),
    ("/file/conversion/obj/stl", "POST", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"),
    ("/file/conversion/obj/step", "POST", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"),
]

for path, method, data in endpoints:
    url = f"https://api.zoo.dev{path}"
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InterfaceForge/1.0",
            "Content-Type": "application/json" if "json" in path or "kcl" in path else "application/octet-stream",
        },
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"{path}: HTTP {resp.status} - {resp.read()[:200]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"{path}: HTTP {e.code} - {body[:200]}")
    except Exception as e:
        print(f"{path}: ERROR {e}")

async def test_ws_cmds():
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        # Try sending export command schema or kcl execution command schema
        cmds_to_try = [
            {"type": "export_scene", "format": "stl"},
            {"type": "export_scene", "format": "step"},
            {"type": "export", "entity_ids": [], "format": {"type": "stl"}},
            {"type": "export", "entity_ids": [], "format": {"type": "step"}},
            {"type": "execute_code", "code": "const p = 1"},
        ]
        for cmd in cmds_to_try:
            cmd_id = f"id_{cmd['type']}"
            await ws.send(json.dumps({
                "type": "modeling_cmd_req",
                "cmd_id": cmd_id,
                "cmd": cmd
            }))
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    continue
                d = json.loads(msg)
                if d.get("resp", {}).get("type") == "modeling" or not d.get("success", True) or "errors" in d:
                    print(f"WS {cmd['type']}:", d)
                    break
                else:
                    print(f"WS {cmd['type']} frame:", d)
                    # Break if it's session data or non-response
                    if d.get("resp", {}).get("type") not in ("modeling_session_data", "metrics_request"):
                        break

asyncio.run(test_ws_cmds())
