# InterfaceForge — Technical Design

**Document status:** Draft v0.1  
**Source documents:** `InterfaceForge_PRD_v0.1.md`, `user_flow.md`, `ascii_wireframes.md`  
**Audience:** Product owner, technical lead, Codex, Antigravity/Gemini, Claude, QA agents, and any implementation agent  
**Purpose:** Define the implementation architecture, contracts, boundaries, operational model, and non-reversible technical decisions for the Zoo API Makeathon MVP

---

# Technical Design

## Context

InterfaceForge is a guided adapter-generation application for users who do not know CAD but can provide two interface images or sketches and a few dimensions.

The product converts:

```text
Two user-approved 2D interface definitions
        +
Connection relationship
        +
Manufacturing parameters
        ↓
Validated canonical design schema
        ↓
Deterministic KCL
        ↓
Zoo Engine execution
        ↓
3D preview and manufacturing exports
```

The primary hero case is a hollow adapter connecting a vacuum hose to a CNC-router dust port. A secondary case is a simple flat camera mounting adapter.

The system must prioritize:

- accessibility over CAD flexibility;
- deterministic geometry over unconstrained AI generation;
- user approval over hidden inference;
- clear recovery over silent failure;
- documented Zoo API use over superficial integration;
- one reliable adapter family over many unstable ones.

The Makeathon build window is short, so the architecture must be modular enough to demonstrate depth without creating unnecessary infrastructure.

---

## Constraints

### Competition constraints

- The project must be created from scratch during the official Makeathon window.
- The public repository must be open source.
- Zoo API use must be meaningful.
- Documentation, bug reporting, technical readability, UI/UX, and creativity are judging criteria.
- API keys and credentials must not be committed.
- The final demo must be reproducible enough for judges to understand.

### Product constraints

- No end-user authentication in MVP.
- No billing, subscriptions, credits, or cloud project accounts.
- Desktop-first UX.
- Two interfaces per project.
- Image-assisted profile extraction is required.
- Each interface requires user review and approval.
- Generated geometry must remain parametric.
- The system produces KCL and STL; STEP is planned but not implemented.
- The user must not need to operate Zoo Design Studio manually.

### Geometry constraints

- Supported profiles:
  - circle;
  - rectangle;
  - rounded rectangle;
  - validated traced closed profile.
- Supported connection modes:
  - coaxial;
  - offset;
  - angle-based connections (not supported in submission).
- Arbitrary freeform solids, assemblies, curved pipe paths, and complex surfacing are out of scope.
- Traced profiles must be normalized before lofting.
- Geometry limits must be conservative and configurable.

### Operational constraints

- Remote Zoo services may be slow or temporarily unavailable.
- The Engine API, Agent API, and File Format API may fail independently.
- Vision analysis may use an external service and must be treated as untrusted input.
- Remote API behavior may change during the competition.
- The system must preserve the last known good model after failed revisions.

### Team constraints

- Solo human developer supported by AI coding agents.
- Python is the strongest implementation language.
- Frontend experience is limited but agent-assisted.
- The design must be readable and enforceable by multiple AI agents.

---

## Proposed architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Browser Client                                                        │
│                                                                       │
│ React/Vite UI                                                         │
│ - Guided workflow                                                     │
│ - Image upload                                                        │
│ - Editable SVG review                                                 │
│ - Connection configuration                                            │
│ - Result viewer                                                       │
│ - Revision and export                                                  │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ HTTPS / JSON / multipart
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│ FastAPI Application                                                   │
│                                                                       │
│ API routes                                                            │
│ Session/project service                                               │
│ Input validation                                                      │
│ Vision adapter                                                        │
│ Profile normalization                                                 │
│ Canonical schema service                                              │
│ Geometry-rule engine                                                  │
│ Deterministic KCL compiler                                             │
│ Zoo Engine client                                                     │
│ Zoo Agent client                                                      │
│ Zoo File Format client                                                │
│ Artifact manager                                                      │
│ Logging / tracing                                                     │
└─────────────┬────────────────┬───────────────────┬────────────────────┘
              │                │                   │
              ▼                ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐
│ Vision provider  │  │ Zoo APIs         │  │ Temporary artifact     │
│                  │  │                  │  │ storage                 │
│ Image parsing    │  │ Engine           │  │                         │
│ OCR/shape hints  │  │ Agent            │  │ Uploads                 │
│ Structured JSON  │  │ File Format      │  │ KCL                     │
└──────────────────┘  └──────────────────┘  │ Exports                 │
                                            │ Logs                    │
                                            └─────────────────────────┘
```

### Architectural style

- Single frontend application.
- Single Python backend application.
- Thin service wrappers around external APIs.
- Canonical design schema as the internal source of truth.
- Deterministic KCL generation as a compiler step.
- Temporary local or ephemeral artifact storage.
- No database required for MVP unless session persistence becomes necessary.

---

## Component responsibilities

### 1. Frontend application

Responsible for:

- guided step navigation;
- image upload;
- image-quality guidance;
- source image preview;
- SVG profile review;
- editable dimension fields;
- provenance and confidence indicators;
- connection-mode selection;
- connection parameter controls;
- generation progress;
- result viewer;
- structured revision;
- natural-language revision;
- export selection;
- user-facing errors and recovery.

Must not:

- contain Zoo or AI secrets;
- call privileged external APIs directly;
- generate final KCL independently;
- silently modify approved dimensions;
- treat client-side validation as sufficient.

### 2. API layer

Responsible for:

- request parsing;
- input validation;
- response normalization;
- route-level error mapping;
- request IDs;
- service orchestration;
- preventing unauthorized field updates.

### 3. Project/session service

Responsible for:

- temporary project identity;
- workflow state;
- approved interfaces;
- canonical schema versions;
- last-known-good model;
- stale/current artifact status;
- short-lived project recovery where implemented.

### 4. Vision adapter

Responsible for:

- sending image/sketch input to a vision-capable model;
- requesting structured shape/dimension output;
- returning confidence and provenance candidates;
- rejecting malformed responses;
- isolating provider-specific formats.

Must not produce final KCL.

### 5. Profile normalization service

Responsible for:

- validating contour closure;
- removing duplicate points;
- smoothing noise within strict limits;
- normalizing winding direction;
- resampling points;
- aligning start points;
- detecting self-intersection;
- classifying supported shapes;
- producing a clean SVG-compatible profile.

### 6. Canonical schema service

Responsible for:

- creating and versioning the project design schema;
- recording dimension provenance;
- storing approval state;
- applying validated changes;
- comparing schema versions;
- marking models stale.

### 7. Geometry-rule engine

Responsible for:

- profile compatibility checks;
- wall-thickness rules;
- clearance ranges;
- minimum length;
- angle limits;
- offset-to-length limits;
- self-intersection risk;
- traced-profile complexity limits;
- manufacturing warnings.

### 8. KCL compiler

Responsible for:

- converting canonical schema into deterministic KCL;
- using tested templates/functions;
- stable naming;
- explicit units;
- comments and readable structure;
- reproducible output;
- rejecting unsupported combinations before Zoo execution.

### 9. Zoo Engine client

Responsible for:

- authentication with server-held credentials;
- model execution;
- snapshots or preview artifacts;
- geometry result capture;
- timeout/retry policy;
- normalized engine errors.

### 10. Zoo Agent client

Responsible for:

- converting natural-language revisions into structured parameter patches;
- explanation and clarification;
- enforcing JSON schema;
- rejecting non-allowlisted modifications.

Must not directly replace full KCL.

### 11. Zoo File Format client

Responsible for:

- export conversion;
- STL generation or verification;
- volume analysis where reliable;
- per-format status and error normalization.

### 12. Artifact manager

Responsible for:

- uploaded images;
- generated SVG;
- canonical JSON;
- KCL source;
- previews;
- export files;
- cleanup;
- safe filenames;
- temporary download links.

### 13. Observability layer

Responsible for:

- structured logs;
- request IDs;
- API latency;
- error IDs;
- generation stage timing;
- known-good fixture results;
- sensitive-data redaction.

---

## Trust boundaries

```text
Untrusted user input
    - uploaded images
    - dimensions
    - profile edits
    - natural-language prompts
        │
        ▼
Application validation boundary
        │
        ├── Vision model output: untrusted
        ├── Agent API output: untrusted
        └── External API errors/results: validated before use
        │
        ▼
Canonical schema boundary
        │
        ▼
Deterministic KCL compiler
        │
        ▼
Zoo execution boundary
        │
        ▼
Validated artifacts
```

### Trust rules

- User inputs are untrusted.
- Vision output is advisory until validated and user-approved.
- Agent output is never directly executable.
- KCL is generated only from validated canonical data.
- External export artifacts must be checked for expected format and non-zero size.
- API keys remain server-side.
- User-uploaded files never become code paths or executable filenames.
- Model success does not imply manufacturability certification.

---

## Data model

### Project

```json
{
  "project_id": "uuid",
  "schema_version": "0.1",
  "state": "interfaces_approved",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "interface_a": {},
  "interface_b": {},
  "connection": {},
  "manufacturing": {},
  "current_schema_revision": 3,
  "current_model_revision": 2,
  "last_known_good_model_revision": 2
}
```

### Interface definition

```json
{
  "id": "interface_a",
  "source_image_ref": "artifact-id",
  "profile_type": "circle",
  "profile_points": [],
  "center": {"x": 0.0, "y": 0.0},
  "dimensions": [
    {
      "id": "outer_diameter",
      "label": "Outer diameter",
      "value": 34.5,
      "unit": "mm",
      "provenance": "user_entered",
      "confidence": 1.0,
      "critical": true
    }
  ],
  "validation": {
    "is_closed": true,
    "self_intersects": false,
    "warnings": []
  },
  "approved": true,
  "approved_at": "ISO-8601"
}
```

### Connection definition

```json
{
  "mode": "offset",
  "length_mm": 110.0,
  "offset_x_mm": 20.0,
  "offset_y_mm": 0.0,
  "angle_deg": 0.0
}
```

### Manufacturing definition

```json
{
  "process": "fdm",
  "material": "PETG",
  "wall_thickness_mm": 2.4,
  "clearance_a_mm": 0.3,
  "clearance_b_mm": 0.1
}
```

### Model revision

```json
{
  "model_revision": 2,
  "schema_revision": 3,
  "status": "current",
  "kcl_artifact_ref": "artifact-id",
  "preview_artifact_ref": "artifact-id",
  "exports": {
    "stl": "artifact-id",
    "step": "artifact-id"
  },
  "volume_cm3": 42.8,
  "warnings": [],
  "generated_at": "ISO-8601"
}
```

### Error record

```json
{
  "error_id": "IF-ENGINE-004",
  "request_id": "uuid",
  "category": "engine",
  "user_message": "The adapter could not be generated at the selected angle.",
  "recommended_action": "Increase transition length or reduce angle.",
  "technical_message": "redacted technical detail",
  "retryable": true,
  "timestamp": "ISO-8601"
}
```

---

## API contracts

All API responses should use a consistent envelope.

### Success envelope

```json
{
  "ok": true,
  "request_id": "uuid",
  "data": {}
}
```

### Error envelope

```json
{
  "ok": false,
  "request_id": "uuid",
  "error": {
    "id": "IF-PROFILE-004",
    "category": "profile_validation",
    "message": "The detected contour crosses itself.",
    "recommended_action": "Edit the profile or upload a clearer image.",
    "retryable": false,
    "field_errors": []
  }
}
```

### Core endpoints

#### `POST /api/projects`

Creates a temporary project.

Response:

```json
{
  "ok": true,
  "data": {
    "project_id": "uuid",
    "state": "new"
  }
}
```

#### `POST /api/projects/{project_id}/interfaces/{interface_id}/upload`

Multipart upload for Interface A or B.

Returns:

- artifact reference;
- basic file metadata;
- analysis job or immediate processing status.

#### `POST /api/projects/{project_id}/interfaces/{interface_id}/analyze`

Requests profile extraction.

Response:

```json
{
  "ok": true,
  "data": {
    "profile_type": "rounded_rectangle",
    "profile_points": [],
    "dimensions": [],
    "confidence": 0.82,
    "warnings": []
  }
}
```

#### `PATCH /api/projects/{project_id}/interfaces/{interface_id}`

Updates dimensions/profile selection.

Only allowlisted fields may be modified.

#### `POST /api/projects/{project_id}/interfaces/{interface_id}/approve`

Approves a validated interface.

Must reject unresolved critical values.

#### `PUT /api/projects/{project_id}/connection`

Stores and validates connection configuration.

#### `POST /api/projects/{project_id}/generate`

Creates a new schema/model revision and starts generation.

May return synchronous completion or job status depending on final implementation.

#### `GET /api/projects/{project_id}/generation/{job_id}`

Returns staged generation status.

#### `POST /api/projects/{project_id}/revisions/interpret`

Converts natural language into a proposed parameter patch.

#### `POST /api/projects/{project_id}/revisions/apply`

Validates and applies an approved patch.

#### `POST /api/projects/{project_id}/exports`

Requests selected formats.

#### `GET /api/projects/{project_id}/artifacts/{artifact_id}`

Returns a short-lived download or file response.

### Contract rules

- All units in backend contracts are explicit.
- API never accepts raw KCL from the browser.
- Profile approval requires server-side validation.
- Agent output is not exposed as executable code.
- Export requests require current model state.
- Stale model exports return a conflict error.

---

## Authentication and authorization

### End-user authentication

No end-user authentication in MVP.

Projects are temporary and identified by an unguessable project/session token.

### Backend authorization

- Zoo and vision credentials are stored only on the server.
- The frontend never receives provider secrets.
- A project token may be required for access to project-specific routes.
- Artifact download links should be short-lived or scoped to the session.
- Direct object references must be validated against the active project.

### Service credentials

- Environment variables or deployment-secret manager.
- Separate keys where providers support them.
- Keys must be redacted from logs and exception output.
- `.env.example` contains names only.

### Authorization failure behavior

- Users are never redirected to login.
- Invalid project token returns a project-expired or unavailable message.
- Invalid provider credentials surface as service unavailability.

---

## Validation strategy

Validation occurs in layers.

### 1. Client validation

Used for fast feedback:

- required fields;
- numeric format;
- obvious bounds;
- file type and size;
- step prerequisites.

Client validation is never authoritative.

### 2. API schema validation

Pydantic models enforce:

- types;
- units;
- enums;
- ranges;
- required properties;
- version compatibility.

### 3. Profile validation

Checks:

- closure;
- duplicate points;
- self-intersection;
- supported complexity;
- valid scale;
- minimum dimensions;
- shape-specific requirements.

### 4. Design-rule validation

Checks:

- approved profiles;
- connection compatibility;
- wall thickness;
- clearance;
- angle;
- offset;
- minimum length;
- manufacturing constraints.

### 5. Agent patch validation

Checks:

- JSON schema;
- allowlisted paths;
- no profile approval bypass;
- no unit ambiguity;
- no out-of-range values;
- no hidden destructive change.

### 6. KCL preflight

Checks:

- required template exists;
- stable variable names;
- explicit units;
- finite values;
- supported topology;
- no empty profile.

### 7. Post-generation validation

Where supported:

- non-empty model;
- expected body count;
- expected bounding range;
- export artifact exists;
- export artifact size > 0;
- model volume is plausible.

---

## Error model

### Error categories

- `INPUT`
- `IMAGE`
- `PROFILE`
- `DIMENSION`
- `DESIGN_RULE`
- `KCL`
- `ENGINE`
- `AGENT`
- `FILE_FORMAT`
- `EXPORT`
- `SESSION`
- `NETWORK`
- `INTERNAL`

### Error ID format

```text
IF-{CATEGORY}-{NUMBER}
```

Examples:

- `IF-IMAGE-002`
- `IF-PROFILE-004`
- `IF-ENGINE-001`
- `IF-EXPORT-003`

### Error properties

Each error must define:

- user-facing message;
- recommended action;
- retryable boolean;
- HTTP status;
- internal technical detail;
- request ID;
- safe log context.

### Recovery rules

- User-input errors preserve all valid fields.
- Failed revision preserves last known good model.
- Service timeout allows retry.
- Malformed Agent output is never applied.
- Stale model cannot be exported.
- Unknown errors do not expose raw stack traces.

---

## State management

### Frontend state

Recommended split:

- URL/router state:
  - current step;
  - project ID;
  - interface ID.
- server state:
  - project;
  - analysis results;
  - model status;
  - export status.
- local UI state:
  - unsaved field edits;
  - open dialogs;
  - viewport controls.

A server-state library such as TanStack Query is recommended but not mandatory.

### Backend state

Preferred MVP options:

1. in-memory session store plus artifact directory for local demo;
2. SQLite for reliable project recovery;
3. Redis only if deployed infrastructure already supports it.

### Recommended decision

Use SQLite or a lightweight persistent store if implementation time permits. Pure in-memory state risks losing the demo project on restart.

### State invariants

- Interface approval is explicit.
- Editing approved data increments schema revision.
- Editing invalidates current model.
- Successful generation creates model revision.
- Failed generation does not replace last known good.
- Export references exact model revision.

---

## Background processing

### Candidate background tasks

- image analysis;
- profile normalization;
- Zoo geometry generation;
- preview rendering;
- export conversion;
- volume analysis.

### MVP approach

Use simple application-managed jobs rather than a distributed queue unless runtime behavior requires more.

Possible design:

- create job record;
- run task in FastAPI background task or controlled worker;
- expose polling endpoint;
- store stage and progress;
- prevent duplicate active generation per project.

### Job states

```text
queued
running
succeeded
failed
cancel_requested
cancelled
```

### Job requirements

- idempotency key per generation request;
- timeout per provider;
- stage-level logging;
- safe retry;
- no concurrent model writes for same project;
- last known good artifact preserved.

---

## Caching

### What may be cached

- normalized profile from identical image hash;
- stable sample projects;
- generated KCL for identical canonical schema hash;
- export results for identical model revision;
- static help content;
- provider capability metadata.

### What should not be broadly cached

- raw uploads across users;
- secrets;
- low-confidence inference;
- user-specific project tokens;
- failed Agent responses.

### Cache key strategy

Use deterministic hashes of:

- schema version;
- canonical JSON;
- generation template version;
- export format;
- provider options.

### MVP recommendation

Implement only:

- generated artifact reuse by schema hash;
- export reuse by model revision;
- browser caching for static assets.

Avoid building a complex distributed cache.

---

## Observability

### Structured logging

Each log entry should include where relevant:

- timestamp;
- request ID;
- project ID;
- schema revision;
- model revision;
- job ID;
- operation;
- stage;
- duration;
- provider;
- result;
- normalized error ID.

### Metrics

Track:

- image-analysis success rate;
- profile approval rate;
- generation success rate;
- export success rate;
- average generation duration;
- Agent patch validation failure rate;
- provider timeout count;
- physical validation result for hero case.

### Tracing

At minimum, preserve request correlation across:

```text
frontend request
→ backend request
→ vision / Zoo call
→ artifact creation
→ response
```

### Bug documentation

Every Zoo issue should record:

- date/time;
- endpoint or workflow;
- request summary;
- expected result;
- actual result;
- reproduction steps;
- error details;
- screenshot/artifact;
- workaround;
- severity;
- report status.

### Privacy

Do not log:

- raw API keys;
- full user images by default;
- unnecessary prompt content;
- provider authorization headers.

---

## Testing strategy

### Unit tests

Cover:

- Pydantic schemas;
- dimension provenance;
- unit conversion;
- profile closure;
- duplicate-point removal;
- winding normalization;
- self-intersection detection;
- profile resampling;
- geometry limits;
- clearance rules;
- wall-thickness rules;
- Agent patch allowlist;
- KCL emitter;
- error mapping.

### Contract tests

Mock and validate:

- vision response schema;
- Engine client response;
- Agent response;
- File Format response;
- error normalization.

### Integration tests

Cover:

- upload → analysis → approval;
- two approved profiles → connection validation;
- canonical schema → KCL;
- KCL → Engine result;
- model → export;
- revision → new model;
- failed revision → previous model retained.

### End-to-end tests

Known-good flows:

1. coaxial circular reducer;
2. offset circular adapter;
3. angle-based connections (not supported in submission) circular adapter;
4. rectangular transition;
5. simple flat mounting plate.

### Visual tests

- SVG profile snapshots;
- critical UI states;
- result preview screenshots where stable.

### Physical test

Hero vacuum adapter:

- generate;
- export;
- slice;
- print;
- fit-test;
- record measured mismatch;
- revise if required;
- document result.

### Manual accessibility test

- keyboard-only workflow;
- focus order;
- error focus;
- live-region behavior;
- color-independent provenance;
- zoom alternatives.

---

## Deployment model

### Recommended MVP deployment

- Frontend: static hosting.
- Backend: single containerized FastAPI service.
- Persistent storage: SQLite volume or managed lightweight database.
- Artifact storage:
  - local persistent volume for demo deployment, or
  - object storage if readily available.
- Secrets: deployment environment variables.
- HTTPS required.

### Local development

```text
frontend/
backend/
docs/
tests/
artifacts/   # gitignored
```

Commands should be documented for Windows.

### Environment separation

- local;
- test;
- production/demo.

Use distinct API keys if available.

### Deployment priorities

- simple;
- reproducible;
- low operational risk;
- no unnecessary cloud complexity;
- easy judge setup.

---

## Migration strategy

The MVP begins with schema version `0.1`.

### Schema versioning

Every canonical project includes:

```json
{
  "schema_version": "0.1"
}
```

### Migration rules

- Never silently reinterpret old fields.
- Add migration functions when schema changes.
- Store original canonical JSON with each model revision.
- KCL template version should be recorded.
- Existing generated artifacts remain linked to their original schema/template version.

### MVP migration needs

Likely migrations:

- adding profile metadata;
- adding manufacturing presets;
- changing clearance representation;
- changing model-revision structure.

### Backward compatibility

Only required for projects created during active development if persistence is implemented.

No public long-term compatibility guarantee in MVP.

---

## Security analysis

### Threats

#### Malicious uploads

Risks:

- oversized files;
- malformed images;
- decompression bombs;
- unsupported file content;
- filename traversal.

Mitigations:

- file size limit;
- MIME verification;
- image decoding in controlled library;
- generated filenames;
- no direct execution;
- temporary storage;
- cleanup.

#### Prompt injection through images or text

Risks:

- image contains instructions to external model;
- natural-language prompt tries to bypass constraints.

Mitigations:

- fixed system prompts;
- structured output schema;
- treat model output as untrusted;
- allowlisted Agent patch fields;
- no secret exposure to model;
- no tool execution from model output.

#### API-key exposure

Mitigations:

- server-side only;
- environment secrets;
- redaction;
- no frontend provider calls;
- repository scanning.

#### Insecure direct object reference

Mitigations:

- unguessable project tokens;
- project-artifact ownership checks;
- short-lived download links;
- no sequential public IDs.

#### Denial of service / API exhaustion

Mitigations:

- upload limits;
- per-project active-job limit;
- request throttling if needed;
- generation idempotency;
- timeout;
- no automatic infinite retry.

#### Unsafe generated geometry

Mitigations:

- clear disclaimer;
- manufacturability warnings;
- no certification claims;
- user approval;
- physical test for hero model;
- conservative rules.

#### Privacy leakage

Mitigations:

- ephemeral uploads;
- minimal logs;
- explicit external-service notice;
- cleanup policy;
- no public artifact URLs by default.

---

## Accessibility implementation

### Semantic structure

- single H1;
- landmarks for header, navigation, main, footer;
- labeled workflow navigation;
- proper form grouping.

### Form behavior

- visible labels;
- units associated with numeric inputs;
- error summary and field-level errors;
- no placeholder-only instructions;
- keyboard-operable controls.

### SVG profile editor

- all dimensions mirrored in HTML fields;
- profile description in text;
- zoom controls;
- no drag-only requirement;
- provenance labels as text/icons.

### 3D viewer

- textual model summary;
- keyboard-accessible controls where available;
- fit/reset controls;
- reduced-motion consideration;
- no critical validation shown only in 3D.

### Dynamic states

- polite live region for progress;
- assertive region for critical errors;
- focus moves to error/proposal heading when appropriate;
- dialog focus trapping and restoration.

### Color and contrast

- provenance never color-only;
- warnings include icon and text;
- contrast checked before final polish;
- focus indicators visible.

---

## Alternatives considered

### 1. Full browser CAD editor

Rejected because:

- duplicates Zoo Design Studio;
- exceeds Makeathon scope;
- creates high UX and geometry complexity;
- conflicts with accessibility-first product direction.

### 2. Unrestricted Agent-generated KCL

Rejected because:

- non-deterministic;
- difficult to validate;
- poor recovery when geometry is wrong;
- observed Zookeeper behavior requires iterative correction;
- undermines reliable demos.

### 3. Text-only input

Rejected because:

- lay users struggle to describe physical geometry;
- dimensions and profiles are easier to verify visually;
- increases hallucination and ambiguity.

### 4. Photo directly to final model

Rejected because:

- unsafe inference;
- perspective distortion;
- hidden geometry;
- user cannot trust result;
- no approval gate.

### 5. General-purpose adapter support

Rejected for MVP because:

- arbitrary topologies are too broad;
- difficult to test;
- higher engine failure rate;
- weaker polish.

### 6. Streamlit-only application

Possible but not preferred because:

- weaker custom SVG editing;
- less polished guided workflow;
- limited frontend control.

### 7. Local CAD kernel instead of Zoo

Rejected for competition entry because:

- weakens meaningful Zoo API use;
- adds kernel complexity;
- defeats core contest objective.

### 8. Pure in-memory session state

Considered for speed but risky because:

- application restart loses projects;
- weak demo reliability;
- no recovery.

A lightweight persistent store is preferred.

---

## Known trade-offs

- Restricting profile types improves reliability but limits perceived generality.
- Requiring user approval adds steps but builds trust.
- External vision improves accessibility but adds latency and privacy considerations.
- Deterministic KCL limits creative freedom but improves reproducibility.
- Supporting angled adapters increases wow factor but adds geometric failure risk.
- Server-side orchestration protects secrets but adds backend complexity.
- SQLite improves recovery but introduces schema management.
- Polling is simpler than WebSockets but less immediate.
- STL/KCL; STEP is planned but not implemented exports create value but increase external API failure surfaces.
- Desktop-first design is practical but limits mobile use.
- Preserving last known good models uses more storage but greatly improves recovery.

---

## Unresolved decisions

1. Exact vision provider and model.
2. Exact Zoo SDK versus direct REST/WebSocket use.
3. Whether generation jobs are synchronous or polled background jobs.
4. Whether SQLite is mandatory for MVP.
5. Exact artifact storage approach in deployed demo.
6. Exact 3D preview technology.
7. Whether GLB is required internally for preview.
8. Maximum traced-profile point count.
9. Profile-resampling algorithm.
10. Maximum supported angle.
11. Offset-to-length safety formula.
12. Default wall-thickness rules.
13. Fit preset values.
14. Whether volume analysis is stable enough for user-facing display.
15. Whether direct browser camera capture is included.
16. Whether manual basic-shape entry exists as fallback.
17. Whether design JSON is user-downloadable.
18. Whether sample projects are interactive.
19. Whether section view is included.
20. Exact deployment host.

---

# Architecture Decision Records

The following ADRs define decisions that implementation agents must not casually reverse. Any proposed reversal requires:

- explicit product-owner approval;
- written rationale;
- impact analysis;
- migration plan;
- update to this document and `docs/DESIGN_DECISIONS.md`.

---

## ADR-001 — Canonical design schema is the source of truth

**Status:** Accepted

### Decision

The versioned canonical design schema is the source of truth for all user-approved geometry and manufacturing inputs.

KCL is a generated artifact, not the primary project state.

### Rationale

- separates user intent from CAD syntax;
- supports validation;
- enables deterministic regeneration;
- enables future alternative renderers;
- makes Agent changes safe and inspectable.

### Consequences

- all geometry generation must begin from validated schema;
- raw KCL edits are not imported back into project state in MVP;
- schema migrations must be versioned.

### Agents must not

- replace canonical JSON with KCL as project state;
- mutate model geometry outside schema;
- accept arbitrary frontend KCL.

---

## ADR-002 — Final KCL generation is deterministic

**Status:** Accepted

### Decision

Final KCL must be emitted from tested templates and functions using validated canonical data.

### Rationale

- avoids Agent unpredictability;
- improves testability;
- makes bugs reproducible;
- supports reliable demo flow.

### Consequences

- supported geometry is intentionally constrained;
- new geometry families require explicit templates and tests.

### Agents must not

- allow an LLM to freely generate final executable KCL;
- bypass template validation to make a single case pass.

---

## ADR-003 — AI outputs are untrusted proposals

**Status:** Accepted

### Decision

Vision and Agent outputs are treated as untrusted structured proposals until validated.

### Rationale

- models may hallucinate;
- dimensions and geometry affect physical fit;
- protects against prompt injection and malformed output.

### Consequences

- strict schemas;
- allowlists;
- user approval;
- no direct execution.

### Agents must not

- apply Agent patches without validation;
- mark inferred values as user-entered;
- silently approve profiles.

---

## ADR-004 — Interface approval is a mandatory gate

**Status:** Accepted

### Decision

Both interfaces must be explicitly approved before connection configuration and generation.

### Rationale

- preserves user trust;
- makes uncertainty visible;
- prevents bad image inference from becoming hidden geometry.

### Consequences

- additional workflow steps;
- approved profiles become versioned state;
- editing invalidates downstream model state.

### Agents must not

- auto-approve profiles;
- skip approval for demo speed;
- generate from unresolved critical values.

---

## ADR-005 — Preserve the last known good model

**Status:** Accepted

### Decision

A failed revision or regeneration must not replace or delete the previous successful model.

### Rationale

- protects user work;
- enables safe iteration;
- improves resilience during remote API failures.

### Consequences

- model revisions are versioned;
- stale/current status must be explicit;
- artifact storage retains at least one prior successful result.

### Agents must not

- overwrite current model before new generation succeeds;
- delete prior exports on failed revision.

---

## ADR-006 — Zoo Engine API is the core geometry executor

**Status:** Accepted

### Decision

Zoo’s Engine API is central to geometry execution and model generation.

### Rationale

- contest alignment;
- meaningful use requirement;
- avoids adding another CAD kernel;
- demonstrates Zoo as a programmable geometry backend.

### Consequences

- network dependency;
- API-minute consumption;
- need for robust error handling and logs.

### Agents must not

- replace Zoo with a local CAD kernel for the primary workflow;
- reduce Zoo to a decorative export-only integration.

---

## ADR-007 — Agent API is limited to structured revisions and explanations

**Status:** Accepted

### Decision

The Agent API may interpret natural-language changes, ask clarification, and explain issues, but it cannot directly control final geometry.

### Rationale

- preserves useful AI interaction;
- avoids unrestricted CAD generation;
- improves safety and predictability.

### Consequences

- parameter patch schema required;
- unsupported requests must fall back to manual controls.

### Agents must not

- let Agent output overwrite KCL;
- allow non-allowlisted schema paths.

---

## ADR-008 — Purpose-built UX replaces manual Zoo correction

**Status:** Accepted

### Decision

Users correct profiles and parameters inside InterfaceForge, not in Zoo Design Studio.

### Rationale

- Zoo’s manual CAD UX is not suitable for the target lay user;
- InterfaceForge must hide KCL and CAD complexity;
- correction must remain guided and accessible.

### Consequences

- SVG and parameter editing are core product features;
- no “Open in Design Studio to fix” dependency.

### Agents must not

- make Design Studio a required user step;
- expose raw KCL as the primary editor.

---

## ADR-009 — Backend owns all privileged external API calls

**Status:** Accepted

### Decision

Vision, Zoo Engine, Agent, and File Format calls requiring credentials are made by the backend.

### Rationale

- protects secrets;
- centralizes validation and error handling;
- enables observability and quotas.

### Consequences

- backend required even for static frontend;
- frontend uses only InterfaceForge API.

### Agents must not

- embed provider keys in frontend;
- call privileged provider APIs directly from browser.

---

## ADR-010 — MVP remains a modular monolith

**Status:** Accepted

### Decision

The MVP uses one frontend and one backend application, with internal modules rather than microservices.

### Rationale

- solo developer;
- short competition window;
- easier deployment and debugging;
- sufficient separation through modules.

### Consequences

- internal boundaries must still be explicit;
- background jobs remain lightweight.

### Agents must not

- introduce microservices, message brokers, or distributed infrastructure without explicit approval.

---

## ADR-011 — No user accounts or billing in MVP

**Status:** Accepted

### Decision

The Makeathon MVP has no end-user login, account system, subscription, payment, or credit balance.

### Rationale

- not needed to prove value;
- high implementation and compliance cost;
- distracts from competition scoring.

### Consequences

- temporary project tokens;
- limited persistence;
- no cloud project list.

### Agents must not

- add authentication frameworks;
- build billing or credit logic;
- redirect users to sign-in.

---

## ADR-012 — Geometry scope is intentionally constrained

**Status:** Accepted

### Decision

The MVP supports only defined profile families and connection modes.

### Rationale

- reliable generation;
- testability;
- physical validation;
- competition polish.

### Consequences

- unsupported requests must be rejected clearly;
- extensibility belongs in roadmap/documentation.

### Agents must not

- add arbitrary freeform CAD;
- expand topology before P0 reliability is achieved.

---

## ADR-013 — Errors are product features, not raw exceptions

**Status:** Accepted

### Decision

All significant failures map to stable error IDs, plain-language explanations, and corrective actions.

### Rationale

- target users do not understand API/KCL errors;
- judging rewards notes and bug reporting;
- improves support and reproducibility.

### Consequences

- central error registry;
- provider errors normalized;
- logs retain technical context.

### Agents must not

- expose raw stack traces;
- use generic “Something went wrong” where a known category exists.

---

## ADR-014 — Accessibility is implemented before visual polish

**Status:** Accepted

### Decision

Semantic structure, keyboard access, text equivalents, focus handling, and non-color status cues are baseline implementation requirements.

### Rationale

- target user accessibility;
- prevents expensive retrofit;
- wireframes already define accessible states.

### Consequences

- SVG and 3D information require text equivalents;
- drag cannot be mandatory;
- dynamic states use live regions.

### Agents must not

- defer all accessibility until final styling;
- create color-only provenance or validation.

---

## ADR-015 — Competition documentation is part of implementation

**Status:** Accepted

### Decision

API notes, bug reports, design decisions, tests, and limitations are updated during development, not after.

### Rationale

- documentation and bug reporting represent a major portion of judging;
- real-time notes are more accurate;
- improves team/agent coordination.

### Consequences

- significant changes include documentation updates;
- bugs require reproducible records.

### Agents must not

- postpone all documentation until the end;
- silently work around Zoo bugs without recording them.
