# InterfaceForge - Bugs and Limitations

**Document status:** Active sanitized audit record
**Last reviewed:** 2026-08-04
**Project:** InterfaceForge (Zoo API Makeathon 2026)
**Last reviewed:** 2026-08-04

## Test environment

- **Test date:** 2026-08-04.
- **Commit under test:** `ae5af82db52ee97568ee17cf3b5e5bdc3f549b77`.
- **Runtime:** Python 3.14.6 from `venv314`; repository `pyproject.toml` targets Python 3.14.
- **Zoo paths used:** `https://api.zoo.dev/user`, `https://api.zoo.dev/`, `wss://api.zoo.dev/ws/ml/copilot`, and the InterfaceForge `ZooEngineProvider` / `ZooExportProvider` paths.
- **Credential status:** Credentialed for authenticated REST probes and Agent attempts. The token was never written to evidence or output. Engine/export settings defaulted to `mock`; live providers were invoked directly for the audit.
- **Test matrix:** 30 focused offline regression tests; 3 current KCL compiler fixtures; 2 authenticated REST probes; 18 live Agent prompts; 1 current-KCL Engine probe; 1 STL export probe.
- **Sanitized evidence:** `tmp/zoo_agent_live_20260804.json` contains the 18 Agent request prompts and redacted result envelopes. The current KCL fixture is `tmp/zoo_api_audit_current.kcl`. These paths are ignored scratch artifacts and are not production outputs.

The official Zoo documentation describes REST endpoints with bearer authentication, WebSocket application protocols, KCL export formats including STL, and the Agent WebSocket at `wss://api.zoo.dev/ws/ml/copilot`: [API overview](https://docs.zoo.dev/docs/developer-tools/api), [KCL export](https://zoo.dev/docs/developer-tools/cli/manual/zoo_kcl_export), [Agent API](https://zoo.dev/docs/developer-tools/agent-api), and [Agent WebSocket](https://docs.zoo.dev/docs/developer-tools/api/ml/open-a-websocket-to-prompt-the-ml-copilot).

## Confirmed Zoo bugs

No confirmed Zoo bugs were found in this audit.

No finding met all four requirements for a Zoo bug: current documented behavior, reproducibility, distinguishable expected/actual results, and evidence excluding InterfaceForge as the cause. Timeouts, WebSocket service-restart closes, and missing local KCL tooling were therefore not reported as Zoo defects.

## Zoo developer-experience observations

These observations do not meet the Zoo bug threshold.

### Developer experience observation - Agent transport failures lack actionable detail

- **Observed:** 17 of 18 live Agent prompts returned an `IF-AGENT-500` envelope after timeout or WebSocket close. Several exception strings were empty; two reported WebSocket close code 1012 (service restart).
- **Why it matters:** The caller cannot distinguish connection refusal, idle timeout, service restart, and malformed stream termination from the returned message alone.
- **Suggested improvement:** Provide a stable transport error category, close code/reason, server request ID, and whether any response frames were received. Document retry guidance and idempotency for interrupted Agent requests.

### Improvement suggestion - Document the structured Agent contract independently of prose examples

The public Agent documentation describes the Agent broadly, while InterfaceForge relies on a narrow JSON proposal contract. A versioned schema example for bounded parameter revisions, explicit unsupported-request behavior, units, and malformed-output handling would reduce integration ambiguity. This is a documentation/contract suggestion, not a confirmed defect.

### Developer experience observation - Line-level KCL diagnostics are not consistently surfaced by the integration

The KCL runtime can identify a source line and column, but the InterfaceForge provider wraps some parser/runtime failures into a broad `IF-ENG-001` message. A stable error category with source span, phase (`parse`, `model`, or `export`), and request ID would make debugging easier. This observation is about the integration boundary and does not establish a Zoo failure.

## InterfaceForge limitations

1. Reliable input is a clean, front-facing, filled 2D profile image. Image tracing, calibration, perspective handling, profile cleanup, and annotation-heavy drawing handling remain InterfaceForge concerns and limitations.
2. Scale is manually calibrated from a known measurement and must be explicitly confirmed. Perspective correction is not automatic.
3. Dimensioned engineering drawings are experimental/manual-review inputs; users must inspect and approve the traced profile.
4. Final generation supports the bounded profile and connection scope implemented by InterfaceForge. Angle-based connections are unsupported for this submission.
5. Internal cavities, threads, mounting holes, countersinks, dovetails, undercuts, multi-depth interfaces, and certified manufacturing readiness are outside the current product scope.
6. STEP export is not implemented for this submission.
7. Generated adapters are user-reviewed engineering candidates and require inspection before manufacturing.

## InterfaceForge defects observed during this audit

### Current live Engine timeout is not returned as a normal job result

The current KCL fixture compiled successfully with the InterfaceForge compiler. When the direct `ZooEngineProvider` live path executed it, the 30-second `execute_code_and_export` timeout propagated as `asyncio.TimeoutError` instead of being converted into the provider's documented `IF-ENG-002` failed-job envelope. This is an InterfaceForge provider/orchestration defect observed during the audit, not a Zoo bug. No production code was changed in this task.

The live STL probe consequently did not reach a conversion result. The local runtime also has neither the importable `zoo_kcl` package nor a `zoo` CLI, so conversion success, repeated output equivalence, facet counts, bounds, and conversion-vs-model error separation remain unproven here.

## Resolved InterfaceForge defects

### Deprecated KCL/sketch syntax - resolved

An earlier InterfaceForge artifact emitted deprecated KCL syntax (`const` declarations and deprecated sketch-era constructs). The current compiler emits current KCL 2.0 syntax and the current compiler fixture compiled successfully. The earlier failure was caused by InterfaceForge emitting outdated syntax, not by a confirmed Zoo Boolean, loft, or solid-generation defect.

## Evidence boundaries

- **Credential-tested:** Authenticated REST probes to `/user` and `/`; live Agent WebSocket attempts; direct live Engine and STL-provider calls.
- **Repeated:** 30 offline regression tests; 18 distinct Agent prompts. The Agent transport failures were not repeated three times per prompt because the first batch already showed widespread timeout/service-restart behavior and further calls would add cost without improving attribution.
- **Offline only:** Current KCL compilation and the existing provider regression suite. These do not prove Zoo Engine geometry behavior.
- **Not proven:** Current Zoo Engine loft/subtraction behavior across the requested geometry matrix; deterministic live STL conversion; malformed-KCL and unsupported-geometry diagnostics from the live Engine; timeout/connection-close semantics at the Zoo service; and the requested three-repeat Agent consistency checks.
- **Cannot generalize:** One authenticated REST success proves reachability/authentication only. Agent model interpretation variability is not a Zoo API defect unless a documented structured-output guarantee is violated. No raw credentials, authorization headers, private IDs, or request IDs are retained in the permanent report.

## Evidence reconciliation for Prompt 2

- **Verified live behavior:** A prior credentialed Zoo Agent integration flow completed successfully, including bounded proposals and explicit confirmation/rejection behavior. Prior project evidence also verified STL export.
- **Latest live observation:** During the focused 2026-08-04 adversarial audit, 17 of 18 Agent calls timed out or closed their WebSocket. The direct live Engine audit timed out before a fresh STL conversion result.
- **Transient/inconclusive:** Agent transport timeouts, WebSocket closures, and the Engine timeout do not establish a confirmed Zoo bug.
- **InterfaceForge defect:** The current live Engine timeout was observed propagating as `asyncio.TimeoutError` rather than the intended `IF-ENG-002` job envelope. This is an InterfaceForge orchestration issue.
- **Offline-only:** Local compiler, geometry, mock provider, and regression tests do not prove live Zoo behavior.
- **Permanent evidence hygiene:** Raw credentials, authorization headers, private IDs, and sensitive logs are not retained in tracked documentation.
