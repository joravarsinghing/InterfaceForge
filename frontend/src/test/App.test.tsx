import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as apiModule from '../services/api';
import { ProviderModeStatus } from '../types/schema';

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
    expect(screen.getAllByTestId('wordmark')[0]).toHaveTextContent('INTERFACEFORGE');
    expect(
      screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })
    ).toBeInTheDocument();
  });

  it('displays connected backend status and accurate privacy copy in footer', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('Connected')).toBeInTheDocument());
    expect(screen.getByText(/Project state is stored locally by the development backend/i)).toBeInTheDocument();
    expect(screen.getByText(/No user accounts or tracking systems exist/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'GitHub Repository' })).toHaveAttribute('href', 'https://github.com/joravarsinghing/InterfaceForge');
    expect(document.querySelector('img.footer-zoo-logo')).toHaveAttribute('src', '/Zoo.dev.logo.svg');
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
});
