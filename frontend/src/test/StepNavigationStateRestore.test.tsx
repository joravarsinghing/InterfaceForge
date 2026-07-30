import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { StepNavigation } from '../components/StepNavigation';
import { getInterfaceStepPath } from '../services/workflow';
import { Project } from '../types/schema';

const baseProject: Project = {
  project_id: 'proj-nav',
  project_token: 'tok-nav',
  schema_version: '0.1',
  state: 'new',
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
  current_schema_revision: 1,
  current_model_revision: null,
  last_known_good_model_revision: null,
  interface_a: {
    id: 'interface_a',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: false,
    source_image_ref: null,
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: false,
    source_image_ref: null,
  },
  connection: { mode: 'coaxial', length_mm: 0, offset_x_mm: 0, offset_y_mm: 0, angle_deg: 0 },
  manufacturing: { process: 'fdm', material: 'PETG', wall_thickness_mm: 2.4, clearance_a_mm: 0.3, clearance_b_mm: 0.1 },
  model_revisions: [],
};

describe('interface step route resolution', () => {
  it('opens upload only when the interface has no saved image or approval', () => {
    expect(getInterfaceStepPath(baseProject, 'interface_a')).toBe('/step1');
    expect(getInterfaceStepPath(baseProject, 'interface_b')).toBe('/step2');
  });

  it('opens review for uploaded but unapproved interfaces', () => {
    const project: Project = {
      ...baseProject,
      interface_a: { ...baseProject.interface_a, source_image_ref: 'artifacts/uploads/a.png' },
      interface_b: { ...baseProject.interface_b, source_image_ref: 'artifacts/uploads/b.png' },
    };

    expect(getInterfaceStepPath(project, 'interface_a')).toBe('/step1/analysis');
    expect(getInterfaceStepPath(project, 'interface_b')).toBe('/step2/analysis');
  });

  it('opens review for approved interfaces without changing saved state', () => {
    const project: Project = {
      ...baseProject,
      interface_a: { ...baseProject.interface_a, approved: true, source_image_ref: 'artifacts/uploads/a.png' },
      interface_b: { ...baseProject.interface_b, approved: true, source_image_ref: 'artifacts/uploads/b.png' },
    };

    expect(getInterfaceStepPath(project, 'interface_a')).toBe('/step1/analysis');
    expect(getInterfaceStepPath(project, 'interface_b')).toBe('/step2/analysis');
    expect(project.interface_a.approved).toBe(true);
    expect(project.interface_b.approved).toBe(true);
    expect(project.interface_a.source_image_ref).toBe('artifacts/uploads/a.png');
    expect(project.interface_b.source_image_ref).toBe('artifacts/uploads/b.png');
  });

  it('locks Step 5 when only a failed model revision exists', () => {
    const failedProject: Project = {
      ...baseProject,
      state: 'generation_failed',
      interface_a: { ...baseProject.interface_a, approved: true },
      interface_b: { ...baseProject.interface_b, approved: true },
      connection: { ...baseProject.connection, length_mm: 40 },
      model_revisions: [{
        model_revision: 1,
        schema_revision: 1,
        status: 'failed',
        exports: {},
        warnings: ['compiler failed'],
        generated_at: '2026-07-29T00:00:00Z',
      }],
    };

    render(
      <MemoryRouter initialEntries={['/step4']}>
        <StepNavigation project={failedProject} />
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: /Review & Export/i })).not.toBeInTheDocument();
    expect(screen.getByText('Review & Export').closest('.step-link')).toHaveAttribute('aria-disabled', 'true');
  });

  it('uses restored project state for top-step links after hydration', () => {
    const restoredProject: Project = {
      ...baseProject,
      state: 'interfaces_approved',
      interface_a: { ...baseProject.interface_a, approved: true, source_image_ref: 'artifacts/uploads/a.png' },
      interface_b: { ...baseProject.interface_b, approved: true, source_image_ref: 'artifacts/uploads/b.png' },
      connection: { ...baseProject.connection, length_mm: 45 },
    };

    render(
      <MemoryRouter initialEntries={['/step3']}>
        <StepNavigation project={restoredProject} />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /Interface A Capture/i })).toHaveAttribute('href', '/step1/analysis');
    expect(screen.getByRole('link', { name: /Interface B Capture/i })).toHaveAttribute('href', '/step2/analysis');
  });
});
