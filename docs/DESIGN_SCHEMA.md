# Canonical Design Schema

The canonical `Project` JSON is the source of truth. KCL, preview geometry, generation, and exports are derived from the validated project and its persisted `LoftPlan`. Schema version is currently `0.1`.

## Enumerations and defaults

- `WorkflowState`: `new`, `interface_a_uploaded`, `interface_a_review_required`, `interface_a_approved`, `interface_b_uploaded`, `interface_b_review_required`, `interfaces_approved`, `connection_configured`, `generation_in_progress`, `generation_failed`, `model_current`, `model_stale`, `revision_draft`, `export_in_progress`, `export_ready`.
- `ProfileType`: active `circle`, `rectangle`, `rounded_rectangle`, `traced_closed`; `custom_closed` remains compatibility-only.
- `FitMode`: `fit_over` or `fit_inside`.
- `ConnectionMode`: active `coaxial` or `offset`; `angled` is compatibility-only and not submission scope.
- `ManufacturingProcess`: `fdm`, `sla`, or `cnc`.
- `ProviderMode`: `mock` or `live`.
- `ModelRevisionStatus`: `draft`, `generating`, `current`, `stale`, `failed`, `superseded`.

## Project fields

`project_id` and `project_token` are required strings. `display_name` defaults to `Adapter`; `schema_version` defaults to `0.1`; `state` defaults to `new`. Timestamps are ISO-8601 UTC strings. `current_schema_revision` defaults to `1`; `current_model_revision` and `last_known_good_model_revision` are nullable integers. `interface_a` and `interface_b` are required `Interface` objects. `connection`, `manufacturing`, and `model_revisions` have defaults; `loft_plan` is nullable.

## Interface fields

An `Interface` has an ID, optional source/artifact references, profile and resolution fields, `profile_points`, `center`, `dimensions`, `fit_mode`, validation, approval state, calibration, trace metadata, and analysis artifact references. `approved` defaults to false. `ScaleCalibration` stores `point_a`, `point_b`, `pixel_distance`, `real_distance_mm`, `scale_factor`, and `confirmed`. `TracedContour` stores ordered `Point2D` values, `is_closed`, classification, decision, provenance, confidence, and derived `point_count`.

Active final generation requires one approved closed outer profile. `traced_hole_contours` may be retained as analysis metadata but uploaded internal cavities are not active submission geometry.

## Connection, manufacturing, and revisions

`Connection` defaults to length `10.0 mm`, zero X/Y offsets, zero extensions, and zero compatibility `angle_deg`. `Manufacturing` defaults to FDM, PETG, wall thickness `2.4 mm`, and clearances `0.1 mm`.

`ModelRevision` stores integer `model_revision` and `schema_revision`, status, KCL/preview/export artifact references, volume, Zoo model ID, KCL hash, warnings, and timestamp. `ExportReferences` has nullable `stl`, compatibility `step`, and `kcl` references. STEP remains compatibility-only and is not an active submission export.

`LoftPlan` stores `geometry_hash`, `point_count`, `winding`, seam and correspondence shifts, `outer_a`, `outer_b`, `inner_a`, `inner_b`, fit modes, clearances, wall thickness, and ordered `LoftSection` objects. Each section has `z_mm`, `outer`, and `inner` point lists.

## Validation invariants

1. Both interfaces must be approved before connection validation, KCL compilation, or generation.
2. Interface B approval requires Interface A approval.
3. Calibration requires distinct valid points, positive `real_distance_mm`, and explicit confirmation before approval.
4. Traced final profiles require a closed contour with sufficient points and no self-intersection.
5. Active connection modes are coaxial and parallel X/Y offset; compatibility angle values must remain zero.
6. Schema changes stale the current model and exports.
7. Agent proposals are limited to six allowlisted numeric fields and are recalculated server-side.
8. Failed generation preserves `last_known_good_model_revision`.
9. Current exports must match the current model revision and KCL lineage.

## Canonical JSON example

```json
{
  "project_id": "project_demo",
  "project_token": "server-issued-token",
  "display_name": "Dust adapter",
  "provider_mode": "mock",
  "schema_version": "0.1",
  "state": "connection_configured",
  "created_at": "2026-08-04T00:00:00+00:00",
  "updated_at": "2026-08-04T00:00:00+00:00",
  "current_schema_revision": 3,
  "current_model_revision": null,
  "last_known_good_model_revision": null,
  "interface_a": {
    "id": "interface_a",
    "profile_type": "circle",
    "profile_points": [],
    "center": {"x": 0, "y": 0},
    "dimensions": [{"id":"outer_diameter","label":"Outer Diameter","value":50,"unit":"mm","provenance":"user_entered","confidence":1,"critical":true,"feature_ref":"outer_contour","source_annotation":null,"consistency_state":"valid"}],
    "fit_mode": "fit_over",
    "validation": {"is_closed": true, "self_intersects": false, "warnings": []},
    "approved": true,
    "approved_at": "2026-08-04T00:01:00+00:00",
    "scale_calibration": {"source":"inferred","method":"two_point_trace","reference_dimension":"overall_width","point_a":{"x":10,"y":20},"point_b":{"x":110,"y":20},"pixel_distance":100,"real_distance_mm":50,"scale_factor":0.5,"confidence":1,"confirmed":true}
  },
  "interface_b": {
    "id": "interface_b",
    "profile_type": "rounded_rectangle",
    "profile_points": [],
    "center": {"x": 0, "y": 0},
    "dimensions": [],
    "fit_mode": "fit_inside",
    "validation": {"is_closed": true, "self_intersects": false, "warnings": []},
    "approved": true,
    "approved_at": "2026-08-04T00:02:00+00:00",
    "scale_calibration": {"source":"inferred","method":"two_point_trace","reference_dimension":"overall_width","point_a":{"x":12,"y":18},"point_b":{"x":212,"y":18},"pixel_distance":200,"real_distance_mm":100,"scale_factor":0.5,"confidence":1,"confirmed":true}
  },
  "connection": {"mode":"offset","length_mm":40,"offset_x_mm":10,"offset_y_mm":0,"angle_deg":0,"extension_a_mm":0,"extension_b_mm":0},
  "manufacturing": {"process":"fdm","material":"PETG","wall_thickness_mm":2.4,"clearance_a_mm":0.3,"clearance_b_mm":0.1},
  "loft_plan": null,
  "model_revisions": []
}
```
