# InterfaceForge — Canonical Design Schema Specification

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Schema Version:** `0.1`  

---

## 1. Overview

Per **ADR-001**, the canonical design schema is the internal source of truth for InterfaceForge. All CAD generation artifacts (such as KCL scripts) are derived deterministically from this validated schema.

---

## 2. Entity Specifications

### 2.1 Project
Container representing an adapter session, versioning metadata, and workflow state.

```json
{
  "project_id": "uuid-v4",
  "project_token": "tok_xyz...",
  "schema_version": "0.1",
  "state": "connection_configured",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC",
  "current_schema_revision": 4,
  "current_model_revision": null,
  "last_known_good_model_revision": null,
  "interface_a": {},
  "interface_b": {},
  "connection": {
    "mode": "coaxial",
    "length_mm": 40.0,
    "offset_x_mm": 0.0,
    "offset_y_mm": 0.0,
    "angle_deg": 0.0
  },
  "manufacturing": {
    "process": "fdm",
    "material": "PETG",
    "wall_thickness_mm": 2.4,
    "clearance_a_mm": 0.3,
    "clearance_b_mm": 0.1
  },
  "model_revisions": []
}
```

### 2.2 Interface
Describes an adapter port interface (Interface A or Interface B).

- **Supported Profile Types:** `circle`, `rectangle`, `rounded_rectangle` (`traced_closed` deferred)
- **Validation:** `is_closed`, `self_intersects`, `warnings`
- **Approval:** `approved`, `approved_at`

### 2.3 Connection & Manufacturing (Stage S4C)
Defines spatial alignment relationship and 3D printing manufacturing rules.

- **Connection Modes:** `coaxial`, `offset`, `angled`
- **Connection Parameters:** `length_mm` (> 0), `offset_x_mm`, `offset_y_mm`, `angle_deg` ([0.0, 45.0])
- **Manufacturing Parameters:** `process` (`fdm`, `sla`, `cnc`), `material`, `wall_thickness_mm` (>= 0.4 mm), `clearance_a_mm` ([0.0, 5.0]), `clearance_b_mm` ([0.0, 5.0])

---

## 3. Validation Rules (Stage S4B & S4C)

### 3.1 Profile Validation Criteria
1. **Supported Profile Type:** Must be one of `circle`, `rectangle`, `rounded_rectangle`.
2. **Minimum Two Known Dimensions:** At least two dimensions must have positive finite values (`> 0`) and provenance other than `unresolved`.
3. **Positive Finite Values:** All dimension parameters must have values strictly greater than 0 and finite numbers (`math.isfinite(val)`).
4. **Valid Confidence Range:** All confidence scores must lie within `[0.0, 1.0]`.
5. **Unresolved Critical Dimensions:** No dimension flagged with `critical: true` may remain `unresolved`.

### 3.2 Connection & Manufacturing Validation Criteria (Stage S4C)
1. **Prerequisite Approval:** Both Interface A and Interface B must be approved (`interface_a.approved == true && interface_b.approved == true`).
2. **Positive Finite Length & Wall:** `length_mm > 0` and `wall_thickness_mm >= 0.4` mm.
3. **Clearance Range:** `clearance_a_mm` and `clearance_b_mm` between `0.0` mm and `5.0` mm.
4. **Angle Limit:** `abs(angle_deg) <= 45.0`°.
5. **Mode Consistency:** Coaxial mode requires `offset_x = 0, offset_y = 0, angle = 0`. Offset mode requires `angle = 0`.
6. **Offset-to-Length Ratio:** $\frac{\text{offset\_dist}}{\text{length}} <= 1.5$.
7. **Self-Intersection Risk:** Total spatial span must not cause loft self-intersection.

---

## 4. Schema Invariants & Revision Rules

1. **Upstream Invalidation:** Editing an approved interface clears its `approved` flag, increments `current_schema_revision`, and marks any `current` model revision as `stale`.
2. **Parameter Edit Staleness:** Modifying connection or manufacturing settings increments `current_schema_revision` and marks any `current` model revision as `stale`.
3. **Last-Known-Good Model Preservation:** If a model generation fails, `last_known_good_model_revision` is preserved untouched.
4. **Current Revision Promotion:** A model revision becomes `current` only upon explicit successful generation completion.
