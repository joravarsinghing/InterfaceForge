import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv('backend/.env')
token = os.getenv('ZOO_API_TOKEN')

headers = {
    "Authorization": f"Bearer {token}",
    "User-Agent": "InterfaceForge/1.0",
    "Content-Type": "application/json",
}

endpoints = [
    ("POST /kcl/compile", "https://api.zoo.dev/kcl/compile"),
    ("POST /kcl/execute", "https://api.zoo.dev/kcl/execute"),
    ("POST /kcl/export", "https://api.zoo.dev/kcl/export"),
    ("POST /kcl/convert", "https://api.zoo.dev/kcl/convert"),
    ("POST /modeling/kcl", "https://api.zoo.dev/modeling/kcl"),
    ("POST /file/conversion/kcl/stl", "https://api.zoo.dev/file/conversion/kcl/stl"),
    ("POST /file/conversion/kcl/step", "https://api.zoo.dev/file/conversion/kcl/step"),
    ("GET /kcl", "https://api.zoo.dev/kcl"),
    ("GET /file/conversion/formats", "https://api.zoo.dev/file/conversion/formats"),
]

for name, url in endpoints:
    try:
        data = json.dumps({"code": "const x = 1"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data if "POST" in name else None,
            headers=headers,
            method="POST" if "POST" in name else "GET"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        res_bytes = resp.read()
        print(f"[OK {resp.status}] {name}: len={len(res_bytes)} body={res_bytes[:200].decode('utf-8', errors='ignore')}")
    except urllib.error.HTTPError as e:
        err_b = e.read().decode('utf-8', errors='ignore')
        print(f"[HTTP {e.code}] {name}: {err_b[:200]}")
    except Exception as ex:
        print(f"[ERR] {name}: {ex}")
