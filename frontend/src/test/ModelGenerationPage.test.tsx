import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ModelGenerationPage } from '../pages/ModelGenerationPage';
import { GenerationJob, Project } from '../types/schema';
import * as api from '../services/api';

const mockProject: Project = {
  project_id: 'proj-test-s55',
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

const mockSucceededJob: GenerationJob = {
  job_id: 'job_test_123',
  project_id: 'proj-test-s55',
  model_revision: 1,
  status: 'succeeded',
  current_stage: 'finalizing',
  progress_percent: 100,
  mock_scenario: 'success',
  recovery_steps: [],
  preview_metadata: {
    preview_svg: '<svg><text>Mock Preview</text></svg>',
    bounding_box: { x_mm: 60.0, y_mm: 60.0, z_mm: 50.0 },
    volume_cm3: 34.52,
    facet_count: 1240,
    render_timestamp: '2026-07-23T12:00:00Z',
    is_mock: true,
  },
  created_at: '2026-07-23T12:00:00Z',
  updated_at: '2026-07-23T12:00:00Z',
};

const mockFailedJob: GenerationJob = {
  job_id: 'job_fail_123',
  project_id: 'proj-test-s55',
  model_revision: 1,
  status: 'failed',
  current_stage: 'validating',
  progress_percent: 10,
  mock_scenario: 'engine_validation_failure',
  error_id: 'IF-ENG-001',
  error_message: 'Zoo Engine validation error: KCL lofting surface self-intersects.',
  recovery_steps: ['Adjust connection mode or reduce adapter wall thickness.'],
  created_at: '2026-07-23T12:00:00Z',
  updated_at: '2026-07-23T12:00:00Z',
};

describe('ModelGenerationPage Component (Stage S5.5)', () => {
  it('renders mock engine mode banner, readiness card, and start generation action', async () => {
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

    expect(screen.getByRole('heading', { level: 1, name: /3D Model Generation & Staged Pipeline/i })).toBeInTheDocument();
    expect(screen.getByText(/Running in Mock Engine Mode/i)).toBeInTheDocument();

    await waitFor(() => {

      expect(screen.getByText(/Both Interface A and Interface B are approved/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Start 3D Generation/i })).not.toBeDisabled();
  });

  it('shows the Live Zoo engine notice and hides mock controls in live mode', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    render(
      <BrowserRouter>
        <ModelGenerationPage project={{ ...mockProject, provider_mode: 'live' }} />
      </BrowserRouter>
    );

    expect(await screen.findByText(/Running in Live Zoo Engine Mode/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Mock Test Scenario:/i)).not.toBeInTheDocument();
  });
  it('triggers 3D generation and renders staged progress and preview metadata', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    vi.spyOn(api, 'startGeneration').mockResolvedValue(mockSucceededJob);

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start 3D Generation/i })).not.toBeDisabled();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Start 3D Generation/i }));
    });

    expect(screen.getByRole('heading', { level: 2, name: /Generation Job \[job_test_123\]/i })).toBeInTheDocument();
    expect(screen.getAllByText(/SUCCEEDED/i)[0]).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /Generated 3D Adapter Preview/i })).toBeInTheDocument();
    expect(screen.getByText(/34.52 cm3/i)).toBeInTheDocument();
  });

  it('handles service failure state, recovery steps, and retry trigger', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    vi.spyOn(api, 'startGeneration').mockResolvedValue(mockFailedJob);
    vi.spyOn(api, 'retryGeneration').mockResolvedValue(mockSucceededJob);

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start 3D Generation/i })).not.toBeDisabled();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Start 3D Generation/i }));
    });

    expect(screen.getByText(/Generation Failure Notice \[IF-ENG-001\]/i)).toBeInTheDocument();
    expect(screen.getByText(/KCL lofting surface self-intersects/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry Generation/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Proceed to Review & Export/i })).toBeDisabled();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Retry Generation/i }));
    });

    expect(api.retryGeneration).toHaveBeenCalledWith('proj-test-s55', 'job_fail_123', 'tok_test', 'success');
  });
});
