import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ConnectionConfigPage } from '../pages/ConnectionConfigPage';
import { Project } from '../types/schema';
import * as api from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    validateConnectionConfig: vi.fn(),
    updateConnectionConfig: vi.fn(),
    patchInterface: vi.fn(),
  };
});

const mockApprovedProject: Project = {
  project_id: 'proj_123',
  project_token: 'tok_abc',
  schema_version: '0.1',
  state: 'interfaces_approved',
  created_at: '2026-07-23T00:00:00Z',
  updated_at: '2026-07-23T00:00:00Z',
  current_schema_revision: 2,
  interface_a: {
    id: 'interface_a',
    profile_type: 'circle',
    fit_mode: 'fit_over',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      {
        id: 'outer_diameter',
        label: 'Outer Diameter',
        value: 50.0,
        unit: 'mm',
        provenance: 'user_entered',
        confidence: 1.0,
        critical: true,
      },
    ],
    validation: { is_closed: true, self_intersects: false, warnings: [] },
    approved: true,
    approved_at: '2026-07-23T00:00:00Z',
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'rectangle',
    fit_mode: 'fit_over',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      {
        id: 'width',
        label: 'Width',
        value: 40.0,
        unit: 'mm',
        provenance: 'user_entered',
        confidence: 1.0,
        critical: true,
      },
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

describe('ConnectionConfigPage Component (Stage S4C)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders interface summary bar and connection mode cards', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Step 3 - Guided Connection/i)).toBeInTheDocument();
    expect(screen.getByText(/Interface A:/i)).toBeInTheDocument();
    expect(screen.getByText(/Interface B:/i)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Coaxial/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Parallel Offset/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Limited Angle/i })).toBeInTheDocument();
    expect(screen.getAllByText('Fit over the outside').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Fit inside the opening').length).toBeGreaterThan(0);
  });

  it('switches mode and updates active fields for Offset and Angled modes', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    // Initial Coaxial mode: X/Y offset and Angle fields not visible
    expect(screen.queryByLabelText(/X Offset/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Transition Angle/i)).not.toBeInTheDocument();

    // Select Offset Mode
    fireEvent.click(screen.getByRole('radio', { name: /Parallel Offset/i }));
    expect(screen.getByLabelText(/X Offset/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Y Offset/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Transition Angle/i)).not.toBeInTheDocument();

    // Select Angled Mode
    fireEvent.click(screen.getByRole('radio', { name: /Limited Angle/i }));
    expect(screen.getByLabelText(/X Offset/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Transition Angle/i)).toBeInTheDocument();
  });

  it('updates the shared preview from draft connection values before save', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    expect((screen.getByLabelText(/Transition Length/i) as HTMLInputElement).value).toBe('40');
    fireEvent.change(screen.getByLabelText(/Transition Length/i), { target: { value: '70' } });
    expect((screen.getByLabelText(/Transition Length/i) as HTMLInputElement).value).toBe('70');
    expect(api.validateConnectionConfig).not.toHaveBeenCalled();
  });

  it('displays field-level errors and blocks proceed button when validation fails', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: false,
      blocking_errors: [
        {
          id: 'IF-CONN-003',
          message: 'Transition length must be a positive finite number greater than 0 mm.',
          field: 'length_mm',
          recovery_steps: ['Enter length > 0'],
        },
      ],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    const submitBtn = screen.getByRole('button', { name: /Generate Model/i });
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/ERRORS DETECTED/i)).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Transition length must be a positive finite number/i).length).toBeGreaterThan(0);
    expect(submitBtn).toBeDisabled();
  });

  it('saves valid connection settings and proceeds', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    const mockUpdate = vi.mocked(api.updateConnectionConfig).mockResolvedValue({
      ...mockApprovedProject,
      state: 'connection_configured',
    });

    const onProjectUpdate = vi.fn();

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} onProjectUpdate={onProjectUpdate} />
      </BrowserRouter>
    );

    const submitBtn = screen.getByRole('button', { name: /Generate Model/i });
    await waitFor(() => {
      expect(submitBtn).not.toBeDisabled();
    });

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        'proj_123',
        expect.objectContaining({ mode: 'coaxial', length_mm: 40 }),
        expect.objectContaining({ wall_thickness_mm: 2.4 }),
        'tok_abc'
      );
      expect(onProjectUpdate).toHaveBeenCalled();
    });
  });

  it('disables save button and displays error when transition length is changed to 0', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={{
          ...mockApprovedProject,
          loft_plan: {
            schema_revision: '0.1',
            geometry_hash: 'hash123',
            point_count: 32,
            winding: 'cw',
            seam_index: 0,
            outer_a: [],
            outer_b: [],
            inner_a: [],
            inner_b: [],
            outer_shift: 0,
            outer_reversed: false,
            inner_shift: 0,
            inner_reversed: false,
            sections: [{ z_mm: 0, outer: [], inner: [] }],
          } as any,
        }} />
      </BrowserRouter>
    );

    const lengthInput = screen.getByLabelText(/Transition Length/i);
    fireEvent.change(lengthInput, { target: { value: '0' } });

    await waitFor(() => {
      expect(screen.getByText(/ERRORS DETECTED/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Generate Model/i })).toBeDisabled();
    });
  });

  it('displays VALID WITH WARNINGS badge and warning message without error code ID when warnings exist', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [
        {
          id: 'IF-CONN-W001',
          message: 'Transition length is short (< 10 mm), causing steep loft angles.',
          field: 'length_mm',
          recovery_steps: ['Increase length'],
        },
      ],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Generate Model/i }));

    await waitFor(() => {
      expect(screen.getByText(/VALID WITH WARNINGS/i)).toBeInTheDocument();
      expect(screen.getByText('Transition length is short (< 10 mm), causing steep loft angles.')).toBeInTheDocument();
      expect(screen.queryByText(/\[IF-CONN-W001\]/i)).not.toBeInTheDocument();
    });
  });

  it('renders fit intent SVG preview boxes and updates diagram when dropdown mode changes', async () => {
    vi.mocked(api.validateConnectionConfig).mockResolvedValue({
      is_valid: true,
      blocking_errors: [],
      warnings: [],
      recommended_values: { length_mm: 40, wall_thickness_mm: 2.4 },
    });

    render(
      <BrowserRouter>
        <ConnectionConfigPage project={mockApprovedProject} />
      </BrowserRouter>
    );

    const previewBoxA = screen.getByTestId('fit-intent-preview-a');
    expect(previewBoxA).toBeInTheDocument();
    const imgA = previewBoxA.querySelector('img');
    expect(imgA).toBeInTheDocument();
    expect(imgA).toHaveAttribute('alt', 'Fit over diagram');

    const selectA = screen.getByLabelText('Interface A');
    fireEvent.change(selectA, { target: { value: 'fit_inside' } });

    expect(previewBoxA.querySelector('img')).toHaveAttribute('alt', 'Fit inside diagram');
  });
});
