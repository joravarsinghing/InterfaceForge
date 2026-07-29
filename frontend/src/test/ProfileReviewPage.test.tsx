import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ProfileReviewPage } from '../pages/ProfileReviewPage';
import { Project } from '../types/schema';
import * as api from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    patchInterface: vi.fn(),
    approveInterface: vi.fn(),
    snapScalePoint: vi.fn(),
    calibrateInterfaceScale: vi.fn(),
    resetInterfaceScaleCalibration: vi.fn(),
  };

});

const mockProject: Project = {
  project_id: 'proj_123',
  project_token: 'tok_abc',
  schema_version: '0.1',
  state: 'interface_a_review_required',
  created_at: '2026-07-22T00:00:00Z',
  updated_at: '2026-07-22T00:00:00Z',
  current_schema_revision: 1,
  interface_a: {
    id: 'interface_a',
    source_image_ref: 'artifacts/uploads/test.png',
    profile_type: 'circle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [
      {
        id: 'outer_diameter',
        label: 'Outer Diameter',
        value: 50.0,
        unit: 'mm',
        provenance: 'image_extracted',
        confidence: 0.95,
        critical: true,
      },
      {
        id: 'wall_thickness',
        label: 'Wall Thickness',
        value: 5.0,
        unit: 'mm',
        provenance: 'image_extracted',
        confidence: 0.9,
        critical: false,
      },
    ],
    validation: {
      is_closed: true,
      self_intersects: false,
      warnings: [],
    },
    approved: false,
  },
  interface_b: {
    id: 'interface_b',
    profile_type: 'rectangle',
    profile_points: [],
    center: { x: 0, y: 0 },
    dimensions: [],
    validation: {
      is_closed: true,
      self_intersects: false,
      warnings: [],
    },
    approved: false,
  },
  connection: {
    mode: 'coaxial',
    length_mm: 0,
    offset_x_mm: 0,
    offset_y_mm: 0,
    angle_deg: 0,
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

describe('ProfileReviewPage Component', () => {
  it('renders source image, clean SVG, calibration, and display-only dimensions', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByRole('heading', { name: /Interface A.*Profile Review & Approval/i })).toBeInTheDocument();
    expect(screen.getByText(/Source Image/i)).toBeInTheDocument();
    expect(screen.getByText(/Clean SVG Profile/i)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /Calibration/i })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /Interface Dimensions/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add Dimension Parameter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Update Profile/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Confirm Scale/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Update & Confirm/i })).not.toBeInTheDocument();
  });

  it('shows detected profile type and raw scale only in collapsed technical details', () => {
    const project: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
    };
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={project} />
      </BrowserRouter>
    );

    expect(screen.queryByLabelText(/Detected Profile Type/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Technical details/i)).toBeInTheDocument();
    expect(screen.getByText(/Detected profile type/i)).toBeInTheDocument();
    expect(screen.getByText(/Pixel distance/i)).toBeInTheDocument();
    expect(screen.getByText(/Scale factor/i)).toBeInTheDocument();
  });

  it('uses one consistent Replace Image action', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByRole('button', { name: /Replace Image/i })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Upload Better Image/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Re-upload Image/i })).not.toBeInTheDocument();
  });

  it('blocks approval before confirmed two-point calibration', () => {
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={mockProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Two-point calibration must be confirmed/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve Interface A/i })).toBeDisabled();
  });

  it('shows display-only primitive dimensions after confirmed calibration', () => {
    const calibratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 50,
          scale_factor: 0.5,
          confidence: 1,
          confirmed: true,
        },
      },
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={calibratedProject} />
      </BrowserRouter>
    );

    expect(screen.getAllByText(/Outer Diameter/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole('spinbutton', { name: /Value for Outer Diameter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: /Provenance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /Critical/i })).not.toBeInTheDocument();
  });

  it('preserves legacy unmapped dimensions only in technical compatibility details', () => {
    const legacyProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        dimensions: [
          ...mockProject.interface_a.dimensions,
          {
            id: 'custom_dim_1',
            label: 'Custom Dimension 1',
            value: 12,
            unit: 'mm',
            provenance: 'user_entered',
            confidence: 1,
            critical: true,
            feature_ref: null,
            consistency_state: 'unmapped',
          },
        ],
      },
    };
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={legacyProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Legacy unmapped dimensions/i)).toBeInTheDocument();
    expect(screen.getByText(/Custom Dimension 1: stored for compatibility, not used for generation/i)).toBeInTheDocument();
  });

  it('calls snap and calibration APIs for two-point SVG calibration', async () => {
    const tracedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        traced_hole_contours: [],
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          pixel_distance: 0,
          real_distance_mm: 40,
          scale_factor: 0,
          confidence: 1,
          confirmed: false,
        },
      },
    };
    vi.mocked(api.snapScalePoint)
      .mockResolvedValueOnce({ point: { x: 0, y: 0 }, distance_px: 3, feature_id: 'outer_contour' })
      .mockResolvedValueOnce({ point: { x: 100, y: 0 }, distance_px: 2, feature_id: 'outer_contour' });
    vi.mocked(api.calibrateInterfaceScale).mockResolvedValue({
      ...tracedProject,
      interface_a: {
        ...tracedProject.interface_a,
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
    });

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={tracedProject} />
      </BrowserRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Calibrate/i }));
    const svg = screen.getByRole('img', { name: /Traced closed profile SVG/i });
    fireEvent.click(svg);
    fireEvent.click(svg);

    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: false }),
      'tok_abc'
    ));

    fireEvent.click(screen.getByRole('button', { name: /Confirm Calibration/i }));
    await waitFor(() => expect(api.calibrateInterfaceScale).toHaveBeenCalledWith(
      'proj_123',
      'interface_a',
      expect.objectContaining({ confirmed: true, real_distance_mm: 40 }),
      'tok_abc'
    ));
  });

  it('hydrates markers after refresh and invalidates on real distance edit', () => {
    const hydratedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        profile_type: 'traced_closed',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        traced_hole_contours: [],
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
    };
    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={hydratedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/A: 0.00, 0.00/i)).toBeInTheDocument();
    expect(screen.getByText(/B: 100.00, 0.00/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Real distance in mm/i), { target: { value: '50' } });
    expect(screen.getAllByText(/Calibration needed/i).length).toBeGreaterThan(0);
  });

  it('renders approved state and uses recalibrate action', () => {
    const approvedProject: Project = {
      ...mockProject,
      interface_a: {
        ...mockProject.interface_a,
        approved: true,
        approved_at: '2026-07-22T01:00:00Z',
        traced_outer_contour: {
          id: 'outer_contour',
          points: [
            { x: 0, y: 0 },
            { x: 100, y: 0 },
            { x: 100, y: 50 },
            { x: 0, y: 50 },
          ],
          is_closed: true,
          classification: 'outer_contour',
          provenance: 'analysis',
          confidence: 1,
          point_count: 4,
        },
        scale_calibration: {
          source: 'user_calibration',
          method: 'two_point_trace',
          reference_dimension: 'two_point_distance',
          point_a: { x: 0, y: 0 },
          point_b: { x: 100, y: 0 },
          pixel_distance: 100,
          real_distance_mm: 40,
          scale_factor: 0.4,
          confidence: 1,
          confirmed: true,
        },
      },
      state: 'interface_a_approved',
    };

    render(
      <BrowserRouter>
        <ProfileReviewPage interfaceId="interface_a" project={approvedProject} />
      </BrowserRouter>
    );

    expect(screen.getByText(/Status: Approved/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Recalibrate/i })).toBeInTheDocument();
  });
});
