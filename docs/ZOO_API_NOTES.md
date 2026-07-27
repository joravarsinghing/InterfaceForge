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

