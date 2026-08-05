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

const mockRunningJob: GenerationJob = {
  ...mockSucceededJob,
  status: 'running',
  current_stage: 'executing',
  progress_percent: 42,
  preview_metadata: undefined,
};
const mockRecoveredJob: GenerationJob = {
  ...mockRunningJob,
  status: 'failed',
  error_id: 'IF-JOB-RESTARTED',
  error_message: 'Generation was interrupted because the backend restarted. Your last successful model is still available. Please try again.',
  recovery_steps: ['Retry model generation when the backend is available.'],
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
  it('renders readiness card and start generation action', async () => {
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

    await waitFor(() => {
      expect(screen.getByText(/Both Interface A and Interface B are approved/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Start 3D Generation/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /Proceed to Review & Export/i })).toBeDisabled();
  });

  it('shows Regenerate 3D Model when a prior revision is stale', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    const staleProject: Project = {
      ...mockProject,
      state: 'model_stale',
      current_model_revision: 1,
      last_known_good_model_revision: 1,
      model_revisions: [{
        model_revision: 1,
        schema_revision: 1,
        status: 'stale',
        exports: {},
        warnings: [],
        generated_at: '2026-07-23T12:00:00Z',
      }],
    };

    render(
      <BrowserRouter>
        <ModelGenerationPage project={staleProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Regenerate 3D Model' })).not.toBeDisabled();
    });
  });

  it('hides mock controls in live mode', async () => {
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

    expect(screen.queryByLabelText(/Mock Test Scenario:/i)).not.toBeInTheDocument();
  });
  it('shows percentage progress and a rotating Zoo loading dialogue while the job runs', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });
    vi.spyOn(api, 'startGeneration').mockResolvedValue(mockRunningJob);

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

    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText(/While Zoo is thinking:/i)).toBeInTheDocument();
    expect(screen.getByText(/AI-native CAD platform/i)).toBeInTheDocument();
  });
  it('shows a loading animation while KCL generation is pending', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });
    let resolveCompile: ((value: any) => void) | undefined;
    vi.spyOn(api, 'compileKcl').mockReturnValue(new Promise((resolve) => { resolveCompile = resolve; }));

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Inspect KCL Code \(optional\)/i })).not.toBeDisabled();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Inspect KCL Code \(optional\)/i }));
    });

    expect(screen.getByTestId('step4-action-loading')).toHaveTextContent(/Generating KCL code. Please wait/i);
    await act(async () => {
      resolveCompile?.({ success: false, errors: [], warnings: [] });
    });
  });

  it('shows a loading animation while 3D generation is starting', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });
    let resolveGeneration: ((value: GenerationJob) => void) | undefined;
    vi.spyOn(api, 'startGeneration').mockReturnValue(new Promise((resolve) => { resolveGeneration = resolve; }));

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

    expect(screen.getByTestId('step4-action-loading')).toHaveTextContent(/Starting 3D model generation. Please wait/i);
    await act(async () => {
      resolveGeneration?.(mockRunningJob);
    });
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
    expect(screen.getByRole('button', { name: /Start 3D Generation/i })).toHaveClass('step4-generated-button');
    expect(screen.getByRole('button', { name: /Proceed to Review & Export/i })).not.toBeDisabled();
  });

  it('does not render the removed Zoo Design Studio download link after compilation', async () => {
    vi.spyOn(api, 'fetchKclReadiness').mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });
    vi.spyOn(api, 'compileKcl').mockResolvedValue({
      success: true,
      compiler_version: '0.1.0',
      schema_revision: 3,
      schema_version: '0.1',
      artifact_ref: 'artifacts/adapter.kcl',
      kcl_hash: 'abc123hash4567890',
      kcl_code: 'fn main() {}',
      preview_snippet: 'fn main() {}',
      errors: [],
      warnings: [],
    });

    render(
      <BrowserRouter>
        <ModelGenerationPage project={mockProject} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Inspect KCL Code \(optional\)/i })).not.toBeDisabled();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Inspect KCL Code \(optional\)/i }));
    });

    expect(screen.queryByRole('link', { name: /Download Zoo Design Studio \| Zoo/i })).not.toBeInTheDocument();
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
  it('exits progress polling and shows restart recovery', async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "fetchKclReadiness").mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });
    vi.spyOn(api, "fetchActiveGeneration").mockResolvedValue(mockRunningJob);
    vi.spyOn(api, "fetchGenerationStatus").mockResolvedValue(mockRecoveredJob);

    try {
      render(
        <BrowserRouter>
          <ModelGenerationPage project={mockProject} />
        </BrowserRouter>
      );
      await act(async () => { await Promise.resolve(); });
      await act(async () => {
        vi.advanceTimersByTime(2000);
        await Promise.resolve();
      });
      expect(screen.getByText(/Generation Failure Notice \[IF-JOB-RESTARTED\]/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Retry Generation/i })).toBeInTheDocument();
      expect(screen.queryByText(/Zoo Engine generation progress/i)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

});
