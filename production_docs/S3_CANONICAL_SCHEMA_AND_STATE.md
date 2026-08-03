# Stage S3 — Canonical Design Schema and Project State

**Stage Status:** Complete  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Date:** July 22, 2026  
**Primary Author:** Antigravity AI  

> **Historical / Superseded:** This stage report records its historical state and outcomes; it is not the current submission capability contract. Current truth: KCL 2.0 solid-body generation works; supported outputs are STL and KCL; STEP is planned but not implemented; supported connection modes are coaxial and offset; angle-based connections are unsupported; historical surface-shell, `joinSurfaces()`, Boolean-blocker, and deprecated-KCL notes are superseded; live Zoo Agent execution remains unproven unless credential-tested.

---

## 1. Executive Summary

Stage S3 establishes the internal source of truth required by **ADR-001** and **ADR-005**. Versioned Pydantic models for the canonical design schema have been implemented in the FastAPI backend alongside matching TypeScript contracts in the React frontend. Lightweight local persistence is backed by SQLite via standard library `sqlite3`. Server-side invariant enforcement ensures valid workflow transitions, schema revision incrementing, downstream model staleness propagation, and last-known-good model preservation upon generation failure.

---

## 2. Selected Persistence Approach

- **Engine:** SQLite 3 via standard library `sqlite3`.
- **Database Location:** Configurable via `settings.db_path`, defaulting to `artifacts/interfaceforge.db` (git-ignored via `.gitignore`).
- **Bootstrap & Migration:** Auto-creates table `projects` if it does not exist when `SQLiteProjectRepository` initializes. Supports in-memory test databases (`:memory:`) via shared connection handle.
- **Architectural Separation:** `SQLiteProjectRepository` isolates database access from `ProjectService` business logic and API endpoints.

---

## 3. Canonical Schema Models

Implemented versioned models in `backend/app/models/schema.py`:

1. **Project:** `project_id`, `project_token`, `schema_version` ("0.1"), `state`, timestamps, `current_schema_revision`, `current_model_revision`, `last_known_good_model_revision`, `interface_a`, `interface_b`, `connection`, `manufacturing`, `model_revisions`.
2. **Interface:** `id`, `source_image_ref`, `profile_type` (`circle`, `rectangle`, `rounded_rectangle`, `traced_closed`), `profile_points`, `center`, `dimensions`, `validation`, `approved`, `approved_at`.
3. **Dimension:** `id`, `label`, `value`, `unit`, `provenance` (`user_entered`, `image_extracted`, `system_inferred`, `unresolved`), `confidence`, `critical`.
4. **Connection:** `mode` (`coaxial`, `offset`, `angled`), `length_mm`, `offset_x_mm`, `offset_y_mm`, `angle_deg`.
5. **Manufacturing:** `process` (`fdm`, `sla`, `cnc`), `material`, `wall_thickness_mm`, `clearance_a_mm`, `clearance_b_mm`.
6. **ModelRevision:** `model_revision`, `schema_revision`, `status` (`draft`, `generating`, `current`, `stale`, `failed`, `superseded`), `kcl_artifact_ref`, `preview_artifact_ref`, `exports` (`stl`, `step`), `volume_cm3`, `warnings`, `generated_at`.

---

## 4. Workflow State Model & Transition Matrix

Supported workflow states:
`new`, `interface_a_uploaded`, `interface_a_review_required`, `interface_a_approved`, `interface_b_uploaded`, `interface_b_review_required`, `interfaces_approved`, `connection_configured`, `generation_in_progress`, `generation_failed`, `model_current`, `model_stale`, `revision_draft`, `export_in_progress`, `export_ready`.

### Valid Transitions Table

| Current State | Trigger Action | Target State | Notes / Invariants |
| :--- | :--- | :--- | :--- |
| **`new`** | `mark-uploaded` (A) | `interface_a_uploaded` | Creates initial project token |
| **`interface_a_uploaded`** | `approve` (A) | `interface_a_approved` | Interface A locked & approved |
| **`interface_a_approved`** | `mark-uploaded` (B) | `interface_b_uploaded` | Interface B upload enabled |
| **`interface_b_uploaded`** | `approve` (B) | `interfaces_approved` | Invariant 1: Requires Interface A approved |
| **`interfaces_approved`** | `PUT /connection` | `connection_configured` | Invariant 2: Requires both interfaces approved |
| **`connection_configured`**| `model/start` | `generation_in_progress` | Invariant 3: Connection parameters required |
| **`generation_in_progress`**| `model/succeed` | `model_current` | Invariant 8: Promotes revision to current |
| **`generation_in_progress`**| `model/fail` | `generation_failed` | Invariant 7: Preserves last-known-good revision |
| **`model_current`** | `export/start` | `export_in_progress` | Invariant 4: Requires current valid model |
| **`export_in_progress`** | `export/complete` | `export_ready` | Attaches STL and STEP references |
| **`model_current`** | Edit interface | `interface_a/b_review_required` | Invariant 5: Increments schema rev, clears approval, marks model stale |
| **`model_current`** | Edit connection | `model_stale` | Invariant 6: Increments schema rev, marks model stale |

---

## 5. Required Invariants Enforced

1. **Interface B approval:** Rejected with `IF-APPROVAL-400` if Interface A is not approved.
2. **Connection configuration:** Rejected with `IF-PREREQ-400` unless both interfaces are approved.
3. **Generation start:** Rejected with `IF-PREREQ-400` unless both interfaces are approved and connection is configured.
4. **Export start:** Rejected with `IF-STALE-400` unless a current valid model revision exists.
5. **Editing approved interface:** Clears `approved` flag, increments `current_schema_revision`, and marks existing current model as `stale`.
6. **Editing connection/manufacturing:** Increments `current_schema_revision` and marks existing current model as `stale`.
7. **Failed generation:** Preserves `last_known_good_model_revision` without modification.
8. **Successful generation:** Promotes model revision status to `current` and updates `current_model_revision` & `last_known_good_model_revision`.
9. **Revision tracking:** ModelRevision stores exact `schema_revision` and `model_revision`.
10. **State transitions:** Invalid or unknown transitions return stable error codes (`IF-PROJ-404`, `IF-AUTH-401`, `IF-STATE-400`, `IF-PREREQ-400`, `IF-APPROVAL-400`, `IF-STALE-400`, `IF-SCHEMA-400`).

---

## 6. Endpoints Implemented

- `POST /api/projects`: Create project
- `GET /api/projects/{project_id}`: Get project schema
- `PATCH /api/projects/{project_id}`: Top-level patch
- `POST /api/projects/{project_id}/interfaces/{interface_id}/mark-uploaded`: Set uploaded image ref
- `PATCH /api/projects/{project_id}/interfaces/{interface_id}`: Edit interface params
- `POST /api/projects/{project_id}/interfaces/{interface_id}/approve`: Approve interface
- `PUT /api/projects/{project_id}/connection`: Update connection configuration
- `PUT /api/projects/{project_id}/manufacturing`: Update manufacturing configuration
- `POST /api/projects/{project_id}/model/start`: Start model generation
- `POST /api/projects/{project_id}/model/succeed`: Succeed model generation
- `POST /api/projects/{project_id}/model/fail`: Fail model generation
- `POST /api/projects/{project_id}/export/start`: Start export
- `POST /api/projects/{project_id}/export/complete`: Complete export

---

## 7. Test Evidence

Executed master verification check: `python scripts/run_all_checks.py`.

```text
==========================================
Executing: Repository Governance Audit
==========================================
[OK] PASSED step: Repository Governance Audit

==========================================
Executing: Backend Ruff Lint Check
==========================================
[OK] PASSED step: Backend Ruff Lint Check

==========================================
Executing: Backend Ruff Format Check
==========================================
[OK] PASSED step: Backend Ruff Format Check

==========================================
Executing: Backend Mypy Type Check
==========================================
[OK] PASSED step: Backend Mypy Type Check

==========================================
Executing: Backend Pytest Suite
==========================================
[OK] PASSED step: Backend Pytest Suite (14 passed)

==========================================
Executing: Frontend Vitest Suite
==========================================
[OK] PASSED step: Frontend Vitest Suite (6 passed)

==========================================
Executing: Frontend ESLint Check
==========================================
[OK] PASSED step: Frontend ESLint Check

==========================================
Executing: Frontend TypeScript Check
==========================================
[OK] PASSED step: Frontend TypeScript Check

==========================================
Executing: Frontend Production Build
==========================================
[OK] PASSED step: Frontend Production Build

ALL CHECKS PASSED SUCCESSFULLY!
```

---

## 8. Deviations and Unresolved Questions

- No deviations from requested structure or ADR constraints were introduced.
- Future image processing, SVG profile rendering, KCL compilation, and Zoo API calls were intentionally kept out of scope for Stage S3 as requested.

---

## 9. Stage S3 Exit Status

- [x] Canonical backend schema created and versioned (`schema_version`: "0.1").
- [x] Matching frontend TypeScript contracts created and compiling.
- [x] SQLite persistence implemented and tested.
- [x] Workflow states and 10 server-side invariants enforced.
- [x] Schema revision increment & downstream staleness behavior verified.
- [x] Last-known-good model preservation verified.
- [x] Stable error IDs implemented.
- [x] Documentation updated (`docs/*` and `production_docs/S3_CANONICAL_SCHEMA_AND_STATE.md`).
- [x] All 9 master verification checks pass.
- Stage S3 is ready to close.
