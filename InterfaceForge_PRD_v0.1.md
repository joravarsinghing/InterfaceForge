# InterfaceForge - Implemented Submission Record

Status: authoritative product record for the current submission build.

## Product summary

InterfaceForge turns two reviewed, clean, front-facing 2D interface images into a hollow parametric transition adapter. The primary use case is a dust-extraction adapter between a circular vacuum-hose opening and a rectangular or rounded-rectangle dust port.

The user uploads Interface A and Interface B, confirms scale with two-point calibration and one known real-world distance for each, reviews and approves each detected profile, configures the connection, validates the project, and explicitly generates through Zoo Engine. The persisted `LoftPlan` is authoritative for preview, deterministic KCL, and final geometry.

## Implemented submission scope

- Two interface profiles per project.
- Clean, front-facing, filled 2D images; OpenCV extracts one closed outer profile.
- Supported profiles: `circle`, `rectangle`, `rounded_rectangle`, and approved arbitrary `traced_closed` profiles.
- Per-interface fit intent: `fit-over` or `fit-inside`.
- Two-point calibration: two selected points plus one known real-world distance.
- Mandatory review and explicit approval of Interface A and Interface B.
- Connection modes: `coaxial` and parallel `offset` using X/Y displacement.
- Length, wall thickness, clearances, X/Y offsets, and interface extensions.
- Canonical project JSON and authoritative `LoftPlan`.
- Deterministic KCL 2.0 solid-body compilation and Zoo Engine execution.
- Bounded Zoo Agent proposals, server-side validation/recalculation, and explicit confirmation.
- STL and KCL exports tied to the current model revision.
- Stale-model/stale-export protection and last-known-good recovery after failed regeneration.
- Project-token authorization, SQLite persistence, and backend-only provider credentials.

## Explicit exclusions

Angle-based connections, internal cavities in uploaded profiles, threads, mounting holes, countersinks, dovetails, undercuts, branches, assemblies, curved centerlines, automatic perspective correction, unrestricted photograph-to-CAD reconstruction, STEP export, and certified or manufacturing-ready output are outside this submission.

## Functional requirements

1. Create a project and receive a project token.
2. Upload and analyze Interface A, calibrate it, review it, and approve it.
3. Keep Interface B locked until Interface A is approved; repeat upload, calibration, review, and approval for B.
4. Configure fit intent, connection mode, length, clearances, wall thickness, offsets, and extensions.
5. Validate prerequisites and explicitly start generation.
6. Compile current canonical data to KCL 2.0 and execute it through the selected Engine provider.
7. Preserve the last-known-good model if generation fails.
8. Offer current STL and KCL only when the model and exports are current.
9. Accept bounded Agent revision requests, show structured before/after changes, and apply them only after confirmation. Confirmation marks the model stale; the user must regenerate separately.

## Non-functional requirements

The backend is FastAPI with Pydantic validation and SQLite persistence. The frontend is deployed to Cloudflare Pages and uses `VITE_BACKEND_URL` to reach the backend deployed to Render. Credentials remain server-side. Errors are truthful, recoverable, and use stable error IDs where established. Generated artifacts remain in ignored runtime storage.

## Evidence boundaries

A prior credentialed Zoo Agent integration flow completed successfully. During the focused 2026-08-04 adversarial audit, 17 of 18 Agent attempts ended in timeout or WebSocket closure. This proves prior integration success while showing transport unreliability during the latest audit window. Prior project evidence verified STL export; the 2026-08-04 direct live Engine audit timed out before a fresh STL conversion result. Offline tests are not live Zoo-provider proof, and transient transport failures are not classified as confirmed Zoo bugs without attribution.

## Success criteria

The submission is successful when a user can complete the approved two-profile workflow, inspect the Zoo-generated result when the selected provider is available, download current STL and KCL, and safely recover from failed generation without losing the last-known-good model. Physical printing is optional validation, not a mandatory definition of done.

## Deferred work

STEP export, richer profile topology, angle-based and curved connections, additional feature families, durable production artifact storage, and stronger live-provider reliability remain future work.

## Current functional requirements

- Accept exactly two project interfaces, Interface A followed by Interface B.
- Require clean, front-facing 2D images and OpenCV extraction of one closed outer profile.
- Require two-point calibration with one known real-world distance and explicit confirmation for each profile.
- Require review and explicit approval before connection configuration or generation.
- Support circle, rectangle, rounded rectangle, and approved `traced_closed` profiles.
- Support `fit-over`, `fit-inside`, coaxial, parallel X/Y offset, length, extensions, wall thickness, and clearances.
- Use the canonical project and persisted LoftPlan for preview, KCL 2.0, and generated geometry.
- Execute KCL through Zoo Engine; constrain Zoo Agent to eight allowlisted numeric fields and explicit confirmation.
- Expose current STL and KCL only for the current model revision.
- Preserve last-known-good state after failed generation or revision regeneration.

## Non-functional requirements

The backend must enforce project-token authorization, keep provider credentials server-side, preserve truthful error IDs and recovery steps, validate and recalculate Agent proposals, avoid silent provider fallback, and keep runtime artifacts outside source control. The frontend is deployed to Cloudflare Pages and the FastAPI backend to Render with SQLite persistence.

## Measurable success criteria

1. A user can complete both upload/calibration/review/approval gates using the supported profile workflow.
2. Invalid calibration, unapproved profiles, unsupported modes, invalid wall/clearance values, and unsafe offsets are rejected with actionable validation errors.
3. The same approved LoftPlan drives preview, deterministic KCL 2.0, and generation inputs.
4. Successful generation records a current model revision and current STL/KCL lineage.
5. Failed generation leaves a prior last-known-good model available.
6. Agent proposals display structured changes, never directly edit KCL or contours, and do not apply until confirmation.
7. Stale upstream changes prevent current export download until regeneration.

## Testing expectations

Focused tests cover project routes, approval/calibration gates, connection validation, contour preparation and correspondence, LoftPlan lineage, KCL compilation, generation recovery, Agent allowlisting, export lineage, and frontend workflow state. Mock-provider tests are offline evidence only. Live Zoo claims require credentialed execution and are reported separately from offline tests.

## Risks and mitigations

- Image distortion or annotations can produce incorrect traces; require prepared images, visible review, calibration, and approval.
- Self-intersection, collapsed passages, and excessive offset can produce unsafe geometry; validate contours, fit offsets, wall thickness, clearances, and offset/length ratio before compilation.
- Provider timeouts can interrupt generation or Agent revisions; preserve jobs and last-known-good revisions, expose recovery actions, and do not call transient failures confirmed provider defects without attribution.
- Render filesystem persistence can be ephemeral; keep artifact storage explicit and do not claim durable production storage.
- Stale exports can be mistaken for current outputs; tie exports to model/schema/KCL lineage and block stale downloads.

## Competition deliverables

The submission demonstrates the two-profile dust-extraction adapter workflow, OpenCV-guided profile extraction and calibration, explicit approval, deterministic KCL 2.0 compilation, Zoo Engine execution when available, bounded Zoo Agent revisions, revision/stale-state safety, and STL/KCL downloads. STEP, physical-print completion, angle-based connections, and certified manufacturing readiness are not required deliverables.
