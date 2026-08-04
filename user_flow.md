# InterfaceForge - Implemented User Flow

This document describes the current submission workflow. `Interface A` and `Interface B` are the only two profiles in a project.

## Locked workflow

1. Create a project. The backend returns a project ID and project token; the frontend keeps the token and sends it as `X-Project-Token`.
2. Upload Interface A as a clean, front-facing, filled 2D image. OpenCV produces the processed image, trace artifacts, and one closed outer profile.
3. Select two calibration points, enter one known real-world distance, and confirm the two-point calibration. Calibration applies scale only; it does not correct perspective.
4. Review the detected profile, dimensions, trace, fit intent, and warnings. Explicitly approve Interface A.
5. Interface B remains locked until A is approved. Upload, calibrate, review, and explicitly approve B using the same process.
6. Configure `fit-over` or `fit-inside`, `coaxial` or `offset`, transition length, wall thickness, clearances, X/Y offsets, and interface extensions.
7. Validate the project and inspect the returned validation issues and preview `LoftPlan`.
8. Explicitly start model generation. The server validates readiness, compiles deterministic KCL 2.0 from the authoritative `LoftPlan`, and invokes the selected Engine provider.
9. Poll the generation job and inspect the generated result. A failed job leaves the previous successful revision available as last-known-good.
10. Generate or inspect current exports, then download STL and KCL. STEP is not an implemented submission export.
11. Enter a Zoo Agent revision request. The Agent may propose only bounded changes to length, X/Y offsets, wall thickness, and clearances.
12. Review the structured proposal and explicitly confirm or reject it. Confirmation updates canonical values and marks the model stale; it does not launch generation.
13. Regenerate explicitly when required, inspect the new result, and download revision-current STL and KCL.

## Validation and rejection states

Uploads can be rejected for invalid image content or missing artifacts. Calibration requires two distinct valid points and a positive known distance. Approval requires a valid analyzed profile, confirmed scale, and a closed outer contour; B approval also requires A approval. Connection validation requires both approvals, a positive length, valid clearances/wall thickness, and a supported mode. Angle-based connections and internal cavities are unsupported.

Agent proposals are rejected when they request unsupported fields, duplicate fields, invalid values, or changes outside server-side bounds. The server uses trusted project values and recalculates resulting values; it does not trust arbitrary Agent output or permit direct KCL edits.

## Stale state and recovery

Editing an approved profile, calibration, connection, or manufacturing value invalidates downstream approval/model/export state. Existing exports are stale until regenerated. Failed generation marks the attempted revision failed and restores `current_model_revision` to `last_known_good_model_revision` when one exists. Retry uses the generation retry endpoint. A stale project is not silently exported as current.

## Restoration and authorization

Project state is restored from the backend by project ID plus project token. Generation jobs are resumable through the active/status endpoints. Browser image downloads may use the token query parameter because image elements cannot add the authorization header. Missing or invalid tokens do not expose project data.

## Provider boundary

OpenCV is the deterministic profile extraction path. Gemini is optional guidance only when explicitly configured; it does not author final geometry. Zoo Engine is the authoritative live CAD executor. Zoo Agent proposes bounded revisions. Mock providers exist for explicit offline development/testing and are not live-provider evidence. Credentials are never sent to the frontend.

## Secondary recovery and rejection flows

- Invalid token or project: the backend returns `IF-AUTH-401` or `IF-PROJECT-404`; the frontend keeps the user on a safe error state and offers restart rather than exposing project data.
- Invalid upload: reject unsupported/empty/unsafe files with a recoverable upload error; preserve the existing project state.
- Failed detection or calibration: show analysis/calibration errors, keep the prior valid interface data, and allow re-upload, re-analysis, or recalibration.
- Approval retry: approval remains blocked until the profile is closed, calibrated, reviewed, and valid; correcting the profile clears downstream approval as implemented.
- Blocked navigation: route guards redirect direct access to the earliest incomplete workflow step. Interface B and configuration remain locked until prerequisites are met.
- Invalid configuration: display field-level validation IDs and recovery steps; do not compile or start generation.
- Agent timeout or unsupported request: show a provider/validation error, leave canonical data and the current model unchanged, and allow a new request or explicit Mock test request.
- Generation failure: mark the attempted revision failed, preserve `last-known-good`, and expose retry/status/recovery actions.
- Export failure or stale model: block the affected download, expose per-format status/retry, and require regeneration after upstream changes.
- Resume/restore: reload the project through project ID plus project token; use active generation status to resume a job after refresh.

## Verified accessibility behavior

The implemented frontend provides labeled workflow navigation, visible form labels, keyboard-reachable controls, focus-managed error boundaries/dialogs where present, and text alternatives for profile/geometry review. Visual or full assistive-technology compliance is not claimed without manual verification.
