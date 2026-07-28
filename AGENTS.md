# InterfaceForge — Agent Guidelines

**Project:** InterfaceForge  
**Status:** Active agent governance  
**Priority:** Submission reliability, minimal scope, evidence-based completion

## 1. Read Before Editing

Before making changes, inspect only the source documents relevant to the task:

- `README.md`
- `InterfaceForge_PRD_v0.1.md`
- `technical_design.md`
- `user_flow.md`
- `docs/ARCHITECTURE.md`
- relevant source files, tests, and current production report

Read additional documents only when needed. Do not spend tokens summarizing documents unless requested.

## 2. Source-of-Truth Order

Resolve decisions using this order:

1. Current user instruction
2. Accepted ADRs and `technical_design.md`
3. PRD
4. Current user flow
5. Current architecture and API documentation
6. Existing tested implementation
7. Production reports and archived stage history

Do not silently resolve a material conflict. Report it before implementing when it affects product behavior, architecture, schema, geometry, or provider boundaries.

## 3. Core Architecture Rules

- Canonical project JSON is the source of truth.
- KCL is generated deterministically from approved project data.
- AI output is an untrusted proposal until validated and confirmed.
- Interface approval and explicit scale confirmation are mandatory before generation.
- Preserve the last-known-good state after failed analysis, generation, export, or revision.
- Zoo Engine is the authoritative CAD executor.
- Zoo Agent may propose only bounded, allowlisted parameter changes.
- External credentials and privileged API calls remain backend-only.
- Keep the MVP as the existing frontend/backend modular monolith.
- Do not introduce a local production geometry engine.
- Do not expand geometry or input scope without approval.
- Errors must be truthful, recoverable, and use stable error identifiers where established.

## 4. Product Scope

Primary supported workflow:

'''
Clean profile A
→ provide and confirm one known measurement
→ review and approve A
→ repeat for profile B
→ configure connection
→ generate through Zoo Engine
→ optionally confirm a bounded Zoo Agent revision
→ export current STL, STEP, and KCL
'''

Product boundaries:

- Clean, front-facing cross-section images are the supported primary input.
- Annotation-heavy engineering drawings are experimental/manual-review inputs.
- Gemini may provide interpretation or guidance but must not author final geometry.
- OpenCV produces deterministic traces.
- Scale is never applied or confirmed silently.
- Outputs are editable adapter candidates requiring inspection before manufacturing.
- Do not claim arbitrary photo-to-CAD, perfect drawing cleanup, automatic scale accuracy, or unconditional manufacturing readiness.

## 5. Change Discipline

For every task:

- Inspect the current implementation before editing.
- Make the smallest reliable change that satisfies the request.
- Preserve existing working behavior.
- Avoid unrelated refactors, formatting churn, dependency upgrades, or documentation rewrites.
- Reuse existing schemas, services, helpers, and provider boundaries where practical.
- Add tests for changed behavior and regressions.
- Do not weaken backend validation to simplify frontend behavior.
- Do not commit, push, delete user work, or reset the working tree unless explicitly instructed.
- Assume the worktree may already contain unrelated changes; preserve them.
- Do not begin the next phase or add unrequested features.

## 6. Approval Required Before Changing

Stop and request approval before materially changing:

- canonical schema or schema version;
- workflow sequence or approval gates;
- frontend/backend responsibility boundaries;
- provider roles or credential handling;
- supported geometry families or connection modes;
- deployment architecture or database choice;
- accepted ADRs;
- competition deliverables or public product positioning.

A requested bug fix within the established workflow does not require another approval unless it changes one of these boundaries.

## 7. Security and Repository Hygiene

Never commit:

- `.env` files, API keys, tokens, credentials, or private data;
- runtime uploads or local databases;
- generated STL, STEP, KCL, previews, masks, traces, caches, or scratch artifacts;
- local agent tooling.

Generated runtime content must remain in ignored artifact locations.

Record reproducible Zoo API or SDK defects in:

- `docs/BUGS_AND_LIMITATIONS.md`
- `docs/ZOO_API_NOTES.md`

Do not log secrets while recording failures.

## 8. Validation

Select checks appropriate to the files and behavior changed. Prefer focused checks first, then broader regression checks when practical.

Typical checks:

- focused unit or integration tests;
- affected backend or frontend test suite;
- frontend build when frontend code changes;
- lint and type checks for affected code;
- `git diff --check`;
- repository audit when relevant;
- manual browser or live-provider QA when automation cannot prove behavior.

Do not claim:

- visual PASS without visual inspection;
- live-provider PASS without credentialed execution;
- clean-install PASS using an existing environment;
- full regression PASS when only focused tests ran.

Sandbox/tooling failures are not product failures when the same command passes in the correct project environment, but report both outcomes briefly.

## 9. Automatic Failure Conditions

Mark the task FAIL or PARTIAL when any of these apply:

- requested behavior is cosmetic rather than functional;
- backend safety can be bypassed;
- failed work overwrites valid saved state;
- credentials are exposed;
- tests fail due to the implementation;
- unsupported capability claims are introduced;
- unrelated architecture or product scope is changed;
- manual or live verification is required but presented as proven;
- user-authored or pre-existing work is reverted unintentionally.

## 10. Completion Response

Keep the final response concise and include only:

1. **Result:** PASS, PARTIAL, FAIL, or UNPROVEN.
2. **What changed:** files and key behavior.
3. **Validation:** commands and exact pass/fail totals.
4. **Unproven or deferred:** live, visual, credential, or edge-case limitations.
5. **Manual QA:** only when user action is genuinely required.
6. **Diff summary:** concise `git diff --stat` assessment.
7. **Blockers:** omit when none.

Do not repeat the task prompt, print the full repository tree, recommend a next phase unless requested, or add boilerplate sections with no useful information.

## 11. Task Prompt Convention

The current task prompt defines the immediate objective and acceptance criteria. This file supplies the standing rules, so task prompts should not repeat these guidelines unless an exception or special emphasis is necessary.

When requirements are ambiguous, inspect the implementation first and make a reasonable, conservative decision. Ask the user only when the decision materially changes product behavior or crosses an approval boundary.