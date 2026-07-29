import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as apiModule from '../services/api';
import { Project, ProviderModeStatus } from '../types/schema';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchHealthStatus: vi.fn(),
    fetchProject: vi.fn(),
    createProject: vi.fn(),
    fetchProviderModeStatus: vi.fn(),
    validateDefaultProviderMode: vi.fn(),
    updateProviderMode: vi.fn(),
  };
});

const mockProviderStatus: ProviderModeStatus = {
  selected_mode: 'mock',
  effective_mode: 'mock',
  live_available: false,
  engine_provider: 'mock',
  export_provider: 'mock',
  analysis_provider: 'mock',
  agent_provider: 'mock',
  message: 'Mock / offline providers are active for this project.',
};

const liveProviderStatus: ProviderModeStatus = {
  selected_mode: 'live',
  effective_mode: 'live',
  live_available: true,
  engine_provider: 'zoo',
  export_provider: 'zoo',
  analysis_provider: 'gemini',
  agent_provider: 'zoo',
  message: 'Live Zoo providers are active for future generation, export, and Agent requests.',
};

const mockProject: Project = {
  project_id: 'proj-test',
  project_token: 'tok_test',
  display_name: 'Adapter 1',
  provider_mode: 'mock',
  schema_version: '0.1',
  state: 'new',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
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
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: false,
  },
  connection: { mode: 'coaxial', length_mm: 0, offset_x_mm: 0, offset_y_mm: 0, angle_deg: 0 },
  manufacturing: { process: 'fdm', material: 'PETG', wall_thickness_mm: 2.4, clearance_a_mm: 0.3, clearance_b_mm: 0.1 },
  model_revisions: [],
};

function mockHealthyBackend() {
  vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
    service_name: 'InterfaceForge Backend',
    status: 'ok',
    environment: 'development',
    version: '0.1.0',
  });
}

describe('InterfaceForge Frontend Application Shell (S6A.5 UI Stabilization)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
    mockHealthyBackend();
    vi.mocked(apiModule.validateDefaultProviderMode).mockResolvedValue(mockProviderStatus);
    vi.mocked(apiModule.fetchProviderModeStatus).mockResolvedValue(mockProviderStatus);
  });

  it('renders skip link, logo, header, navigation, and main H1 heading', async () => {
    render(<App />);

    expect(screen.getByText('Skip to main content')).toBeInTheDocument();
    expect(screen.getAllByText('Interface')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Forge')[0]).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })
    ).toBeInTheDocument();
  });

  it('displays mock/offline provider status and accurate privacy copy in footer', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('Mock / Offline')).toBeInTheDocument());
    expect(screen.getByRole('group', { name: 'Provider mode' })).toBeInTheDocument();
    expect(screen.getByText(/Project state is stored locally by the development backend/i)).toBeInTheDocument();
    expect(screen.getByText(/No user accounts or tracking systems exist/i)).toBeInTheDocument();
  });

  it('displays healthy service status inside collapsible architecture details', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Runtime Dependencies')).toBeInTheDocument();
      expect(screen.getByText('InterfaceForge backend')).toBeInTheDocument();
    });
  });

  it('recovers safely when sessionStorage contains invalid or malformed project session', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'invalid-proj-id');
    sessionStorage.setItem('interfaceforge_project_token', 'invalid-token');
    vi.mocked(apiModule.fetchProject).mockRejectedValue(new Error('[IF-PROJECT-404] Project not found'));

    render(<App />);

    await waitFor(() => {
      expect(sessionStorage.getItem('interfaceforge_project_id')).toBeNull();
      expect(screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })).toBeInTheDocument();
    });
  });

  it('shows the Mock/Live toggle before project creation with a separate truthful status badge', async () => {
    render(<App />);

    expect(screen.getByRole('group', { name: 'Provider mode' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mock' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Live' })).not.toBeDisabled();
    await waitFor(() => expect(screen.getByText('Mock / Offline')).toHaveAttribute('data-pulse', 'false'));
  });

  it('validates and stores a pre-project Live selection without creating a project', async () => {
    vi.mocked(apiModule.validateDefaultProviderMode).mockImplementation(async (mode) => {
      return mode === 'live' ? liveProviderStatus : mockProviderStatus;
    });

    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Live' }));

    await waitFor(() => expect(apiModule.validateDefaultProviderMode).toHaveBeenCalledWith('live'));
    await waitFor(() => expect(sessionStorage.getItem('interfaceforge_provider_mode')).toBe('live'));
    expect(apiModule.createProject).not.toHaveBeenCalled();
    expect(document.querySelector('.status-live')).toHaveAttribute('data-pulse', 'true');
  });

  it('shows backend rejection before project creation and keeps Mock active', async () => {
    vi.mocked(apiModule.validateDefaultProviderMode).mockImplementation(async (mode) => {
      if (mode === 'live') {
        throw new Error('[IF-PROVIDER-409] Live mode is unavailable because required backend credentials are not configured.');
      }
      return mockProviderStatus;
    });

    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Live' }));

    await waitFor(() => expect(screen.getByText(/IF-PROVIDER-409/)).toBeInTheDocument());
    expect(sessionStorage.getItem('interfaceforge_provider_mode')).toBe('mock');
    expect(screen.getByText('Mock / Offline')).toHaveAttribute('data-pulse', 'false');
    expect(apiModule.createProject).not.toHaveBeenCalled();
  });

  it('creates the next project with the validated pre-project provider mode', async () => {
    vi.mocked(apiModule.validateDefaultProviderMode).mockImplementation(async (mode) => {
      return mode === 'live' ? liveProviderStatus : mockProviderStatus;
    });
    vi.mocked(apiModule.createProject).mockResolvedValue({ ...mockProject, provider_mode: 'live' });
    vi.mocked(apiModule.fetchProviderModeStatus).mockResolvedValue(liveProviderStatus);

    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Live' }));
    await waitFor(() => expect(sessionStorage.getItem('interfaceforge_provider_mode')).toBe('live'));
    fireEvent.click(screen.getByRole('button', { name: /Start New Project/i }));

    await waitFor(() => expect(apiModule.createProject).toHaveBeenCalledWith('live'));
  });

  it('restores a validated pre-project Live preference across refresh', async () => {
    sessionStorage.setItem('interfaceforge_provider_mode', 'live');
    vi.mocked(apiModule.validateDefaultProviderMode).mockResolvedValue(liveProviderStatus);

    render(<App />);

    await waitFor(() => expect(apiModule.validateDefaultProviderMode).toHaveBeenCalledWith('live'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Live' })).toHaveAttribute('aria-pressed', 'true'));
    expect(document.querySelector('.status-live')).toHaveAttribute('data-pulse', 'true');
  });

  it('uses the project-scoped provider-mode endpoint after project hydration', async () => {
    sessionStorage.setItem('interfaceforge_project_id', mockProject.project_id);
    sessionStorage.setItem('interfaceforge_project_token', mockProject.project_token);
    vi.mocked(apiModule.fetchProject).mockResolvedValue(mockProject);
    vi.mocked(apiModule.fetchProviderModeStatus).mockResolvedValueOnce(mockProviderStatus);
    vi.mocked(apiModule.updateProviderMode).mockResolvedValue({
      project: { ...mockProject, provider_mode: 'live' },
      provider_status: liveProviderStatus,
    });

    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Live' }));

    await waitFor(() => {
      expect(apiModule.updateProviderMode).toHaveBeenCalledWith(mockProject.project_id, 'live', mockProject.project_token);
    });
    expect(apiModule.validateDefaultProviderMode).not.toHaveBeenCalledWith('live');
  });
});
