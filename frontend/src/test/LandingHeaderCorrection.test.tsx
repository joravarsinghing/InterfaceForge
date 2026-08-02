import { render, screen, fireEvent } from '@testing-library/react';
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
        onRetryHealth={vi.fn()}
      />
    );

    const home = screen.getByLabelText('InterfaceForge Home');
    expect(home.querySelector('img.logo-compact-header')).toHaveAttribute('src', '/InterfaceForge_logo_in.svg');
    expect(home.querySelector('.brand-wordmark')).toBeInTheDocument();
    expect(screen.getByText('Adapter 1')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('renders professional help content with safe links and close control', () => {
    render(<Header healthState={healthState} project={project} onRetryHealth={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Toggle help panel' }));
    expect(screen.getByRole('heading', { name: 'InterfaceForge Help' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'How to use it' })).toBeInTheDocument();
    expect(screen.getByText(/confirm one known measurement/i)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'View portfolio' });
    expect(link).toHaveAttribute('href', 'https://joravarsinghing.github.io/portfolio/');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByRole('link', { name: 'email Joravar' })).toHaveAttribute('href', 'mailto:joravarofficial@outlook.com');
    fireEvent.click(screen.getByRole('button', { name: 'Close Help' }));
    expect(screen.queryByRole('heading', { name: 'InterfaceForge Help' })).not.toBeInTheDocument();
  });

  it('renders centered hero icon and media for both example applications', () => {
    render(
      <MemoryRouter>
        <LandingPage healthState={healthState} onRetryHealth={vi.fn()} />
      </MemoryRouter>
    );

    expect(document.querySelector('.hero-icon')).toHaveAttribute('src', '/InterfaceForge_logo.svg');
    expect(screen.getByRole('img', { name: 'Zoo.dev' })).toHaveAttribute('src', '/Zoo.dev.logo.svg');
    expect(screen.getByRole('link', { name: 'Powered by Zoo.dev' })).toHaveAttribute('href', 'https://zoo.dev/');
    expect(screen.getByRole('img', { name: 'Vacuum Hose Adapter example render' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Vacuum Hose Adapter example animation' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Custom Funnel Adapter example render' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Custom Funnel Adapter example animation' })).toBeInTheDocument();
    expect(document.querySelectorAll('.example-media-split')).toHaveLength(2);
  });
});
