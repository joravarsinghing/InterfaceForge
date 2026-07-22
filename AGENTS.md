# InterfaceForge — Agent Governance and Operation Guidelines (AGENTS.md)

**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Document status:** Active Governance Rules  

---

## 1. Mandatory Reading

Every AI coding or review agent (Codex, Antigravity/Gemini, Claude, or subagents) MUST read the following source-of-truth documents before making modifications:

1. [`InterfaceForge_PRD_v0.1.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/InterfaceForge_PRD_v0.1.md)
2. [`technical_design.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/technical_design.md)
3. [`user_flow.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/user_flow.md)
4. [`ascii_wireframes.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/ascii_wireframes.md)
5. [`README.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/README.md)
6. [`LICENSE`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/LICENSE)
7. [`.gitignore`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/.gitignore)
8. [`.gitattributes`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/.gitattributes)
9. [`production_docs/S1_PROJECT_FOUNDATION.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/production_docs/S1_PROJECT_FOUNDATION.md)

---

## 2. Document Precedence Hierarchy

When conflicts or ambiguities arise, agents MUST enforce the following precedence order:

1. **Product Requirements Document (PRD)** ([`InterfaceForge_PRD_v0.1.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/InterfaceForge_PRD_v0.1.md))
2. **Technical Design & Accepted ADRs** ([`technical_design.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/technical_design.md))
3. **User Flows** ([`user_flow.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/user_flow.md))
4. **ASCII Wireframes** ([`ascii_wireframes.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/ascii_wireframes.md))
5. **Production Control Documents** (`production_docs/S<N>_*.md`)
6. **Implementation Notes & Scratchpads**

*Note: Agents must not silently resolve conflicts. Any conflict must be explicitly documented in production stage reports.*

---

## 3. Mandatory Governance Rules

### 3.1 Accepted ADR Compliance
Agents must strictly comply with all accepted Architecture Decision Records (ADR-001 through ADR-015 in `technical_design.md`):
- **ADR-001:** Canonical design schema is the source of truth; KCL is a generated artifact.
- **ADR-002:** Final KCL generation is deterministic; no unconstrained LLM CAD generation.
- **ADR-003:** AI outputs are untrusted proposals; validation and approval required.
- **ADR-004:** Interface approval is a mandatory gate before 3D generation.
- **ADR-005:** Preserve the last-known-good model after failed revisions.
- **ADR-006:** Zoo Engine API is the core geometry executor.
- **ADR-007:** Agent API is limited to structured revisions and explanations.
- **ADR-008:** Purpose-built UX replaces manual Zoo Design Studio editing for users.
- **ADR-009:** Backend owns all privileged external API calls and credentials.
- **ADR-010:** MVP remains a modular monolith (single frontend + single backend).
- **ADR-011:** No user accounts, billing, or cloud project systems in MVP.
- **ADR-012:** Geometry scope is strictly constrained to supported families and modes.
- **ADR-013:** Errors are product features with stable error IDs, plain text, and recovery steps.
- **ADR-014:** Accessibility baseline is enforced before visual polish.
- **ADR-015:** Competition documentation is maintained continuously during development.

### 3.2 Scope and Modifications
- **No Unapproved Scope Expansion:** Do not add unrequested features or post-MVP capabilities.
- **Small & Reviewable Changes:** Keep edits modular, focused, and testable.
- **Tests Required:** Behavioral and logic changes must include accompanying unit/integration tests.
- **No Destructive Edits Without Rollback:** Never perform destructive refactors without preserving a working rollback state.
- **Preserve Last-Known-Good Behavior:** Existing working behavior must remain stable when adding or refactoring code.

### 3.3 Security & Assets
- **No Committed Secrets or Private Data:** Never commit API keys, `.env` files, credentials, personal uploads, or temporary artifacts.
- **Artifact Isolation:** Generated STL, STEP, KCL, GLB, SQLite DBs, and preview images must reside in `artifacts/` and remain git-ignored.

### 3.4 Bug Tracking & Zoo API Reporting
- All Zoo API issues, SDK bugs, or unexpected behavior must be recorded immediately in [`docs/BUGS_AND_LIMITATIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/BUGS_AND_LIMITATIONS.md) and [`docs/ZOO_API_NOTES.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/ZOO_API_NOTES.md) with reproduction steps.

---

## 4. Mandatory Approval Gates

Agents MUST STOP and request explicit user/product-owner approval before altering any of the following:

1. **Canonical Schema** (`schema_version`, data structures, dimension definitions)
2. **User Flows** (step sequences, approval gates, navigation logic)
3. **API Responsibilities** (frontend/backend boundaries, provider roles)
4. **Geometry Scope** (profile types, lofting rules, connection modes, physical constraints)
5. **Deployment Model** (stack choices, hosting architecture, database selection)
6. **Accepted ADRs** (ADR-001 through ADR-015)
7. **Competition Deliverables** (README scope, video scripts, contest submission forms)

---

## 5. Stage Reports and Response Format

- Relevant production control documents in `production_docs/` must be updated as work progresses.
- **Completion Report Requirement:** Every task execution response provided by an agent MUST end with the standardized completion-report format defined below:

```text
Work completed
Files created
Files modified
Governance established
Repository structure
Final tree
Any deviations from requested structure
Tests run
Exact commands
Passed
Failed
Skipped
Validation evidence
Repository-audit output
Git-status summary
Secret-scan summary
Markdown/link-check summary
Issues found
Conflicts between source documents
Missing information
Risks
Technical debt
Scope concerns
Documentation updated
Production report
README
AGENTS.md
Placeholder documents
User intervention required
Exact decisions or manual actions needed
Recommended next stage
State whether current stage is ready to close
List blockers
Recommend the exact scope of next stage
```
