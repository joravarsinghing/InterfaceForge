# Zoo API Integration Notes

**Status:** Active & Verified (Stage S8.2 Zoo Model Export Alignment)  
**Purpose:** Records technical insights, SDK usage patterns, latency observations, performance benchmarks, and implementation notes across Engine, Agent, and File Format APIs.

---

## 1. Engine API WebSocket Protocol (`/ws/modeling/commands`)

- **Gateway URL:** `wss://api.zoo.dev/ws/modeling/commands`
- **Authentication:** HTTP Bearer token header (`Authorization: Bearer <token>`).
- **Request Framing:** Each frame must be wrapped as a `WebSocketRequest` JSON object with `"type": "modeling_cmd_req"`, `"cmd_id": "<uuid>"`, and `"cmd": { ... }`.
- **Response Framing:** Engine emits responses with `"resp": {"type": "modeling", "data": {"modeling_response": { ... }}}`.
- **Required Parameters:**
  - `make_plane` requires `"clobber": false`, `"origin"`, `"size"`, `"x_axis"`, `"y_axis"`.
  - `set_scene_units` requires `"unit": "mm"`.
  - `take_snapshot` returns PNG image data in `data.contents`.

---

## 2. Latency Benchmarks & Performance Metrics

| Case Name | Execution Duration | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Minimal Cube** | 2.21s | SUCCEEDED | Initial WebSocket connection handshake + execution |
| **Simple Plate** | 1.93s | SUCCEEDED | Extruded rectangular geometry |
| **Circular Coaxial Adapter** | 2.03s | SUCCEEDED | Two concentric circular profiles |
| **Circular Offset Adapter** | 2.02s | SUCCEEDED | Offset circular center axes |
| **Limited Angle Adapter** | 2.02s | SUCCEEDED | Inclined plane construction |
| **Dissimilar Profile Adapter** | 2.11s | SUCCEEDED | Circle to rounded rectangle transition |

Average live execution latency: **~2.05 seconds**.

---

## 3. Security & Token Protection Rules

- Credentials loaded exclusively from `backend/.env`.
- Secrets redacted in all exception messages via `redact_secrets()`.
- Explicit safety gates enforce `ENGINE_PROVIDER=zoo` / `EXPORT_PROVIDER=zoo` and `RUN_ZOO_LIVE_EXPORTS=1`.

---

## 4. File Format API REST Protocol (`/file/conversion/{src_format}/{output_format}`)

- **REST Endpoint:** `POST https://api.zoo.dev/file/conversion/{src_format}/{output_format}`
- **Authentication:** `Authorization: Bearer <token>` header.
- **Headers:** `User-Agent: InterfaceForge/1.0` (required to bypass Cloudflare bot protection headers), `Content-Type: application/octet-stream`.
- **Request Payload:** Raw binary or string CAD model payload (`application/octet-stream`).
- **Response Format:** JSON object containing `status: "completed"` and `outputs: { "<filename>": "<base64_string>" }`.
- **Base64 Decoding:** Output payloads are base64 encoded strings; missing padding is restored prior to `base64.b64decode()`.

### Live File Format API Real Geometry Benchmarks (Stage S8.1 Audit)

- **Input Variant Support:** `POST /file/conversion/{src_format}/{output_format}` accepts CAD formats including `obj`, `step`, `stl`, `acis`, `catia`, `creo`, `fbx`, `gltf`, `inventor`, `nx`, `parasolid`, `ply`, `points`, `sldprt`.
- **Payload Conversion:** Converting Wavefront OBJ (`obj`) model geometry payloads to `stl` and `step` returns full 3D CAD topologies (32-128 triangles for STL, 332-1292 entities for STEP).

| Test Case | Format | Latency | Output Size | Facets / Entities | Hash (short) | Geometry Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Simple Plate** | STL | 1.28s | 4,843 B | 32 facets | `a1e7bde4218d` | **VALID REAL GEOMETRY** |
| **Simple Plate** | STEP | 1.16s | 15,524 B | 332 entities | `36113b4096d7` | **VALID REAL GEOMETRY** |
| **Circular Coaxial Adapter** | STL | 1.20s | 21,185 B | 128 facets | `9790095122d7` | **VALID REAL GEOMETRY** |
| **Circular Coaxial Adapter** | STEP | 1.42s | 62,332 B | 1,292 entities | `3733f8466e65` | **VALID REAL GEOMETRY** |
| **Circular Offset Adapter** | STL | 1.14s | 21,196 B | 128 facets | `137e88be57b1` | **VALID REAL GEOMETRY** |
| **Circular Offset Adapter** | STEP | 1.33s | 62,419 B | 1,292 entities | `a7ed551d2e85` | **VALID REAL GEOMETRY** |
| **Limited-Angle Adapter** | STL | 1.15s | 22,907 B | 128 facets | `20bff4ee9d30` | **VALID REAL GEOMETRY** |
| **Limited-Angle Adapter** | STEP | 1.32s | 64,402 B | 1,292 entities | `f8fefb8a3826` | **VALID REAL GEOMETRY** |

Average live conversion latency: **~1.25 seconds**.

---

## 5. Zoo Engine WebSocket Loft & Boolean Subtraction Schema (Stage S8.4)

In Stage S8.4, native B-Rep geometry construction over WebSocket (`wss://api.zoo.dev/ws/modeling/commands`) was updated to execute native `loft` and `boolean_subtract` commands:

1. **Loft Command Schema:**
   ```json
   {
     "type": "loft",
     "section_ids": ["<path_uuid_a>", "<path_uuid_b>"],
     "v_degree": 1,
     "bez_approximate_rational": false,
     "tolerance": 0.001
   }
   ```
   - **Response Payload:** `{"resp": {"type": "modeling", "data": {"modeling_response": {"type": "loft", "data": {"solid_id": "<solid_uuid>"}}}}}`.

2. **Boolean Subtraction Command Schema:**
   ```json
   {
     "type": "boolean_subtract",
     "target_ids": ["<outer_solid_uuid>"],
     "tool_ids": ["<inner_void_solid_uuid>"],
     "tolerance": 0.001
   }
   ```
   - **Response Payload:** `{"resp": {"type": "modeling", "data": {"modeling_response": {"type": "boolean_subtract", "data": {}}}}}`.


## 6. 2026-07-29 Live Export Blocker: Boolean Subtraction Export

During the Day 1 AM P0 golden path proof, InterfaceForge successfully analyzed, calibrated, approved, compiled KCL, and generated a current live Zoo model for a circle-to-rounded-rectangle adapter. The model revision stored a live Zoo model id and matching KCL hash.

Live STL and STEP export then failed during the Zoo-native WebSocket export construction after `loft` and `boolean_subtract` with the normalized error:

```text
IF-EXPORT-001: Zoo-native export failed for 'stl'/'step': ZOO_ENGINE_ERROR: The Zoo engine cannot handle this 3D subtraction yet. Please report this as an issue
```

KCL export succeeded from the stored KCL artifact. STL/STEP were not replaced with mock or local geometry output for proof evidence.


---

## 7. 2026-07-29 Authoritative KCL Export Route Diagnostic

Official Zoo documentation describes KCL execution/export through the `zoo-kcl` Python package and the `zoo kcl export` CLI. The safest InterfaceForge export architecture is to export from the exact stored KCL for the current model revision and verify the KCL SHA-256 against the revision hash before writing STL/STEP artifacts.

Local diagnostic results in the current backend environment:

```text
zoo_token_configured=False
kcl_package=False
zoo --version -> command not found
pip install zoo-kcl -> available releases require Python >=3.11
```

Because the backend currently declares Python >=3.10,<3.11, live KCL-native STL/STEP export cannot be proven in this venv without a runtime/tooling change. No local OBJ fallback or second WebSocket reconstruction is acceptable proof for live export.

## 6. Live KCL Warnings and Boolean Failure (2026-08-02)

- Zoo KCL identifiers use lowerCamelCase (`sketchOuter0`, `outerSurface`, and `adapterModel`) for Zoo compatibility.
- Live KCL execution reports `The Zoo engine cannot handle this 3D subtraction yet` for the outer/inner loft Boolean. The primary compiler path is therefore the surface-shell construction: outer and inner surface lofts plus explicit bottom/top rim surfaces joined with `joinSurfaces()`.
- The compiler-side parser/mock executor passing is not evidence of live Zoo boolean success.