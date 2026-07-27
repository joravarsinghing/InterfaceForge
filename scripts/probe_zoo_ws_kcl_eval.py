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
    print("=== PROBING WEBSOCKET KCL EVALUATION & EXPORT ===")
    ws_url = "wss://api.zoo.dev/ws/modeling/commands"
    ws_headers = {"Authorization": f"Bearer {token}"}
    
    kcl_sample = """
fn adapter_ring(r1, r2, h) {
  return startSketchOn('XY')
    |> circle({ radius: r1 }, %)
    |> extrude(length: h, %)
}
adapter_ring(25.0, 20.0, 40.0)
"""

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
                print(f"[{name}] RECV:", json.dumps(data)[:300])
                if data.get("resp", {}).get("type") == "modeling" or not data.get("success", True):
                    return data

        await send_cmd("units", {"type": "set_scene_units", "unit": "mm"})

        cmds = [
            ("engine_util_eval_kcl", {"type": "engine_util_eval_kcl", "kcl": kcl_sample}),
            ("kcl_code", {"type": "kcl_code", "code": kcl_sample}),
            ("execute_kcl", {"type": "execute_kcl", "code": kcl_sample}),
            ("parse_kcl", {"type": "parse_kcl", "code": kcl_sample}),
            ("kcl", {"type": "kcl", "code": kcl_sample}),
        ]

        for name, cmd in cmds:
            res = await send_cmd(name, cmd)

        # Now test export3d after executing KCL or commands
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
        step_fmt = {
            "type": "step",
            "coords": coords,
            "selection": {"type": "default_scene"},
        }

        res_stl = await send_cmd("export3d_stl", {
            "type": "export3d",
            "format": stl_fmt,
            "entity_ids": [],
        })
        res_step = await send_cmd("export3d_step", {
            "type": "export3d",
            "format": step_fmt,
            "entity_ids": [],
        })

asyncio.run(main())
