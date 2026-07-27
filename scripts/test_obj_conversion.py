import os
import json
import urllib.request
import base64
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

# Simple OBJ mesh of a 3D box/plate: 8 vertices, 12 triangular faces
obj_data = """v -25.0 -25.0 0.0
v 25.0 -25.0 0.0
v 25.0 25.0 0.0
v -25.0 25.0 0.0
v -25.0 -25.0 40.0
v 25.0 -25.0 40.0
v 25.0 25.0 40.0
v -25.0 25.0 40.0
f 1 2 3
f 1 3 4
f 5 7 6
f 5 8 7
f 1 5 6
f 1 6 2
f 2 6 7
f 2 7 3
f 3 7 8
f 3 8 4
f 4 8 5
f 4 5 1
"""

for target_fmt in ["stl", "step"]:
    url = f"https://api.zoo.dev/file/conversion/obj/{target_fmt}"
    req = urllib.request.Request(
        url,
        data=obj_data.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InterfaceForge/1.0",
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        res_json = json.loads(resp.read().decode("utf-8"))
        outputs = res_json.get("outputs", {})
        for fname, b64val in outputs.items():
            pad = len(b64val) % 4
            if pad:
                b64val += "=" * (4 - pad)
            decoded = base64.b64decode(b64val)
            print(f"OBJ -> {target_fmt}: file={fname}, size={len(decoded)} bytes")
            if target_fmt == "stl":
                print("  STL header/start:", decoded[:50])
            else:
                print("  STEP snippet:", decoded.decode('utf-8', errors='ignore')[:300])
    except Exception as e:
        print(f"OBJ -> {target_fmt} ERROR: {e}")
