import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { Header } from '../components/Header';
import { LandingPage } from '../pages/LandingPage';
import { Project } from '../types/schema';

const project: Project = {
  project_id: 'proj-raw-id-1234567890',
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

const healthState = {
  data: { service_name: 'InterfaceForge Backend', status: 'ok', environment: 'test', version: '0.1.0' },
  loading: false,
  error: null,
};

describe('focused landing-page correction pass', () => {
  it('renders compact header icon plus separate wordmark and readable project name', () => {
    render(
      <Header
        healthState={healthState}
        project={project}
        providerStatus={{
          selected_mode: 'mock',
          effective_mode: 'mock',
          live_available: false,
          engine_provider: 'mock',
          export_provider: 'mock',
          analysis_provider: 'mock',
          agent_provider: 'mock',
          message: 'Mock / offline providers are active for this project.',
        }}
        onRetryHealth={vi.fn()}
      />
    );

    const home = screen.getByLabelText('InterfaceForge Home');
    expect(home.querySelector('img.logo-compact-header')).toHaveAttribute('src', '/InterfaceForge_logo_in.svg');
    expect(home.querySelector('.brand-wordmark')).toBeInTheDocument();
    expect(home.querySelector('.wordmark-interface')?.textContent).toBe('Interface');
    expect(home.querySelector('.wordmark-forge')?.textContent).toBe('Forge');
    expect(screen.getByText('Adapter 1')).toBeInTheDocument();
    expect(screen.queryByText(/proj-raw-id/)).not.toBeInTheDocument();
  });

  it('keeps the provider toggle enabled in Mock even when initial live availability is false', () => {
    render(
      <Header
        healthState={healthState}
        project={project}
        providerStatus={{
          selected_mode: 'mock',
          effective_mode: 'mock',
          live_available: false,
          engine_provider: 'mock',
          export_provider: 'mock',
          analysis_provider: 'mock',
          agent_provider: 'mock',
          message: 'Mock / offline providers are active for this project.',
        }}
        onRetryHealth={vi.fn()}
        onProviderModeChange={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Mock' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Live' })).not.toBeDisabled();
  });

  it('calls provider mode change and reports unavailable live without live pulse', async () => {
    const onProviderModeChange = vi.fn();
    render(
      <Header
        healthState={healthState}
        project={project}
        providerStatus={{
          selected_mode: 'mock',
          effective_mode: 'mock',
          live_available: false,
          engine_provider: 'mock',
          export_provider: 'mock',
          analysis_provider: 'mock',
          agent_provider: 'mock',
          message: 'Live mode is unavailable because required backend credentials are not configured.',
        }}
        providerModeError="[IF-PROVIDER-409] Live mode is unavailable because required backend credentials are not configured."
        onRetryHealth={vi.fn()}
        onProviderModeChange={onProviderModeChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Live' }));
    expect(onProviderModeChange).toHaveBeenCalledWith('live');
    expect(screen.getByRole('button', { name: 'Mock' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Live' })).not.toBeDisabled());
    expect(screen.getByText('Mock / Offline')).toHaveAttribute('data-pulse', 'false');
    expect(screen.getByText(/IF-PROVIDER-409/)).toBeInTheDocument();
  });

  it('disables the provider toggle only while a mode-change request is pending', async () => {
    let resolveRequest: () => void = () => undefined;
    const onProviderModeChange = vi.fn(
      () => new Promise<void>((resolve) => {
        resolveRequest = resolve;
      })
    );

    render(
      <Header
        healthState={healthState}
        project={project}
        providerStatus={{
          selected_mode: 'mock',
          effective_mode: 'mock',
          live_available: false,
          engine_provider: 'mock',
          export_provider: 'mock',
          analysis_provider: 'mock',
          agent_provider: 'mock',
          message: 'Mock / offline providers are active for this project.',
        }}
        onRetryHealth={vi.fn()}
        onProviderModeChange={onProviderModeChange}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Live' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Mock' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Checking' })).toBeDisabled();
    });

    resolveRequest();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Mock' })).not.toBeDisabled();
      expect(screen.getByRole('button', { name: 'Live' })).not.toBeDisabled();
    });
  });

  it('shows pulsing live status only when effective mode is live', () => {
    render(
      <Header
        healthState={healthState}
        project={{ ...project, provider_mode: 'live' }}
        providerStatus={{
          selected_mode: 'live',
          effective_mode: 'live',
          live_available: true,
          engine_provider: 'zoo',
          export_provider: 'zoo',
          analysis_provider: 'gemini',
          agent_provider: 'zoo',
          message: 'Live Zoo providers are active.',
        }}
        onRetryHealth={vi.fn()}
        onProviderModeChange={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Live' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.querySelector('.status-live')).toHaveAttribute('data-pulse', 'true');
  });

  it('renders creator help content with safe external portfolio link and close control', () => {
    render(<Header healthState={healthState} project={project} onRetryHealth={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Toggle help panel' }));
    expect(screen.getByRole('heading', { name: 'Created by Joravar Singh' })).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Open Joravar Singh's portfolio/i });
    expect(link).toHaveAttribute('href', 'https://joravarsinghing.github.io/portfolio/');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    fireEvent.click(screen.getByRole('button', { name: 'Close Help' }));
    expect(screen.queryByText(/Created by Joravar Singh/)).not.toBeInTheDocument();
  });

  it('renders centered hero icon and accessible example image placeholders', () => {
    render(
      <MemoryRouter>
        <LandingPage healthState={healthState} onRetryHealth={vi.fn()} />
      </MemoryRouter>
    );

    expect(document.querySelector('.hero-icon')).toHaveAttribute('src', '/InterfaceForge_logo.svg');
    expect(screen.getByRole('img', { name: 'Placeholder for future Vacuum Hose Adapter example image' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Placeholder for future Camera Mount Adapter example image' })).toBeInTheDocument();
  });
});

