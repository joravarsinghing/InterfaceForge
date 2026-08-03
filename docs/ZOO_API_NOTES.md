# Zoo API Integration Notes

**Status:** Active submission notes
**Last reviewed:** 2026-08-03

## Current submission boundary

- Zoo Engine remains the authoritative CAD executor.
- InterfaceForge emits deterministic KCL 2.0 solid-body source from approved project data.
- STL export is verified for the current submission.
- STEP export is not implemented and is out of scope.
- Limited-angle mode is not supported.
- Zoo Agent proposals remain bounded by server-side validation and require explicit user confirmation.
- Live Zoo Agent chat-revision execution was credential-tested and PASSED, including bounded proposals and explicit confirmation/rejection flow.

## Security and provider rules

- Credentials are backend-only and must not appear in logs or generated artifacts.
- The last-known-good model is preserved when generation or export fails.
- Offline mocks and contract tests are not evidence of credentialed live-provider execution.

## Historical notes

Older stage export benchmarks and Boolean-blocker notes are superseded by the current KCL 2.0 solid-body path. They are not evidence for the current submission and are intentionally omitted from this active note.