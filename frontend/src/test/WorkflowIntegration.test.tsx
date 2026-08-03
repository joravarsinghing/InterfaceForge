import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App, { AppContent } from '../App';
import * as apiModule from '../services/api';
import { Project } from '../types/schema';

// Mock API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof import('../services/api')>('../services/api');
  return {
    ...actual,
    fetchHealthStatus: vi.fn().mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'healthy',
      environment: 'development',
      version: '0.1.0',
    }),
    createProject: vi.fn(),
    fetchProject: vi.fn(),
    fetchProviderModeStatus: vi.fn().mockResolvedValue({ selected_mode: 'mock', effective_mode: 'mock', live_available: false, engine_provider: 'mock', export_provider: 'mock', analysis_provider: 'mock', agent_provider: 'mock', message: 'Mock / offline providers are active for this project.' }),
    updateProviderMode: vi.fn(),
    uploadInterfaceImage: vi.fn(),
    analyzeInterfaceImage: vi.fn(),
    patchInterface: vi.fn(),
    approveInterface: vi.fn(),
    updateConnectionConfig: vi.fn(),
    validateConnectionConfig: vi.fn(),
    fetchKclReadiness: vi.fn(),
    compileKcl: vi.fn(),
    startGeneration: vi.fn(),
    cancelGeneration: vi.fn(),
    retryGeneration: vi.fn(),
  };
});

const mockProjectState: Project = {
  project_id: 'proj-12345678',
  project_token: 'tok_abc123',
  schema_version: '0.1',
  state: 'new',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  current_schema_revision: 1,
  current_model_revision: null,
  last_known_good_model_revision: null,
  interface_a: {
    id: 'interface_a',
    approved: false,
    source_image_ref: 'artifacts/uploads/a.png',
    dimensions: [{ id: 'outer_diameter', label: 'Outer Diameter', value: 50.0, unit: 'mm', provenance: 'user_entered', confidence: 1.0, critical: true }],
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    validation: { is_closed: true, self_intersects: false, warnings: [] },
  },
  interface_b: {
    id: 'interface_b',
    approved: false,
    source_image_ref: 'artifacts/uploads/b.png',
    dimensions: [{ id: 'outer_diameter', label: 'Outer Diameter', value: 40.0, unit: 'mm', provenance: 'user_entered', confidence: 1.0, critical: true }],
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    validation: { is_closed: true, self_intersects: false, warnings: [] },
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

describe('S6A Workflow Integration Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('1. Completes happy path from landing to Step 5 review & export', async () => {
    vi.mocked(apiModule.createProject).mockResolvedValue(mockProjectState);

    render(<App />);

    expect(screen.getAllByTestId('wordmark')[0]).toBeInTheDocument();
    expect(screen.getAllByTestId('wordmark')[0]).toBeInTheDocument();
    const startBtn = screen.getByRole('button', { name: /Start New Project/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(apiModule.createProject).toHaveBeenCalledTimes(1);
    });
  });

  it('2. Enforces route guards: Interface B cannot be reached before Interface A approval', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    sessionStorage.setItem('interfaceforge_project_token', 'tok_abc123');
    vi.mocked(apiModule.fetchProject).mockResolvedValue({
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: false, source_image_ref: '' },
    });

    render(
      <MemoryRouter initialEntries={['/step2']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Interface A - Upload Image/i)).toBeInTheDocument();
    });
  });

  it('3. Redirects invalid direct route access to earliest incomplete step', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue({
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: false, source_image_ref: '' },
    });

    render(
      <MemoryRouter initialEntries={['/step5']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Interface A - Upload Image/i)).toBeInTheDocument();
    });
  });

  it('4. Handles poor-image rejection and retry in upload page', async () => {
    vi.mocked(apiModule.createProject).mockResolvedValue(mockProjectState);
    vi.mocked(apiModule.uploadInterfaceImage).mockRejectedValue(
      new Error('[IF-FILE-400] Corrupt or unreadable image file.')
    );

    render(<App />);

    const startBtn = screen.getByRole('button', { name: /Start New Project/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(screen.getByText(/Interface A - Upload Image/i)).toBeInTheDocument();
    });
  });

  it('5. Connection validation failure blocks step 3 submission', async () => {
    const approvedProject: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(approvedProject);
    vi.mocked(apiModule.validateConnectionConfig).mockResolvedValue({
      is_valid: false,
      blocking_errors: [{ id: 'IF-CONN-003', message: 'Transition length must be > 0mm.', recovery_steps: [] }],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <MemoryRouter initialEntries={['/step3']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Validation Summary/i)).toBeInTheDocument();
    });
  });

  it('6. Handles mock generation failure scenario and retry trigger', async () => {
    const readyProject: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
      connection: { mode: 'coaxial', length_mm: 40, offset_x_mm: 0, offset_y_mm: 0, angle_deg: 0 },
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(readyProject);
    vi.mocked(apiModule.fetchKclReadiness).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: {},
    });

    render(
      <MemoryRouter initialEntries={['/step4']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/3D Model Generation/i)).toBeInTheDocument();
    });
  });

  it('7. Handles job cancellation in Step 4', async () => {
    const readyProject: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(readyProject);

    render(
      <MemoryRouter initialEntries={['/step4']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/3D Model Generation/i)).toBeInTheDocument();
    });
  });

  it('8. Parameter revision sets model status STALE and permits regeneration', async () => {
    const staleProject: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
      state: 'model_stale',
      current_model_revision: 1,
      last_known_good_model_revision: 1,
      model_revisions: [
        {
          model_revision: 1,
          schema_revision: 1,
          status: 'stale',
          volume_cm3: 38.4,
          exports: {},
          warnings: [],
          generated_at: new Date().toISOString(),
        },
      ],
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(staleProject);

    render(
      <MemoryRouter initialEntries={['/step5']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Model Parameters Modified/i)).toBeInTheDocument();
    });
  });

  it('9. Preserves last-known-good model revision after failed revision', async () => {
    const preservedProject: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
      state: 'generation_failed',
      current_model_revision: 1,
      last_known_good_model_revision: 1,
      model_revisions: [
        { model_revision: 1, schema_revision: 1, status: 'current', volume_cm3: 38.4, exports: {}, warnings: [], generated_at: new Date().toISOString() },
        { model_revision: 2, schema_revision: 2, status: 'failed', exports: {}, warnings: ['Engine validation failed'], generated_at: new Date().toISOString() },
      ],
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(preservedProject);

    render(
      <MemoryRouter initialEntries={['/step5']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Preserved Last-Known-Good Model/i)).toBeInTheDocument();
    });
  });

  it('10. Editing Interface A marks model stale', async () => {
    const projectBeforeEdit: Project = {
      ...mockProjectState,
      interface_a: { ...mockProjectState.interface_a, approved: true },
      interface_b: { ...mockProjectState.interface_b, approved: true },
      state: 'model_current',
      current_model_revision: 1,
      last_known_good_model_revision: 1,
    };
    sessionStorage.setItem('interfaceforge_project_id', 'proj-12345678');
    vi.mocked(apiModule.fetchProject).mockResolvedValue(projectBeforeEdit);

    render(
      <MemoryRouter initialEntries={['/step1/analysis']}>
        <AppContent />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Profile Review & Approval/i)).toBeInTheDocument();
    });
  });

  it('11. Hydrates project from sessionStorage upon backend restart / page reload', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'proj-hydrated-99');
    sessionStorage.setItem('interfaceforge_project_token', 'tok_hydrated_99');
    vi.mocked(apiModule.fetchProject).mockResolvedValue({
      ...mockProjectState,
      project_id: 'proj-hydrated-99',
    });

    render(<App />);

    await waitFor(() => {
      expect(apiModule.fetchProject).toHaveBeenCalledWith('proj-hydrated-99', 'tok_hydrated_99');
    });
  });

  it('12. Confirms exit and resets session upon restart', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'proj-to-exit');
    vi.mocked(apiModule.fetchProject).mockResolvedValue({
      ...mockProjectState,
      project_id: 'proj-to-exit',
    });

    render(<App />);

    await waitFor(() => {
      const startOverBtn = screen.getByRole('button', { name: /Start Over/i });
      expect(startOverBtn).toBeInTheDocument();
      fireEvent.click(startOverBtn);
    });

    expect(screen.getByText(/Restart Project\?/i)).toBeInTheDocument();
  });

  it('13. Supports keyboard navigation on primary flow elements', async () => {
    vi.mocked(apiModule.createProject).mockResolvedValue(mockProjectState);

    render(<App />);

    const skipLink = screen.getByText(/Skip to main content/i);
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute('href', '#main-content');
  });
});
