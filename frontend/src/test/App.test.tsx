import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as apiModule from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchHealthStatus: vi.fn(),
  };
});

describe('InterfaceForge Frontend Application Shell', () => {
  beforeEach(() => {
    vi.resetAllMocks();
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
    expect(screen.getByText('InterfaceForge')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 1, name: /Two interfaces in\. One adapter out\./i })
    ).toBeInTheDocument();
  });

  it('clearly states that image upload and mock analysis are active', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });

    render(<App />);

    expect(screen.getByText(/Image Upload & Mock Analysis Active/i)).toBeInTheDocument();
  });


  it('displays healthy service status when health check succeeds', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
      service_name: 'InterfaceForge Backend',
      status: 'ok',
      environment: 'development',
      version: '0.1.0',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Backend Service Connected & Healthy')).toBeInTheDocument();
      expect(screen.getByText('InterfaceForge Backend')).toBeInTheDocument();
    });
  });

  it('displays backend unavailable state when health check fails', async () => {
    vi.mocked(apiModule.fetchHealthStatus).mockRejectedValue(
      new Error('Failed to fetch backend health')
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Backend Service Unavailable')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch backend health/i)).toBeInTheDocument();
    });
  });
});
