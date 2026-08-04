# InterfaceForge Architecture

InterfaceForge is a modular monolith. The React/TypeScript frontend is deployed to Cloudflare Pages and calls the FastAPI backend deployed to Render through `VITE_BACKEND_URL`. The backend owns authorization, workflow invariants, canonical persistence, image/artifact handling, provider orchestration, deterministic compilation, and export authorization.

```text
Cloudflare Pages frontend
  React workflow, route guards, calibration, review, status, downloads
        | VITE_BACKEND_URL + X-Project-Token
Render FastAPI backend
  routes -> ProjectService / GenerationJobService / AgentService
        |-- SQLite canonical projects and revision lineage
        |-- runtime artifacts: uploads, traces, KCL, previews, exports
        |-- OpenCV analysis and calibration artifacts
        |-- LoftPlan builder -> KCL 2.0 compiler
        |-- EngineProvider: Zoo live or explicit Mock offline
        |-- AgentProvider: Zoo Agent or explicit Mock test provider
        `-- ExportProvider: Zoo-native or explicit Mock provider
```

## Component responsibilities

- Frontend pages enforce the user sequence and `ProtectedRoute`/workflow helpers redirect users to the earliest incomplete step. It never receives Zoo credentials.
- FastAPI routes validate request shapes, require project tokens for project data, and return stable error envelopes.
- `ProjectService` owns canonical project updates, approval gates, calibration, configuration, stale-state transitions, persistence, KCL readiness, and artifact access.
- OpenCV produces deterministic cleaned/analysis images, closed traces, SVG artifacts, and trace diagnostics. Optional Gemini guidance is not the geometry author.
- `LoftPlan` stores normalized, resampled, corresponding outer/inner loops and ordered sections. It is authoritative for preview, KCL, and generated geometry.
- `kcl_compiler.py` emits deterministic KCL 2.0 solid-body code and does not execute providers.
- `GenerationJobService` creates model revisions, executes the selected Engine provider, tracks staged jobs, and preserves last-known-good state on failure.
- `AgentService` validates structured Zoo Agent intent against a six-field allowlist, recalculates trusted values, and requires explicit confirmation.
- Export services verify current revision/KCL lineage and generate active STL/KCL outputs.

## Main data flow

1. Create a project and receive a project token.
2. Upload Interface A/B; runtime image and trace artifacts are stored under the artifact root.
3. Analyze with OpenCV, calibrate with two points plus one known distance, review, and approve each interface.
4. Validate connection/manufacturing settings and preview the resulting LoftPlan.
5. Compile KCL 2.0 from the canonical project and LoftPlan.
6. Start a generation job through the selected Engine provider.
7. Persist model revision metadata, Zoo model ID, KCL hash, preview metadata, and current/last-known-good pointers.
8. Generate and authorize current STL/KCL exports.

## State, lineage, and failure handling

Upstream profile, calibration, connection, or manufacturing changes increment schema revision and mark the model stale. Exports tied to an older model revision are stale and cannot be downloaded as current. A generation attempt creates a draft/generating revision. Success marks it current and updates `last_known_good_model_revision`; failure marks the attempt failed and restores the prior last-known-good revision. Generation jobs can be resumed through active/status routes and retried after failure.

Agent confirmation updates canonical values and returns a stale project with no generation job. The user must explicitly start regeneration. A failed revision never overwrites the previous successful model.

## Security boundaries

Project tokens authorize project and artifact access through `X-Project-Token`; browser binary endpoints additionally accept a token query parameter. Uploaded filenames and artifact paths are handled server-side. Zoo, Gemini, and other provider credentials are environment-backed on the backend only. The frontend receives provider capability status, not secrets. The backend validates Agent proposals and never permits Agent-authored KCL or direct profile-contour changes.

## Storage and deployment

SQLite is the implemented repository and defaults to `artifacts/interfaceforge.db` through `DB_PATH`. Runtime uploads, traces, KCL, previews, and exports use the local artifact directory with path-safety checks. Render filesystem persistence is deployment-dependent; the repository does not claim durable object storage. CORS is configured by `CORS_ORIGINS`. Live provider availability depends on backend credentials and provider settings; Mock providers are explicit offline/test modes, not silent production fallbacks.

## Scope and evidence boundary

Active profiles are circle, rectangle, rounded rectangle, and approved `traced_closed`. Active connections are coaxial and parallel X/Y offset. Angle-based connections, internal cavities, STEP export, and richer CAD features are compatibility/deferred scope. A prior credentialed Zoo Agent flow succeeded, while 17 of 18 Agent attempts timed out or closed during the focused 2026-08-04 audit. The direct live Engine audit timed out before a fresh STL conversion result; transient transport failures are not classified as confirmed Zoo bugs.
