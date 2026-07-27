import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as apiModule from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchHealthStatus: vi.fn(),
    fetchProject: vi.fn(),
  };
});

describe('InterfaceForge Frontend Application Shell (S6A.5 UI Stabilization)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
  });

  it('renders skip link, logo, header, navigation, and main H1 heading', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });

    render(<App />);

    expect(screen.getByText('Skip to main content')).toBeInTheDocument();
    expect(screen.getAllByText('Interface')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Forge')[0]).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })
    ).toBeInTheDocument();
  });

  it('displays subtle Mock Mode badge and accurate privacy copy in footer', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });

    render(<App />);

    expect(screen.getByText('Mock Mode')).toBeInTheDocument();
    expect(screen.getByText(/Project state is stored locally by the development backend/i)).toBeInTheDocument();
    expect(screen.getByText(/No user accounts or tracking systems exist/i)).toBeInTheDocument();
  });

  it('displays healthy service status inside collapsible architecture details', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Backend Service Connected & Healthy/i)).toBeInTheDocument();
      expect(screen.getByText('InterfaceForge Backend')).toBeInTheDocument();
    });
  });

  it('recovers safely when sessionStorage contains invalid or malformed project session', async () => {
    sessionStorage.setItem('interfaceforge_project_id', 'invalid-proj-id');
    sessionStorage.setItem('interfaceforge_project_token', 'invalid-token');

    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });
    vi.mocked(apiModule.fetchProject).mockRejectedValue(new Error('[IF-PROJECT-404] Project not found'));

    render(<App />);

    await waitFor(() => {
      expect(sessionStorage.getItem('interfaceforge_project_id')).toBeNull();
      expect(screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })).toBeInTheDocument();
    });
  });
});
