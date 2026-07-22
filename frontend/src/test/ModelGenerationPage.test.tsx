import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ModelGenerationPage } from '../pages/ModelGenerationPage';
import { Project } from '../types/schema';
import * as api from '../services/api';

const mockProject: Project = {
  project_id: 'proj-test-s5a',
  project_token: 'tok_test',
  schema_version: '0.1',
  state: 'connection_configured',
  created_at: '2026-07-23T00:00:00Z',
  updated_at: '2026-07-23T00:00:00Z',
  current_schema_revision: 3,
  current_model_revision: null,
  last_known_good_model_revision: null,
  interface_a: {
    id: 'interface_a',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      { id: 'outer_diameter', label: 'Outer Diameter', value: 50.0, unit: 'mm', provenance: 'user_entered', confidence: 1.0, critical: true }
    ],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: true,
    approved_at: '2026-07-23T00:00:00Z',
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      { id: 'outer_diameter', label: 'Outer Diameter', value: 34.5, unit: 'mm', provenance: 'user_entered', confidence: 1.0, critical: true }
    ],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: true,
    approved_at: '2026-07-23T00:00:00Z',
  },
  connection: {
    mode: 'coaxial',
    length_mm: 40.0,
    offset_x_mm: 0.0,
    offset_y_mm: 0.0,
    angle_deg: 0.0,
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

describe('ModelGenerationPage Component (Stage S5A)', () => {
  it('renders pre-flight readiness card and compile action button', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: /Deterministic KCL Compiler/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /Pre-Flight Readiness Check/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/Both Interface A and Interface B are approved/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Compile Deterministic KCL/i })).not.toBeDisabled();
  });

  it('triggers KCL compilation and renders KCL source snippet and metadata', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    vi.spyOn(api, 'compileKcl').mockResolvedValue({
      success: true,
      kcl_code: '// InterfaceForge — Deterministic KCL Adapter Model\nconst interface_a_outer_diameter_mm = 50.000',
      artifact_ref: 'artifacts/kcl_proj-test_rev3_12345678.kcl',
      compiler_version: '1.0.0',
      schema_revision: 3,
      schema_version: '0.1',
      kcl_hash: '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
      preview_snippet: '// InterfaceForge — Deterministic KCL Adapter Model\nconst interface_a_outer_diameter_mm = 50.000',
      errors: [],
      warnings: [],
    });

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Compile Deterministic KCL/i })).not.toBeDisabled();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Compile Deterministic KCL/i }));
    });

    expect(screen.getByRole('heading', { level: 2, name: /Generated KCL Artifact Metadata/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Draft/i)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/artifacts\/kcl_/i)[0]).toBeInTheDocument();
  });
});
