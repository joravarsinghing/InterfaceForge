import { describe, expect, it } from 'vitest';
import type {
  APIEnvelope,
  Project,
  WorkflowState,
} from '../types/schema';

describe('Canonical Design Schema & Contract Verification', () => {
  it('correctly parses and type-guards a valid Project payload', () => {
    const rawBackendPayload = {
      project_id: 'test-uuid-1234',
      project_token: 'tok_abc123xyz',
      schema_version: '0.1',
      state: 'new' as WorkflowState,
      created_at: '2026-07-22T12:00:00Z',
      updated_at: '2026-07-22T12:00:00Z',
      current_schema_revision: 1,
      current_model_revision: null,
      last_known_good_model_revision: null,
      interface_a: {
        id: 'interface_a',
        profile_type: 'circle',
        profile_points: [],
        center: { x: 0, y: 0 },
        dimensions: [
          {
            id: 'outer_dia',
            label: 'Outer Diameter',
            value: 50.0,
            unit: 'mm',
            provenance: 'user_entered',
            confidence: 1.0,
            critical: true,
          },
        ],
        validation: { is_closed: true, self_intersects: false, warnings: [] },
        approved: false,
      },
      interface_b: {
        id: 'interface_b',
        profile_type: 'rectangle',
        profile_points: [],
        center: { x: 0, y: 0 },
        dimensions: [],
        validation: { is_closed: true, self_intersects: false, warnings: [] },
        approved: false,
      },
      connection: {
        mode: 'coaxial',
        length_mm: 100,
        offset_x_mm: 0,
        offset_y_mm: 0,
        angle_deg: 0,
      },
      manufacturing: {
        process: 'fdm',
        material: 'PETG',
        wall_thickness_mm: 2.4,
        clearance_a_mm: 0.3,
        clearance_b_mm: 0.1,
      },
      model_revisions: [],
    };

    const envelope: APIEnvelope<Project> = {
      success: true,
      data: rawBackendPayload as Project,
    };

    expect(envelope.success).toBe(true);
    if (envelope.success) {
      expect(envelope.data.project_id).toBe('test-uuid-1234');
      expect(envelope.data.schema_version).toBe('0.1');
      expect(envelope.data.interface_a.dimensions[0].value).toBe(50.0);
    }
  });

  it('correctly formats API error envelopes matching ADR-013', () => {
    const rawErrorPayload = {
      success: false,
      error: {
        id: 'IF-APPROVAL-400',
        message: 'Interface A must be approved before Interface B can be approved.',
        recovery_steps: ['Approve Interface A first.'],
      },
    };

    const envelope = rawErrorPayload as APIEnvelope<Project>;
    expect(envelope.success).toBe(false);
    if (!envelope.success) {
      expect(envelope.error.id).toBe('IF-APPROVAL-400');
      expect(envelope.error.recovery_steps.length).toBe(1);
    }
  });
});
