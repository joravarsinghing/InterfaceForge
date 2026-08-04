# Zoo Live Integration Checklist

**Status:** PARTIAL / UNPROVEN live matrix
**Last reviewed:** 2026-08-04

## Credential and environment safety

| Check | Status | Evidence |
|---|---|---|
| `ZOO_API_TOKEN` backend-only | PASS | Configuration and docs keep credentials server-side. |
| Authenticated REST reachability | PASS (prior evidence) | Prior authenticated probes reached Zoo endpoints; this proves reachability/authentication only. |
| Engine live provider selection | UNPROVEN current matrix | Requires credentialed execution in the intended deployment. |
| Agent live provider selection | PARTIAL | Prior credentialed flow succeeded; latest audit was transport-unreliable. |

## Evidence matrix

| Area | Status | Current evidence |
|---|---|---|
| Prior credentialed Zoo Agent integration | PASS (prior) | Bounded proposal and explicit confirm/reject flow completed previously. |
| Latest Agent transport reliability | PARTIAL | 17 of 18 calls timed out or closed during the 2026-08-04 adversarial audit. |
| KCL 2.0 local compilation | PASS (offline) | Current compiler tests pass; not live Zoo proof. |
| Prior STL export | PASS (prior project evidence) | STL export was previously verified. |
| Fresh live STL conversion | BLOCKED | Direct live Engine audit timed out before conversion result. |
| Coaxial live adapter matrix | UNPROVEN | No fresh credentialed result in this audit. |
| X/Y offset live adapter matrix | UNPROVEN | No fresh credentialed result in this audit. |
| Traced profile live matrix | UNPROVEN | No fresh credentialed result in this audit. |
| Angle mode | NOT IN SCOPE | Compatibility-only field; not an active submission capability. |
| STEP export | NOT IN SCOPE | Compatibility-only field/provider; not an active submission output. |

## Interpretation rules

Do not classify timeouts, WebSocket closures, or missing local Zoo tooling as confirmed Zoo bugs without attribution. Do not treat Mock Engine/Agent/export results as live proof. A live PASS requires credentialed execution with recorded request/result evidence and no unsupported scope claims.

## Recovery procedure

For demo or local development, use explicit Mock mode and label it offline evidence. For live failure, preserve the project/last-known-good model, record the sanitized error class and request phase, and retry only through the documented generation/revision flow. Never place credentials in frontend variables, screenshots, or tracked logs.
