# InterfaceForge — System Architecture

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Modular Monolith Architecture

InterfaceForge uses a modular monolith design containing a FastAPI backend and a React/TypeScript frontend.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ React / TypeScript Frontend                                              │
│ - Global App Shell & Step Navigation (`src/components/StepNavigation`)    │
│ - Session Hydration & Route Guards (`src/components/ProtectedRoute`)    │
│ - Typed API Client (`src/services/api.ts`) & Schema Contracts (`types`)  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTP REST (JSON Envelopes)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (`backend/app`)                                          │
│                                                                          │
│  [API Layer]           `app/api/routes/projects.py`, `generation.py`    │
│                               │                                          │
│  [Service Layer]       `app/services/project_service.py`                 │
│                        - Invariant enforcement & workflow state machine  │
│                        - Schema revision increment & staleness logic     │
│                               │                                          │
│  [Repository Layer]    `app/repositories/sqlite_project_repository.py`   │
│                        - SQLite local persistence (`artifacts/*.db`)     │
│                        - Automated bootstrap and schema management       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Storage & Persistence Layer

- **Database:** SQLite 3 (Standard Library `sqlite3`)
- **File Location:** `artifacts/interfaceforge.db` (Excluded from Git via `.gitignore`)
- **Upload Storage:** `artifacts/uploads/` (Excluded from Git via `.gitignore`)
- **Schema Bootstrap:** Auto-executed on app creation via `SQLiteProjectRepository`.
- **Isolation:** Decoupled repository interface separating DB operations from API route controllers.

---

## 3. Analysis Provider Architecture & Upload Pipeline

Stage S4A introduces the decoupled `AnalysisProvider` abstraction:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ AnalysisProvider (Abstract Base Class)                                   │
│  - `analyze(image_bytes: bytes, filename: str) -> AnalysisResult`        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
GeminiAnalysisProvider (Vision guidance)                     MockAnalysisProvider (Fallback)
- Multimodal image guidance for clean cross-sections     - Deterministic candidate profile generation
- OpenCV remains responsible for deterministic tracing                       - Configurable offline/demo provider
- Strict JSON schema & finite value validation           - Safe fallback when key is unconfigured
- Honest low-confidence quality rejection (< 0.60)       - Selected via ANALYSIS_PROVIDER=mock
```

### Upload Pipeline & Security Controls

1. **File Validation:** MIME type allowlist (`image/png`, `image/jpeg`, `image/webp`), extension validation, 10MB size limit.
2. **Path Traversal Protection:** Base name sanitization (`os.path.basename`) and `target_path.startswith(abs_upload_dir)` validation.
3. **Image Corruption Prevention:** Dual-pass Pillow decoding (`Image.open().verify()` and `load()`) to prevent image bomb attacks.
4. **State Transition Enforcement:** `interface_a_uploaded` and `interface_b_uploaded` state progression; Interface B upload requires approved Interface A (`IF-PREREQ-400`).

---

## 5. KCL Compiler Service Layer (Stage S5A)

Per **ADR-001** and **ADR-002**, Stage S5A introduces a dedicated, deterministic KCL compiler service layer (`backend/app/services/kcl_compiler.py`).

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Canonical Project Design Schema (Source of Truth)                       │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ Validation Gate (Readiness Check)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ KCL Compiler (`app/services/kcl_compiler.py`)                           │
│ - Supported profiles: circle, rectangle, rounded_rectangle, and approved traced_closed              │
│ - Supported connection modes: coaxial, offset, angled (<= 45°)           │
│ - Output: Deterministic KCL string with explicit mm units & comments     │
│ - SHA-256 Hash computation & version metadata (v1.0.0)                  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ Artifact Write
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Artifact Storage (`artifacts/kcl_<project_id>_rev<rev>_<hash>.kcl`)       │
│ - Model revision updated as status=DRAFT (Zoo execution pending)         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Brand & Visual Design System Foundation

- **Visual Theme:** Restrained dark theme with high-contrast neon-green accent tokens (`--accent-neon-green: #00e676`).
- **Logo System:** Full SVG logo (`InterfaceForge_logo.svg`) for landing page and wide desktop header; compact logo mark (`InterfaceForge_logo_in.svg`) for narrow screens, loading states, and app favicon.
- **Accessibility Baseline:** Non-color-only status indicators (`✓ [VALID]`, `⚠️ [WARNING]`, `⛔ [ERROR]`), visible focus ring (`:focus-visible`), and standard GFM contrast thresholds per **ADR-014**.

---

## 7. Zoo Engine Provider Abstraction & Generation Pipeline (Stage S6)

Per **ADR-005**, **ADR-006**, and **ADR-009**, Stage S6 implements live 3D execution via `ZooEngineProvider` behind the `EngineProvider` abstract contract.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ GenerationJobService (`app/services/generation_job_service.py`)         │
│ - Enforces single active job per project (IF-JOB-409 duplicate rejection) │
│ - Preserves last-known-good model revision (ADR-005)                    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
ZooEngineProvider (Active in S6)                        MockEngineProvider (Fallback)
- Live WebSocket modeling API                             - Deterministic staged progress
- Endpoint: wss://api.zoo.dev/ws/modeling/commands        - 6 test scenarios (success, timeout, etc.)
- Bearer auth from backend/.env                           - Offline development mode
- Secret redaction (redact_secrets)                       - Configurable via ENGINE_PROVIDER=mock
```

---

## 8. Full Web App Workflow & Route Integration Architecture (Stage S6A)

Stage S6A connects all individual page components into one end-to-end web application workflow:

1. **Session Hydration:** Active `project_id` & `project_token` stored in `sessionStorage`. Asynchronous hydration on mount via `fetchProject`.
2. **Server-Side & Client-Side Route Guards (`ProtectedRoute.tsx`):** Computes `getEarliestIncompleteStep(project)`. Redirects invalid direct URL access automatically.
3. **Stale Model Handling:** Upstream edits to approved interfaces or connection parameters set model state to `STALE` and trigger warning notices on Step 4 and Step 5.
4. **Preservation of Last-Known-Good Model:** Failed generation attempts preserve `last_known_good_model_revision` without overwriting active model state.
5. **Result and Export Review (`ResultPage.tsx`):** Presents the generated adapter as an inspectable candidate, preserves stale/last-known-good status, and offers STL/KCL exports only from the current approved model revision.

---

## 9. Bounded Zoo Agent API Revision Architecture (Stage S9)

Stage S9 integrates natural language model revisions via `ZooAgentProvider` behind the `AgentProvider` abstraction:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ User Natural Language Input (ResultPage.tsx Revision Panel)               │
│ - "Make it 20 mm longer", "Move outlet 10 mm right and 5 mm up"           │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ POST /api/projects/{id}/revision/propose
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ AgentService (`app/services/agent_service.py`)                           │
│  - Fetches active project schema & trusted parameter values               │
│  - Queries `AgentProvider` (`ZooAgentProvider` or `MockAgentProvider`)   │
│  - Server-side allowlist check (7 allowed connection/mfg fields ONLY)    │
│  - Parametric range & engineering validation (`connection_validation`)    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ Returns AgentProposalResult (Unapplied)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ User Confirmation Gate (`ResultPage.tsx`)                                │
│ - Displays summary, before/after value table, and validation warnings     │
│ - Requires explicit user click on "Confirm Revision"                      │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ POST /api/projects/{id}/revision/confirm
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Schema Patch, KCL Compilation & 3D Generation Pipeline                   │
│ - Updates canonical project schema & increments current_schema_revision  │
│ - Compiles deterministic KCL (`kcl_compiler.py`)                         │
│ - Initiates 3D generation job (`GenerationJobService`)                   │
│ - Preserves last-known-good model revision if 3D generation fails        │
└──────────────────────────────────────────────────────────────────────────┘
```

