# InterfaceForge — System Architecture

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Modular Monolith Architecture

InterfaceForge uses a modular monolith design containing a FastAPI backend and a React/TypeScript frontend.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ React / TypeScript Frontend                                              │
│ - Global App Shell & Step Navigation                                     │
│ - Typed API Client (`src/services/api.ts`) & Schema Contracts (`types`)  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTP REST (JSON Envelopes)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FastAPI Backend (`backend/app`)                                          │
│                                                                          │
│  [API Layer]           `app/api/routes/projects.py`                      │
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
MockAnalysisProvider (S4A Active)                        GeminiAnalysisProvider (Future S4B+)
- Deterministic profile extraction                       - Real multimodal LLM contour extraction
- Returns circle, rect, rounded rect                      - Structured JSON schema enforcement
- Rejection on poor image quality                        - Fallback to mock on network failure
```

### Upload Pipeline & Security Controls

1. **File Validation:** MIME type allowlist (`image/png`, `image/jpeg`, `image/webp`), extension validation, 10MB size limit.
2. **Path Traversal Protection:** Base name sanitization (`os.path.basename`) and `target_path.startswith(abs_upload_dir)` validation.
3. **Image Corruption Prevention:** Dual-pass Pillow decoding (`Image.open().verify()` and `load()`) to prevent image bomb attacks.
4. **State Transition Enforcement:** `interface_a_uploaded` and `interface_b_uploaded` state progression; Interface B upload requires approved Interface A (`IF-PREREQ-400`).

---

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
│ - Supported profiles: circle, rectangle, rounded_rectangle              │
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

