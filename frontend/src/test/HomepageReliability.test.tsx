import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  fetchKclReadiness: vi.fn(),
 };
});

const providerStatus: ProviderModeStatus = {
 selected_mode: 'mock',
 effective_mode: 'mock',
 live_available: false,
 engine_provider: 'mock',
 export_provider: 'mock',
 analysis_provider: 'mock',
 agent_provider: 'mock',
 message: 'Mock / offline providers are active for this project.',
};

const baseProject: Project = {
 project_id: 'proj-existing',
 project_token: 'tok_existing',
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

const connectionConfiguredProject: Project = {
 ...baseProject,
 state: 'connection_configured',
 interface_a: { ...baseProject.interface_a, approved: true },
 interface_b: { ...baseProject.interface_b, approved: true },
 connection: { mode: 'coaxial', length_mm: 40, offset_x_mm: 0, offset_y_mm: 0, angle_deg: 0 },
};

function mockHealth() {
 vi.mocked(apiModule.fetchHealthStatus).mockResolvedValue({
  service_name: 'InterfaceForge Backend',
  status: 'ok',
  environment: 'test',
  version: '0.1.0',
  services: [
   { id: 'backend', label: 'InterfaceForge backend', status: 'Available', message: 'Backend API is responding.' },
   { id: 'gemini_vision', label: 'Gemini Vision', status: 'Not configured', message: 'Gemini API key is not configured.', model: 'gemini-3.5-flash-lite' },
   { id: 'openrouter_vision', label: 'OpenRouter Vision fallback', status: 'Unavailable', message: 'OpenRouter check failed.', model: 'model-a / model-b' },
   { id: 'zoo_engine', label: 'Zoo Authentication', status: 'Available', message: 'Authenticated Zoo API probe succeeded.' },
   { id: 'persistence', label: 'Project persistence/storage', status: 'Available', message: 'SQLite storage is reachable.' },
  ],
 });
}

describe('homepage reliability pass', () => {
 beforeEach(() => {
  window.history.pushState({}, '', '/');
  vi.resetAllMocks();
  sessionStorage.clear();
  mockHealth();
  vi.mocked(apiModule.validateDefaultProviderMode).mockResolvedValue(providerStatus);
  vi.mocked(apiModule.fetchProviderModeStatus).mockResolvedValue(providerStatus);
  vi.mocked(apiModule.fetchKclReadiness).mockResolvedValue({
   is_valid: true,
   blocking_errors: [],
   warnings: [],
   recommended_values: {},
  });
 });

 it('renders homepage text without mojibake or replacement characters', async () => {
  const { container } = render(<App />);

  await waitFor(() => expect(screen.getByText('Runtime Dependencies')).toBeInTheDocument());
  expect(container.textContent).not.toMatch(new RegExp('[\\u00e2\\u00c3\\u00f0\\ufffd]'));
 });

 it('continues an existing project to the backend-derived current workflow step', async () => {
  sessionStorage.setItem('interfaceforge_project_id', connectionConfiguredProject.project_id);
  sessionStorage.setItem('interfaceforge_project_token', connectionConfiguredProject.project_token);
  vi.mocked(apiModule.fetchProject).mockResolvedValue(connectionConfiguredProject);

  render(<App />);

  fireEvent.click(await screen.findByRole('button', { name: 'Continue Project' }));

  await waitFor(() => expect(apiModule.fetchProject).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByText(/3D Model Generation/i)).toBeInTheDocument());
 });

 it('cancels new-project confirmation without creating or overwriting project state', async () => {
  sessionStorage.setItem('interfaceforge_project_id', baseProject.project_id);
  sessionStorage.setItem('interfaceforge_project_token', baseProject.project_token);
  vi.mocked(apiModule.fetchProject).mockResolvedValue(baseProject);

  render(<App />);

  await screen.findByRole('button', { name: 'Continue Project' });
  fireEvent.click(screen.getByRole('button', { name: 'Start New Project' }));
  const dialog = await screen.findByRole('dialog', { name: 'Start New Project?' });
  expect(dialog).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(apiModule.createProject).not.toHaveBeenCalled();
  expect(sessionStorage.getItem('interfaceforge_project_id')).toBe(baseProject.project_id);
 });

 it('creates a separate new project after confirmation and preserves the previous backend project', async () => {
  const newProject = { ...baseProject, project_id: 'proj-new', project_token: 'tok_new', display_name: 'Adapter 2' };
  sessionStorage.setItem('interfaceforge_project_id', baseProject.project_id);
  sessionStorage.setItem('interfaceforge_project_token', baseProject.project_token);
  vi.mocked(apiModule.fetchProject).mockResolvedValue(baseProject);
  vi.mocked(apiModule.createProject).mockResolvedValue(newProject);
  vi.mocked(apiModule.fetchProviderModeStatus).mockResolvedValue(providerStatus);

  render(<App />);

  await screen.findByRole('button', { name: 'Continue Project' });
  fireEvent.click(screen.getByRole('button', { name: 'Start New Project' }));
  const dialog = await screen.findByRole('dialog', { name: 'Start New Project?' });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Start New Project' }));

  await waitFor(() => expect(apiModule.createProject).toHaveBeenCalledWith('mock'));
  expect(apiModule.fetchProject).toHaveBeenCalledWith(baseProject.project_id, baseProject.project_token);
  expect(sessionStorage.getItem('interfaceforge_project_id')).toBe(newProject.project_id);
 });

 it('renders independent service-status states and refresh action', async () => {
  render(<App />);

  await waitFor(() => expect(screen.getByText('Gemini Vision')).toBeInTheDocument());
  expect(screen.getByText('OpenRouter Vision fallback')).toBeInTheDocument();
  expect(screen.getByText('Zoo Authentication')).toBeInTheDocument();
  expect(screen.getByText('Project persistence/storage')).toBeInTheDocument();
  expect(screen.getByText('Not configured')).toBeInTheDocument();
  expect(screen.getByText('Unavailable')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh Status' }));
  expect(apiModule.fetchHealthStatus).toHaveBeenCalledTimes(2);
 });
});



