# Status and decision classification

The ADR sections below preserve valid rationale. The current submission corrections at the top are active behavior. References to angle, STEP, older providers, or stage-era defaults are historical or compatibility-only unless explicitly identified as active. The active Agent allowlist contains six fields.

# Current submission corrections

The following active boundary supersedes older stage notes in this historical decision log: profiles are circle, rectangle, rounded_rectangle, or approved traced_closed; connections are coaxial or parallel offset; the Agent allowlist excludes angle fields; KCL 2.0 and LoftPlan are authoritative; exports are STL/KCL; STEP is planned only. Mock and Gemini references below describe explicit local/optional providers, not silent production fallbacks.

# InterfaceForge Ã¢â‚¬â€ Design Decisions (ADRs & Technical Rationale)

**Document Status:** Active Record  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Stage S3 Persistence Decision: SQLite via Standard Library `sqlite3`

### Decision
Use SQLite standard library (`sqlite3`) for lightweight local project persistence with database files located at `artifacts/interfaceforge.db`.

### Rationale
1. **Zero Infrastructure:** Local development friendly with no external daemons or Docker service dependencies required.
2. **Git Safety:** Database files are stored under `artifacts/` and matched by `*.db` in `.gitignore`, keeping binary state excluded from source control.
3. **Automated Bootstrap:** `SQLiteProjectRepository` automatically executes schema migrations (`CREATE TABLE IF NOT EXISTS projects ...`) on application startup.
4. **Architectural Separation:** Repository layer is strictly separated from service business logic and API endpoints.

---

## 3. Stage S5A Decision: Deterministic KCL Compiler Layer & Brand Integration

### Decision
1. **Deterministic KCL Emission:** Implement KCL code emission in a pure Python compiler service (`backend/app/services/kcl_compiler.py`) derived strictly from canonical schema values without LLM code generation (ADR-001, ADR-002).
2. **Draft Model Status Prior to Execution:** Compiled KCL artifacts create model revisions with status `draft`. The `current_model_revision` is NOT set until Zoo Engine API execution completes successfully.
3. **Restrained Dark Theme & Brand Design System:** Establish CSS design tokens featuring high-contrast dark backgrounds and neon-green accent colors (`#00e676`), integrating full logo SVG (`InterfaceForge_logo.svg`) and compact mark (`InterfaceForge_logo_in.svg`).

### Rationale
- Prevents unconstrained LLM CAD code generation bugs and guarantees reproducible output.
- Upholds strict invariant that unexecuted CAD code does not update active current model state.
- Establishes accessible visual identity adhering to WCAG contrast standards and ADR-014.

---

## 4. Stage S5.5 Decision: EngineProvider Abstraction & Mock Execution Pipeline

### Decision
1. **EngineProvider Abstraction:** Implement an abstract base class `EngineProvider` and deterministic implementation `MockEngineProvider` in `backend/app/services/engine_provider.py` (ADR-006, ADR-009).
2. **Staged Execution Progress:** Model generation progresses through discrete stages (`validating`, `compiling`, `executing`, `rendering`, `finalizing`).
3. **Last-Known-Good Preservation:** If generation fails or is cancelled, `last_known_good_model_revision` is preserved as active `current` model (ADR-005).
4. **Duplicate Active-Job Prevention:** Enforce single active generation job per project (`IF-JOB-409`).
5. **Safe Configuration Fallback:** If `ENGINE_PROVIDER=zoo` is configured without `ZOO_API_TOKEN`, the backend safely falls back to `mock` mode.

### Rationale
- Decouples geometry execution from live credentials, allowing comprehensive offline development and testing.
- Guarantees seamless transition to live Zoo Engine API in Stage S6 without breaking frontend API contracts.

---

## 6. Stage S7 Decision: Real Vision Integration via Gemini Multimodal Vision API

### Decision
1. **Multimodal Vision Integration:** Implement `GeminiAnalysisProvider` behind existing `AnalysisProvider` abstraction using Google Gemini 2.5 Flash model (ADR-003, ADR-009).
2. **Backend-Only Secret Credentials:** Store API key (`GEMINI_API_KEY`) strictly in `backend/.env` with automatic secret redaction (`sanitize_error_message`) on all exception tracebacks and logs.
3. **Versioned Prompt & Untrusted Model Output Validation:** Enforce prompt version `1.0` and multi-pass output validation (JSON structure, profile enums, finite numbers via `math.isfinite`, and confidence range `[0.0, 1.0]`).
4. **Honest Rejection & Recovery:** Rejections (< 0.60 confidence) raise `AnalysisRejectedError` (`IF-ANALYSIS-400`) with clear recovery steps without altering project schema.
5. **Configurable Mock Fallback:** Safe automatic fallback to `MockAnalysisProvider` when `ANALYSIS_PROVIDER=mock` or when API keys are unconfigured.

### Rationale
- Treats AI vision predictions as unapproved candidate proposals requiring explicit user approval per ADR-003 and ADR-004.
- Protects API keys from leaking to client frontend or log files per ADR-009.
- Prevents invalid or malformed LLM outputs from corrupting canonical project memory.

---

## 7. Stage S9 Decision: Bounded Zoo Agent API Revisions & Confirmation Gate

### Decision
1. **Agent as Intent Interpreter Only:** Integrate ZooÃ¢â‚¬â„¢s Copilot WebSocket API (`wss://api.zoo.dev/ws/ml/copilot`) via `ZooAgentProvider` behind `AgentProvider` abstraction. The Agent interprets user intent but is strictly forbidden from writing KCL or generating CAD geometry directly (ADR-001, ADR-002, ADR-007).
2. **Server-Side Agent Allowlist:** Proposals are restricted to 6 explicit connection/manufacturing fields (`connection.length_mm`, `connection.offset_x_mm`, `connection.offset_y_mm`, `manufacturing.wall_thickness_mm`, `manufacturing.clearance_a_mm`, `manufacturing.clearance_b_mm`). Out-of-allowlist requests (profile type changes, process, material, KCL code generation) are rejected server-side (`IF-AGENT-400`).
3. **Explicit User Confirmation Gate:** Proposals are returned as unapplied suggestions. Schema parameters, KCL compilation, and 3D generation execute ONLY after explicit user confirmation (`POST /api/projects/{id}/revision/confirm`).
4. **Preservation of Last-Known-Good Model (ADR-005):** If 3D generation fails after confirmation, `last_known_good_model_revision` remains preserved as active current model without corrupting project state.

### Rationale
- Prevents AI hallucinations, unintended topology changes, or malicious prompt injection from corrupting 3D geometry.
- Enforces user ownership and full transparency over design parameter revisions before 3D execution.

---

## 8. ADR Summary Index

- **ADR-001:** Canonical design schema is source of truth.
- **ADR-002:** Final KCL generation is deterministic.
- **ADR-003:** AI outputs are untrusted proposals requiring validation.
- **ADR-004:** Interface approval is mandatory gate before 3D generation.
- **ADR-005:** Preserve last-known-good model after failed revisions.
- **ADR-006:** Zoo Engine API is core geometry executor.
- **ADR-007:** Agent API is limited to structured revisions and explanations.
- **ADR-008:** Purpose-built UX replaces manual Zoo Design Studio editing.
- **ADR-009:** Backend owns all privileged external API calls and credentials.
- **ADR-010:** MVP modular monolith structure.
- **ADR-012:** Geometry scope includes circle, rectangle, rounded rectangle, and approved `traced_closed` profiles; supported connection modes are coaxial and offset.
- **ADR-013:** Standardized error envelopes with stable error IDs.
- **ADR-014:** Accessibility baseline is enforced before visual polish.

