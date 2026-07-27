import os
import json
import urllib.request
import urllib.error
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

print("Testing Zoo File Conversion REST API with KCL input...")

kcl_code = """
fn plate() {
  const p = startPathAt([0, 0])
    |> line(end = [100, 0])
    |> line(end = [100, 50])
    |> line(end = [0, 50])
    |> close()
  return extrude(p, length = 10)
}
const p1 = plate()
"""

for output_fmt in ["stl", "step", "obj", "gltf"]:
    url = f"https://api.zoo.dev/file/conversion/kcl/{output_fmt}"
    req = urllib.request.Request(
        url,
        data=kcl_code.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InterfaceForge/1.0",
            "Content-Type": "text/plain",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        res_json = json.loads(resp.read().decode("utf-8"))
        print(f"KCL -> {output_fmt}: SUCCESS")
        outputs = res_json.get("outputs", {})
        for k, v in outputs.items():
            print(f"  file: {k}, length of base64: {len(v)}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"KCL -> {output_fmt}: HTTP {e.code} - {body[:200]}")
    except Exception as e:
        print(f"KCL -> {output_fmt}: ERROR {e}")

print("\nTesting WebSocket modeling export command...")
async def test_ws_export():
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        # Send set_scene_units
        await ws.send(json.dumps({
            "type": "modeling_cmd_req",
            "cmd_id": "1",
            "cmd": {"type": "set_scene_units", "unit": "mm"}
        }))
        resp = await ws.recv()
        print("Units resp:", resp[:150])

        # Test export command options
        for export_fmt in ["stl", "step", "obj"]:
            await ws.send(json.dumps({
                "type": "modeling_cmd_req",
                "cmd_id": f"export_{export_fmt}",
                "cmd": {"type": "export", "format": export_fmt}
            }))
            resp = await ws.recv()
            print(f"Export {export_fmt} resp:", resp[:300])

asyncio.run(test_ws_export())
