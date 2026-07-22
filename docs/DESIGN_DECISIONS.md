# InterfaceForge — Design Decisions (ADRs & Technical Rationale)

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

## 4. ADR Summary Index

- **ADR-001:** Canonical design schema is source of truth.
- **ADR-002:** Final KCL generation is deterministic.
- **ADR-005:** Preserve last-known-good model after failed revisions.
- **ADR-006:** Zoo Engine API is core geometry executor.
- **ADR-008:** Purpose-built UX replaces manual Zoo Design Studio editing.
- **ADR-010:** MVP modular monolith structure.
- **ADR-012:** Geometry scope is strictly constrained to supported families and modes.
- **ADR-013:** Standardized error envelopes with stable error IDs.
- **ADR-014:** Accessibility baseline is enforced before visual polish.

