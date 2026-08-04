# InterfaceForge API Usage

This is the application API contract. There are 46 active application routes: 38 project routes, 6 generation routes, and 2 health/readiness routes. FastAPI `/docs` and `/redoc` are framework-generated and excluded. Project routes require `X-Project-Token` unless explicitly noted. Success responses use `{ "success": true, "data": ... }`; API errors use `{ "success": false, "error": { "id", "message", "details", "recovery_steps" } }`.

## Recommended workflow routes

### Health and project

| Method | Full path | Request | Response/side effects and prerequisites |
|---|---|---|---|
| GET | `/health` | None | Health envelope; public. |
| GET | `/ready` | None | Readiness envelope; public. |
| POST | `/api/projects` | Optional `ProjectCreateRequest`: `{ "provider_mode": "mock" | "live" }` | `ProjectCreateResponse` with project ID/token, provider mode, schema version, and state. Live mode requires backend Zoo credentials; `IF-PROVIDER-409` otherwise. |
| GET | `/api/projects/{project_id}` | Token | Full `Project` JSON. `IF-PROJECT-404` or `IF-AUTH-401`. |
| PATCH | `/api/projects/{project_id}` | Optional `state`, `connection`, `manufacturing` | Updated `Project`; upstream changes may increment schema revision and stale the model. |
| GET | `/api/projects/provider-mode` | None | Default provider capability status; public. |
| PATCH | `/api/projects/provider-mode` | `{ "provider_mode": "mock" | "live" }` | Capability status; live unavailable returns `IF-PROVIDER-409`. |
| GET | `/api/projects/{project_id}/provider-mode` | Token | Project provider status without credentials. |
| PATCH | `/api/projects/{project_id}/provider-mode` | `{ "provider_mode": "mock" | "live" }` | Updated project and provider status; live unavailable returns `IF-PROVIDER-409`. |

### Upload, analysis, calibration, and approval

| Method | Full path | Request | Response/side effects and prerequisites |
|---|---|---|---|
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/upload` | Multipart `file`; optional `known_measurement_type`, `known_measurement_value`, `known_measurement_unit` | `UploadResponseData` plus interface preparation data. Stores an artifact and validates the image. Invalid files use upload/analysis errors. |
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/mark-uploaded` | Query/form `source_image_ref` | Updated `Project`; token required. |
| GET | `/api/projects/{project_id}/interfaces/{interface_id}/image` | `X-Project-Token` or `?token=` | Source image bytes. |
| GET | `/api/projects/{project_id}/interfaces/{interface_id}/cleaned_image` | Header or query token | Cleaned image bytes. |
| GET | `/api/projects/{project_id}/interfaces/{interface_id}/analysis_image` | Header or query token | Exact OpenCV analysis image bytes. |
| GET | `/api/projects/{project_id}/interfaces/{interface_id}/trace_svg` | Header or query token | Vector trace bytes. |
| GET | `/api/projects/{project_id}/interfaces/{interface_id}/overlay_svg` | Header or query token | Source/trace overlay bytes. |
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/analyze` | Optional query `provider=opencv|mock|gemini` | `AnalysisResult`; invokes the selected analysis provider. OpenCV is the deterministic path; Gemini is optional guidance. |
| PATCH | `/api/projects/{project_id}/interfaces/{interface_id}` | `InterfacePatchRequest` | Updated `Project`; editing profile data clears approval and downstream current state. |
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/scale/snap` | `{ "point": { "x": number, "y": number } }` | `ScaleSnapResponse` with snapped point, pixel distance, and feature ID. Requires a trace. |
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/scale/calibrate` | `{ "point_a": Point2D, "point_b": Point2D, "real_distance_mm": number, "confirmed": boolean }` | Updated `Project`; requires distinct valid points and a positive known distance. |
| DELETE | `/api/projects/{project_id}/interfaces/{interface_id}/scale/calibration` | None | Updated `Project`; resets calibration and invalidates approval. |
| POST | `/api/projects/{project_id}/interfaces/{interface_id}/approve` | None | Updated `Project`; requires valid closed profile, confirmed calibration, and review. Interface B also requires Interface A approval. |

### Configuration and deterministic KCL

| Method | Full path | Request | Response/side effects and prerequisites |
|---|---|---|---|
| PUT | `/api/projects/{project_id}/connection` | `ConnectionUpdateRequest`: `mode`, `length_mm`, `offset_x_mm`, `offset_y_mm`, `angle_deg`, `extension_a_mm`, `extension_b_mm` | Updated `Project`; only coaxial/offset are active submission modes. Both profiles must be approved. Legacy angle values are compatibility-only and must remain zero. |
| PUT | `/api/projects/{project_id}/manufacturing` | `ManufacturingUpdateRequest`: `process`, `material`, `wall_thickness_mm`, `clearance_a_mm`, `clearance_b_mm` | Updated `Project`; may stale model/exports. |
| PUT | `/api/projects/{project_id}/connection-config` | `{ "connection": ConnectionUpdateRequest, "manufacturing": ManufacturingUpdateRequest }` | Atomic updated `Project`; both approvals required. |
| POST | `/api/projects/{project_id}/validate-connection` | Optional `ConnectionConfigRequest` | Validation result with issues and, when valid, preview `LoftPlan`. |
| GET | `/api/projects/{project_id}/kcl/readiness` | Token | Readiness result; does not compile. |
| POST | `/api/projects/{project_id}/kcl/compile` | Token | `KCLCompileResult`; deterministic KCL 2.0 artifact; does not execute Zoo. |
| GET | `/api/projects/{project_id}/kcl` | Token | Current KCL artifact data; current model/artifact required. |

Example configuration:

```json
{
  "connection": {"mode":"offset","length_mm":40,"offset_x_mm":10,"offset_y_mm":0,"angle_deg":0,"extension_a_mm":0,"extension_b_mm":0},
  "manufacturing": {"process":"fdm","material":"PETG","wall_thickness_mm":2.4,"clearance_a_mm":0.3,"clearance_b_mm":0.1}
}
```

### Generation and export

| Method | Full path | Request | Response/side effects and prerequisites |
|---|---|---|---|
| POST | `/api/projects/{project_id}/generation/start` | Optional `GenerationJobRequest` | Creates a generation job and draft model revision, validates readiness, compiles KCL, and invokes selected Engine provider. |
| GET | `/api/projects/{project_id}/generation/active` | Token | Active `GenerationJob` or `null`; supports restore after refresh. |
| GET | `/api/projects/{project_id}/generation/{job_id}` | Token | `GenerationJob` status/progress. |
| POST | `/api/projects/{project_id}/generation/{job_id}/cancel` | Token | Cancelled job; restores last-known-good model state. |
| POST | `/api/projects/{project_id}/generation/{job_id}/retry` | Optional `GenerationJobRequest` | New generation attempt for failed/cancelled job. |
| GET | `/api/projects/{project_id}/generation/{job_id}/preview` | Token | `PreviewMetadata`; successful preview required. |
| POST | `/api/projects/{project_id}/exports/generate` | Optional `{ "formats": ["stl", "kcl"], "mock_scenario": null }` | `ExportStatusResponse`; current model required. STEP fields remain compatibility-only and are not submission output. |
| GET | `/api/projects/{project_id}/exports/status` | Token | Per-format `FormatExportDetail`, model revision, schema revision, and status. |
| POST | `/api/projects/{project_id}/exports/{format_name}/retry` | Token | Retries one format. |
| GET | `/api/projects/{project_id}/exports/{format_name}/download` | Header or `?token=` | Current STL/KCL artifact bytes; stale/missing artifacts are refused. |

Generation and export errors include `IF-PREREQ-400`, `IF-KCL-*`, `IF-JOB-409`, `IF-JOB-404`, `IF-STALE-409`, `IF-EXPORT-002`, `IF-EXPORT-003`, `IF-EXPORT-005`, and provider-specific IDs.

### Agent revisions

| Method | Full path | Request | Response/side effects and prerequisites |
|---|---|---|---|
| POST | `/api/projects/{project_id}/revision/propose` | `{ "prompt": string, "provider": "zoo" | "mock" }` | `AgentProposalResult` with structured `ParameterChange` items and validation errors. Default provider is Zoo; mock is explicit offline/test mode. |
| POST | `/api/projects/{project_id}/revision/confirm` | `{ "changes": [ParameterChange] }`, optional `?mock_scenario=` | Updated `Project` and `job: null`. Applies only server-validated changes, increments schema revision, and marks the model stale. It does not start generation. |

The allowlist contains exactly eight fields: connection.length_mm, connection.extension_a_mm, connection.extension_b_mm, connection.offset_x_mm, connection.offset_y_mm, manufacturing.wall_thickness_mm, manufacturing.clearance_a_mm, and manufacturing.clearance_b_mm. Profiles, contours, provider settings, and KCL text are not editable by Agent proposals.

## Compatibility-only routes

These routes remain declared for older/manual lifecycle tests and are not the recommended frontend generation workflow:

- `POST /api/projects/{project_id}/model/start`
- `POST /api/projects/{project_id}/model/succeed`
- `POST /api/projects/{project_id}/model/fail`
- `POST /api/projects/{project_id}/export/start`
- `POST /api/projects/{project_id}/export/complete`

They mutate legacy model/export state and require the same project token. New work should use generation jobs and current export routes.

## Authorization and providers

Project tokens are issued at creation and accepted through `X-Project-Token`; browser binary downloads additionally accept `?token=`. Zoo credentials are backend-only. `VITE_BACKEND_URL` connects the frontend to the backend. `ENGINE_PROVIDER`, `EXPORT_PROVIDER`, and project `provider_mode` select mock/live behavior; OpenCV is the deterministic analysis provider, while Gemini is optional guidance. No silent live-to-mock Agent fallback is claimed.
