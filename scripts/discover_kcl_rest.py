import urllib.request
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.config import settings

def main():
    token = settings.zoo_api_token
    base_url = settings.zoo_api_base_url
    
    endpoints = [
        "/kcl/execute",
        "/kcl/compile",
        "/kcl",
        "/modeling/kcl",
        "/file/kcl",
        "/kcl/export",
        "/kcl/wasm",
        "/kcl/run",
        "/file/conversion/kcl/stl",
        "/file/conversion/kcl/step"
    ]
    
    sample_kcl = "fn cube() { return startSketchOn('XY') |> circle(center=[0,0], radius=10) |> extrude(length=20) } cube()"
    
    for ep in endpoints:
        url = f"{base_url}{ep}"
        req = urllib.request.Request(
            url,
            data=sample_kcl.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "InterfaceForge/1.0",
                "Content-Type": "application/octet-stream"
            },
            method="POST"
        )
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            print(f"[HTTP {resp.status}] {ep} -> {resp.read()[:200]}")
        except urllib.error.HTTPError as e:
            print(f"[HTTP {e.code}] {ep} -> {e.read().decode('utf-8', errors='ignore')[:200]}")
        except Exception as e:
            print(f"[ERR] {ep} -> {e}")

if __name__ == "__main__":
    main()
