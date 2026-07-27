import asyncio
import json
import os

import websockets
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("ZOO_API_TOKEN")


async def test_copilot():
    uri = "wss://api.zoo.dev/ws/ml/copilot"
    print(f"Connecting to {uri}...")
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(uri) as ws:
        # Send auth headers message per OpenAPI spec for ws/ml/copilot
        await ws.send(json.dumps({"type": "headers", "headers": headers}))

        prompt = (
            "You are a CAD parameter revision assistant. "
            "Output strictly valid JSON matching this schema:\n"
            "{\n"
            '  "changes": [\n'
            "    {\n"
            '      "field": "connection.length_mm",\n'
            '      "current_value": 50.0,\n'
            '      "proposed_value": 70.0,\n'
            '      "unit": "mm",\n'
            '      "reason": "Increase length by 20mm"\n'
            "    }\n"
            "  ],\n"
            '  "summary": "Increase length from 50mm to 70mm"\n'
            "}\n"
            "User request: Make it 20 mm longer.\n"
            "Current context: connection.length_mm=50.0"
        )

        await ws.send(json.dumps({"type": "user", "content": prompt, "mode": "fast"}))

        whole_resp = None
        while True:
            try:
                res = await asyncio.wait_for(ws.recv(), timeout=20.0)
                if isinstance(res, str):
                    data = json.loads(res)
                    print("Received event keys:", list(data.keys()))
                    if "end_of_stream" in data:
                        whole_resp = data["end_of_stream"].get("whole_response")
                        print("Whole response:", whole_resp)
                        break
                    elif "text" in data or "delta" in data:
                        print("Streaming delta:", data)
                else:
                    print("Received binary frame of length:", len(res))
            except Exception as e:
                print("Error receiving:", e)
                break


if __name__ == "__main__":
    asyncio.run(test_copilot())
